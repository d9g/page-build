# -*- coding: utf-8 -*-
"""
管理员 API 路由
切换推广账号、Prompt 版本管理、引流统计
所有接口需要 ADMIN_SECRET_KEY 鉴权
"""
import os
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from models.schemas import SwitchAccountRequest, SwitchPromptRequest
from services.verify_service import get_active_account_id, set_active_account_id
from services.prompt_manager import prompt_manager
from database import db
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["管理"])


def _check_admin_key(admin_key: str) -> None:
    """校验管理员密钥"""
    if not settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=500, detail="管理密钥未配置")
    if admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="无权限")


@router.post(
    "/switch-account",
    summary="切换推广账号",
    description="切换当前推广的公众号，建议在凌晨 2:00-4:00 操作",
)
async def switch_account(request: SwitchAccountRequest, req: Request):
    """
    切换当前推广的公众号

    建议操作时间：凌晨低峰期
    原因：避免用户正在关注旧号，弹窗突然变成新号的情况
    """
    _check_admin_key(request.admin_key)

    pool = settings.get_account_pool()
    pool_ids = [acc["id"] for acc in pool]
    if request.account_id not in pool_ids:
        raise HTTPException(status_code=400, detail="该账号不在公众号池内")

    redis_client = getattr(req.app.state, "redis", None)
    old_active = await get_active_account_id(redis_client)
    await set_active_account_id(request.account_id, redis_client)

    # 记录切换日志
    await db.log_account_switch(
        from_account=old_active,
        to_account=request.account_id,
        operator="admin",
        switched_at=datetime.now(),
        reason=request.reason,
    )

    logger.info(f"推广账号切换: {old_active} → {request.account_id}")
    return {
        "success": True,
        "previous": old_active,
        "current": request.account_id,
    }


@router.get(
    "/account-stats",
    summary="引流数据统计",
    description="查看各公众号的引流数据，帮助决定何时切换推广目标",
)
async def account_stats(admin_key: str, request: Request):
    """各公众号验证通过的用户数统计"""
    _check_admin_key(admin_key)

    redis_client = getattr(request.app.state, "redis", None)
    pool = settings.get_account_pool()
    stats = []

    for account in pool:
        total = await db.count_verifications(account["id"])
        recent = await db.count_verifications(
            account["id"],
            since=datetime.now() - timedelta(days=7),
        )
        stats.append({
            "account_id": account["id"],
            "name": account["name"],
            "total_verified": total,
            "last_7_days": recent,
        })

    active_id = await get_active_account_id(redis_client)
    return {"active_account": active_id, "stats": stats}


@router.post(
    "/prompt/switch",
    summary="切换 Prompt 版本",
    description="切换当前使用的排版 Prompt 版本",
)
async def switch_prompt(request: SwitchPromptRequest):
    """切换 Prompt 激活版本"""
    _check_admin_key(request.admin_key)

    try:
        old_version = prompt_manager.switch_version(request.version)
        return {
            "success": True,
            "previous": old_version,
            "current": request.version,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt 版本 {request.version} 不存在",
        )


@router.get(
    "/prompt/versions",
    summary="列出 Prompt 版本",
    description="列出所有可用的 Prompt 版本",
)
async def list_prompt_versions(admin_key: str):
    """列出所有 Prompt 版本及当前激活版本"""
    _check_admin_key(admin_key)

    versions = prompt_manager.list_versions()
    config = prompt_manager._load_config()

    return {
        "active_version": config.get("active_version", "v1.0"),
        "versions": versions,
    }
