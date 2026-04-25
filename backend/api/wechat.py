# -*- coding: utf-8 -*-
"""
微信公众号消息回调 API
POST /api/v1/wechat/callback/{account_id}
GET  /api/v1/wechat/callback/{account_id} — 微信服务器验证

所有公众号共用同一个后端，通过 URL 路径参数 account_id 区分
"""
import logging
import os
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
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


@router.get(
    "/callback/{account_id}",
    response_class=PlainTextResponse,
    summary="微信服务器验证",
    description="微信开发者平台配置消息回调时的签名验证",
)
async def wechat_verify(
    account_id: str,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """
    微信服务器验证接口

    配置消息回调时，微信会发 GET 请求验证签名，
    验证通过后原样返回 echostr
    """
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
    description="处理公众号推送的消息，用户发送「排版」关键词时生成验证码",
)
async def wechat_callback(account_id: str, request: Request):
    """
    公众号消息回调处理

    安全措施：
    1. 验证 account_id 在池内
    2. 验证微信签名，防止伪造消息
    3. 校验消息体大小，防止超大请求
    """
    account = get_account_config(account_id)
    if not account:
        return "success"

    # 签名验证：防止攻击者伪造消息
    signature = request.query_params.get("signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")
    token = account.get("token", "")
    if token and not verify_wechat_signature(signature, timestamp, nonce, token):
        logger.warning(f"消息签名验证失败 | account={account_id}")
        return "success"

    body = await request.body()

    # 消息体大小校验，防止超大 XML 请求
    if not validate_message_body(body):
        logger.warning(f"消息体过大或为空 | account={account_id} | size={len(body)}")
        return "success"

    msg = parse_wechat_message(body)

    # 加密消息检测：提示用户配置明文模式或 EncodingAESKey
    if msg.is_encrypted:
        logger.warning(f"收到加密消息 | account={account_id} | 请配置明文模式或添加解密支持")
        return "success"

    # 处理文本消息
    content = msg.content.strip() if msg.msg_type == "text" else ""

    # NOTE: 排版工具验证码
    if content == settings.VERIFY_KEYWORD:
        redis_client = getattr(request.app.state, "redis", None)
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

    # NOTE: 知识漫画生成器激活码（固定码，通过环境变量可配）
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

    # 处理关注事件：推送欢迎语
    if msg.msg_type == "event" and msg.event.lower() == "subscribe":
        logger.info(f"用户关注 | account={account_id} | openid={msg.from_user[:8]}...")
        comic_kw = os.environ.get("COMIC_VERIFY_KEYWORD", "激活")
        reply = build_text_reply(
            msg,
            f"欢迎关注 {account.get('name', '')}！\n\n"
            f"回复「{settings.VERIFY_KEYWORD}」获取排版验证码\n"
            f"回复「{comic_kw}」获取漫画生成使用码",
        )
        return reply

    # 处理取关事件：记录日志
    if msg.msg_type == "event" and msg.event.lower() == "unsubscribe":
        logger.info(f"用户取关 | account={account_id} | openid={msg.from_user[:8]}...")
        return "success"

    # 其他消息不处理
    return "success"
