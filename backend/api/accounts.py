# -*- coding: utf-8 -*-
"""
公众号账户 API 路由
GET /api/v1/accounts/active — 获取当前推广的公众号
"""
import logging
from fastapi import APIRouter, Request
from models.schemas import ActiveAccountResponse
from services.verify_service import get_active_account_id
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/accounts", tags=["账户"])


@router.get(
    "/active",
    response_model=ActiveAccountResponse,
    summary="获取当前推广账号",
    description="返回当前激活推广的单个公众号信息，前端据此展示关注验证弹窗",
)
async def get_active_account(request: Request):
    """
    只返回一个公众号信息（当前推广中的），不暴露整个池子
    """
    redis_client = getattr(request.app.state, "redis", None)
    pool = settings.get_account_pool()

    if not pool:
        return ActiveAccountResponse(
            account={"id": "", "name": "暂未配置", "qrcode": ""},
            keyword=settings.VERIFY_KEYWORD,
            verify_valid_days=settings.VERIFY_VALID_DAYS,
        )

    active_id = await get_active_account_id(redis_client)

    # 查找对应的公众号信息
    account = None
    for acc in pool:
        if acc["id"] == active_id:
            account = acc
            break
    if not account:
        account = pool[0]

    # 只返回前端需要的字段（不暴露 app_secret 等敏感信息）
    safe_account = {
        "id": account["id"],
        "name": account["name"],
        "description": account.get("description", ""),
        "avatar": account.get("avatar", ""),
        "qrcode": account.get("qrcode", ""),
    }

    return ActiveAccountResponse(
        account=safe_account,
        keyword=settings.VERIFY_KEYWORD,
        verify_valid_days=settings.VERIFY_VALID_DAYS,
    )
