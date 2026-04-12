# -*- coding: utf-8 -*-
"""
认证 API 路由
POST /api/v1/auth/login — 微信登录
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from models.schemas import LoginRequest, LoginResponse
from services.auth_service import (
    wechat_code_to_session,
    generate_token,
    save_session,
)
from database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="微信登录",
    description="使用 wx.login 获取的 code 进行登录，返回 session token",
)
async def login(request: LoginRequest, req: Request):
    """
    微信登录流程：
    1. 用 code 调微信 code2Session → 获取 openid
    2. 创建或更新用户记录
    3. 生成 session token 存入 Redis
    4. 返回 token + 验证状态
    """
    try:
        # 1. code 换 session
        wx_session = await wechat_code_to_session(request.code)
        openid = wx_session["openid"]
        session_key = wx_session["session_key"]

        # 2. 创建或更新用户
        user = await db.create_or_update_user(openid, session_key)

        # 3. 生成 token
        token = generate_token(openid)
        redis_client = getattr(req.app.state, "redis", None)
        await save_session(token, openid, redis_client)

        # 4. 检查验证状态
        verified = await db.check_user_verified(openid)

        logger.info(f"用户登录成功 | openid={openid[:8]}... | verified={verified}")
        return LoginResponse(token=token, verified=verified, quota=10)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("登录异常")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")
