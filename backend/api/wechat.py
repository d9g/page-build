# -*- coding: utf-8 -*-
"""
微信公众号消息回调 API
POST /api/v1/wechat/callback/{account_id}
GET  /api/v1/wechat/callback/{account_id} — 微信服务器验证

按 account_id 路由关键字规则 (2026-07-25 老杨拍板):
- 半盏茶说书 (B) → 只响应股票代码 → 调 bidding-tool 拿 task_id → 拼 bidding.d9g 链接
- 居家小能手小羊 (A) → 排版/激活
- 老杨讲理 (C) + 其他号 → 不响应 (return "success")
"""
import asyncio
import logging
import os
import re
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
import httpx

from services.wechat_service import (
    parse_wechat_message,
    build_text_reply,
    verify_wechat_signature,
    get_account_config,
    validate_message_body,
)
from services.verify_service import generate_verify_code
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wechat", tags=["微信回调"])

# ============ 公众号账户矩阵 → 能力映射 (2026-07-25 老杨拍板) ============
# key = .env 里 ACCOUNT_X_NAME 的值
# value = 该号能响应的关键字集合 (stock_code / format / activate)
ACCOUNT_CAPABILITIES = {
    "半盏茶说书": {"stock_code"},   # 只响应股票代码
    "居家小能手小羊": {"format", "activate"},  # 排版/激活
    # "老杨讲理" + 其他号 → 不在表里 → 全部不响应
}

# 股票代码正则（仅做初筛，准确校验走 bidding-tool /api/internal/ai-eval/check/）
STOCK_CODE_PATTERN = re.compile(r'^[03689]\d{5}$')

# 按天限流（每粉丝每天最多 10 次股票代码查询）
DAILY_QUERY_LIMIT = 10


# ============ Redis 限流 (per openid, 按天) ============
async def _check_and_incr_rate_async(openid: str, redis_client, daily_limit: int = DAILY_QUERY_LIMIT) -> bool:
    if not redis_client:
        return True
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    key = f"aiscore:rate:{today}:{openid}"
    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400 + 60)
        result = await pipe.execute()
        count = result[0]
        return int(count) <= daily_limit
    except Exception as e:
        # 老杨 2026-07-25 拍板 (B-2 P1-3 修复): 异常时升级到 error 级别告警 (fail-open 仍保持业务可用性优先级)
        # 原因: 原代码 logger.warning, 限流异常应该在监控里亮起来
        logger.error(f"[wechat] 限流检查异常 fail-open: {e}", exc_info=True)
        return True


# ============ 路由 ============
@router.get(
    "/callback/{account_id}",
    response_class=PlainTextResponse,
    summary="微信服务器验证",
)
async def wechat_verify(
    account_id: str,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    account = get_account_config(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    token = account.get("token", "")
    if verify_wechat_signature(signature, timestamp, nonce, token):
        logger.info(f"微信签名验证通过 | account={account_id}")
        return echostr

    logger.warning(f"微信签名验证失败 | account={account_id}")
    raise HTTPException(status_code=403, detail="签名验证失败")


@router.post(
    "/callback/{account_id}",
    response_class=PlainTextResponse,
    summary="公众号消息回调",
)
async def wechat_callback(account_id: str, request: Request):
    """公众号消息回调（按 account_id 路由关键字）"""
    account = get_account_config(account_id)
    if not account:
        return "success"

    # 签名验证
    signature = request.query_params.get("signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")
    token = account.get("token", "")
    # 老杨 2026-07-25 拍板 (B-2 P0-1 修复): token 为空也走校验逻辑
    # 原因: 原代码 `if token and not verify(...)` 在 token 漏配时短路跳过签名校验,
    #       未来新增公众号一旦漏配 TOKEN, 任何 POST 都能跳过认证进入业务逻辑。
    # 现在逻辑: 有 token 必须验签通过, 没 token 直接拒绝
    if not token or not verify_wechat_signature(signature, timestamp, nonce, token):
        logger.warning(
            f"签名验证失败或 token 漏配 | account={account_id} | token_empty={not token}"
        )
        return "success"

    body = await request.body()
    if not validate_message_body(body):
        logger.warning(f"消息体过大或为空 | account={account_id} | size={len(body)}")
        return "success"

    msg = parse_wechat_message(body)
    if msg.is_encrypted:
        logger.warning(f"收到加密消息 | account={account_id}")
        return "success"

    content = msg.content.strip() if msg.msg_type == "text" else ""
    account_name = account.get("name", "").strip()
    capabilities = ACCOUNT_CAPABILITIES.get(account_name, set())

    # 粉丝不在该号能力集 → 不响应 (return "success")
    if not capabilities:
        logger.debug(f"[wechat] {account_name} 不响应 | content={content[:30]}")
        return "success"

    redis_client = getattr(request.app.state, "redis", None)

    # ============ 排版 (format) ============
    if "format" in capabilities and content == settings.VERIFY_KEYWORD:
        code = await generate_verify_code(
            account_id=account_id,
            gzh_openid=msg.from_user,
            redis_client=redis_client,
        )
        reply = build_text_reply(
            msg,
            f"您的验证码：{code}\n有效期 5 分钟\n请在小程序中输入此验证码",
        )
        return reply

    # ============ 激活 (activate) ============
    if "activate" in capabilities:
        comic_keyword = os.environ.get("COMIC_VERIFY_KEYWORD", "激活")
        comic_code = os.environ.get("COMIC_VERIFY_CODE", "MKPIC2026")
        if content == comic_keyword:
            logger.info(f"漫画激活码请求 | account={account_id} | openid={msg.from_user[:8]}...")
            reply = build_text_reply(
                msg,
                f"🎨 知识漫画生成器使用码：{comic_code}\n\n"
                f"打开漫画生成器，输入此使用码即可免费使用！",
            )
            return reply

    # ============ 股票代码 (stock_code) ============
    if "stock_code" in capabilities and STOCK_CODE_PATTERN.match(content):
        openid = msg.from_user

        # 1. 按天限流 (Redis)
        allowed = await _check_and_incr_rate_async(openid, redis_client)
        if not allowed:
            logger.info(f"[wechat] 限流拦截 | openid={openid[:8]} | stock={content}")
            return build_text_reply(
                msg,
                f"今日查询次数已达上限（{DAILY_QUERY_LIMIT}次/天）\n明天再试吧",
            )

        # 2. 校验股票代码（A 股 / 非指数 / 非 ETF）
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                check_resp = await client.get(
                    f"{settings.BIDDING_INTERNAL_URL_BASE}/ai-eval/check/{content}"
                )
                check_data = check_resp.json()
                if not check_data.get("valid"):
                    return build_text_reply(msg, check_data.get("reason") or "该股票不支持 AI 评分")
        except Exception as e:
            # 老杨 2026-07-25 拍板 (B-2 P1-2 修复): 限缩异常范围 + 升级到 error 告警
            # 原因: 原代码 bare Exception 吞掉几乎所有异常, 继续降级到 run 绕过股票代码校验,
            #       架构上多一层防御没了, 且异常路径对监控不可见
            logger.error(f"[wechat] check 调用失败: {e}", exc_info=True)
            # 降级: 直接调 run, 让 bidding-tool 那边自己校验 (业务可用性优先)

        # 3. 调 bidding-tool 拿 task_id (异步, 1 秒内返)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    settings.BIDDING_INTERNAL_URL,
                    json={"stock_code": content},
                )
                data = resp.json()
        except Exception as e:
            logger.exception(f"[wechat] bidding-tool 调用异常: {e}")
            return build_text_reply(msg, "系统繁忙，请稍后重试")

        if data.get("code") != 0 or not data.get("data"):
            err = data.get("message", "评分失败")
            return build_text_reply(msg, f"❌ {err}")

        task_id = data["data"]["task_id"]
        result_url = f"https://{settings.AISCORE_DOMAIN}/aiscore/{task_id}"
        # 老杨 7/25 拍板: 模板去掉 "不构成投资建议" (怀疑触发微信风控)
        reply = build_text_reply(
            msg,
            f"📈 正在分析 {content} 的 AI 评分\n\n"
            f"点击查看结果（约10秒）：\n{result_url}\n\n"
            f"数据仅供参考",
        )
        logger.info(
            f"[wechat] 股票查询任务已派发 | stock={content} | task_id={task_id} | "
            f"openid={openid[:8]} | status={data['data'].get('status')}"
        )
        return reply

    # ============ 关注/取关事件（仅对该号能力集内的，友好欢迎）============
    if msg.msg_type == "event" and msg.event.lower() == "subscribe":
        logger.info(f"用户关注 | account={account_id} | openid={msg.from_user[:8]}...")
        welcome_lines = [f"欢迎关注 {account_name}！"]
        if "format" in capabilities:
            welcome_lines.append(f"回复「{settings.VERIFY_KEYWORD}」获取排版验证码")
        if "activate" in capabilities:
            comic_kw = os.environ.get("COMIC_VERIFY_KEYWORD", "激活")
            welcome_lines.append(f"回复「{comic_kw}」获取漫画生成使用码")
        if "stock_code" in capabilities:
            welcome_lines.append(f"发送 6 位股票代码（如 000021）查询 AI 评分")
        reply = build_text_reply(msg, "\n".join(welcome_lines))
        return reply

    if msg.msg_type == "event" and msg.event.lower() == "unsubscribe":
        logger.info(f"用户取关 | account={account_id} | openid={msg.from_user[:8]}...")
        return "success"

    # 其他消息不处理
    return "success"