# -*- coding: utf-8 -*-
"""
主题 API 路由
GET /api/v1/themes — 获取所有可用主题
"""
from fastapi import APIRouter
from services.layout_service import get_all_themes

router = APIRouter(prefix="/api/v1", tags=["主题"])


@router.get(
    "/themes",
    summary="获取主题列表",
    description="返回所有可用的排版主题及其样式配置，前端据此渲染主题选择器",
)
async def list_themes():
    """
    返回主题列表

    包含免费主题和付费主题（is_premium=True 的主题需要看激励视频解锁）
    """
    themes = get_all_themes()
    return {"themes": themes}
