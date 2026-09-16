# -*- coding: utf-8 -*-
"""
文字打印工具验证码校验 API

POST /api/printer/verify
body: {"code": "1234"}
返回: {"ok": true|false, "error": "..."}

流程说明:
- tools.webyoung.cn/text-print 用户点击「打印/导出/AI 美化」按钮
  → 弹窗输入 4 位数字验证码
  → 前端 POST /api/printer/verify {"code": "1234"}
  → 此端点调 verify_service.validate_print_code() 校验
  → 校验通过：删除 Redis 验证码（一次性使用），返回 ok=true
  → 校验失败：返回 ok=false + error="验证码无效或已过期"

为什么独立于 /api/v1/verify:
- /api/v1/verify 走 Bearer token + openid + db 状态，30 天免验证
- 文字打印每次操作都重新校验新鲜验证码，无 token 无 db 写入
- 用 Redis 独立命名空间 verify_code_print:{code}，与排版验证码隔离
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
    校验通过后立即删除验证码（一次性使用）。
    """
    redis_client = getattr(request.app.state, "redis", None)
    info = await validate_print_code(body.code, redis_client)

    if not info:
        return {"ok": False, "error": "验证码无效或已过期"}

    return {"ok": True, "account": info.get("account_id", "")}