# -*- coding: utf-8 -*-
"""
排版 API 路由
POST /api/v1/layout — AI 排版（核心接口）
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from models.schemas import LayoutRequest, LayoutResponse, ErrorResponse
from services.layout_service import do_layout
from services.auth_service import get_openid_from_token
from middleware.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["排版"])


@router.post(
    "/layout",
    response_model=LayoutResponse,
    responses={
        400: {"model": ErrorResponse, "description": "输入校验失败"},
        401: {"model": ErrorResponse, "description": "未登录"},
        429: {"model": ErrorResponse, "description": "频率限制"},
        500: {"model": ErrorResponse, "description": "服务器错误"},
    },
    summary="AI 智能排版",
    description="将原始文章文本通过 AI 进行专业排版，返回结构化结果和 HTML",
)
async def layout(
    request: LayoutRequest,
    req: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    AI 排版接口

    流程：Token 鉴权 → 频率限制 → 输入校验 → Prompt → AI → 结果
    """
    # 1. Token 鉴权
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    redis_client = getattr(req.app.state, "redis", None)
    openid = await get_openid_from_token(token, redis_client)
    if not openid:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    try:
        # 2. 频率限制（每用户每小时最多 10 次）
        await check_rate_limit(openid, "layout", redis_client=redis_client)

        # 3. 从选项中提取主题（默认使用 default）
        theme_id = "default"
        if request.options:
            theme_id = request.options.get("theme", "default")

        result = await do_layout(
            content=request.content,
            theme_id=theme_id,
        )

        return LayoutResponse(
            sections=result["sections"],
            html=result["html"],
            suggested_theme=result["suggested_theme"],
            word_count=result["word_count"],
            process_time=result["process_time"],
            prompt_version=result["prompt_version"],
        )

    except ValueError as e:
        # 输入校验失败或 API Key 未配置
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # 频率限制等已包装好的 HTTP 异常直接透传
        raise
    except Exception as e:
        logger.exception("排版接口异常")
        raise HTTPException(status_code=500, detail=f"排版失败: {str(e)}")
