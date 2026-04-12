# -*- coding: utf-8 -*-
"""
关注验证 API 路由
POST /api/v1/verify — 验证码校验
GET  /api/v1/user/status — 用户状态查询
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from models.schemas import VerifyRequest, VerifyResponse, UserStatusResponse
from services.auth_service import get_openid_from_token
from services.verify_service import validate_verify_code
from database import db
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["验证"])


async def _get_openid(authorization: Optional[str], request: Request) -> str:
    """从请求头 Authorization 中提取 openid"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    redis_client = getattr(request.app.state, "redis", None)
    openid = await get_openid_from_token(token, redis_client)
    if not openid:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return openid


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="验证码校验",
    description="校验用户输入的 4 位验证码，通过后 30 天内免重复验证",
)
async def verify(
    request: VerifyRequest,
    req: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    验证逻辑：
    1. 验证码必须有效（存在且未过期）
    2. 验证码对应的公众号在池内（任一均可通过）
    3. 记录验证日志
    4. 更新用户验证状态（30 天有效）
    """
    openid = await _get_openid(authorization, req)
    redis_client = getattr(req.app.state, "redis", None)

    info = await validate_verify_code(request.code, redis_client)
    user = await db.get_user_by_openid(openid)

    if not info:
        if user:
            await db.log_verification(user["id"], request.code, "", "fail")
        return VerifyResponse(success=False, message="验证码无效或已过期")

    # 验证通过
    expires_at = datetime.now() + timedelta(days=settings.VERIFY_VALID_DAYS)
    await db.save_verification(openid, info["account_id"], expires_at)
    await db.log_verification(
        user["id"] if user else None,
        request.code,
        info["account_id"],
        "success",
    )

    logger.info(f"关注验证通过 | openid={openid[:8]}... | account={info['account_id']}")
    return VerifyResponse(
        success=True,
        message="验证成功",
        valid_days=settings.VERIFY_VALID_DAYS,
    )


@router.get(
    "/user/status",
    response_model=UserStatusResponse,
    summary="用户状态",
    description="查询用户验证状态和排版统计",
)
async def user_status(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """返回用户当前的验证状态和使用统计"""
    openid = await _get_openid(authorization, request)
    user = await db.get_user_by_openid(openid)

    if not user:
        return UserStatusResponse(verified=False)

    verified = await db.check_user_verified(openid)
    return UserStatusResponse(
        verified=verified,
        verified_account=user.get("verified_account"),
        expires_at=user.get("verify_expires_at"),
        layout_count=user.get("layout_count", 0),
    )
