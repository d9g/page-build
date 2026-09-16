# -*- coding: utf-8 -*-
"""
文字打印工具验证码校验 API

POST /api/printer/verify
body: {"code": "1234"}
返回: {"ok": true|false, "token": "...", "account": "...", "error": "..."}

流程说明:
- tools.webyoung.cn/text-print 用户点击「打印/导出/AI 美化」按钮
  → 弹窗输入 4 位数字验证码
  → 前端 POST /api/printer/verify {"code": "1234"}
  → 此端点调 verify_service.validate_print_code() 校验
  → 校验通过：删除 Redis 验证码（一次性使用），返回 ok=true + token
  → 校验失败：返回 ok=false + error="验证码无效或已过期"

为什么独立于 /api/v1/verify:
- /api/v1/verify 走 Bearer token + openid + db 状态，30 天免验证
- 文字打印每次操作都重新校验新鲜验证码，无 token 无 db 写入
- 用 Redis 独立命名空间 verify_code_print:{code}，与排版验证码隔离

token 设计 (2026-09-16 加):
- 校验通过后生成临时 token = account_id:gzh_openid:expires_at_ts
- 前端存 localStorage，5 分钟内凭 token 即可执行打印/导出/美化
- token TTL 校验在后端 verify_token() 函数实现
- 验证码用一次即焚，token 在 TTL 窗口内复用
"""
import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from services.verify_service import validate_print_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/printer", tags=["打印工具"])


class PrintVerifyRequest(BaseModel):
    """文字打印验证码校验请求"""
    code: str = Field(..., min_length=4, max_length=4, description="4 位数字验证码")


@router.post(
    "/verify",
    summary="文字打印验证码校验",
)
async def printer_verify(request: Request, body: PrintVerifyRequest):
    """
    校验 4 位数字验证码是否有效。
    校验通过后立即删除验证码（一次性使用），返回 token 用于 5 分钟内免验证操作。
    """
    import time

    redis_client = getattr(request.app.state, "redis", None)
    info = await validate_print_code(body.code, redis_client)

    if not info:
        return {"ok": False, "error": "验证码无效或已过期"}

    # 生成 5 分钟有效的 token (account_id:gzh_openid:expires_ts)
    account_id = info.get("account_id", "")
    gzh_openid = info.get("gzh_openid", "")
    expires_at = int(time.time()) + 300  # 5 分钟
    token = f"{account_id}:{gzh_openid}:{expires_at}"

    return {
        "ok": True,
        "token": token,
        "account": account_id,
        "expires_at": expires_at,
    }
