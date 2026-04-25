# -*- coding: utf-8 -*-
"""
排版 API v4.0

双模式：
- POST /layout/quick  快速排版（需关注公众号验证）
- POST /layout        智能排版（需验证码）
- GET  /themes        获取主题列表
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from models.schemas import LayoutRequest, LayoutResponse, ErrorResponse
from services.layout_service import do_layout, do_quick_layout, get_all_themes
from services.auth_service import get_openid_from_token
from middleware.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["排版"])


@router.post(
    "/layout/quick",
    response_model=LayoutResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def quick_layout(
    request: LayoutRequest,
    req: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    快速排版 — 纯本地 Markdown → HTML，不调 AI

    需要登录（关注公众号验证），不需要验证码。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    redis_client = getattr(req.app.state, "redis", None)
    openid = await get_openid_from_token(token, redis_client)
    if not openid:
        raise HTTPException(status_code=401, detail="登录已过期")

    try:
        theme_id = "shujuan"
        if request.options:
            theme_id = request.options.get("theme", "shujuan")

        result = do_quick_layout(
            content=request.content,
            theme_id=theme_id,
        )

        return LayoutResponse(
            sections=[],
            html=result["html"],
            suggested_theme=result["suggested_theme"],
            word_count=result["word_count"],
            process_time=result["process_time"],
            prompt_version="local",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("快速排版异常")
        raise HTTPException(status_code=500, detail=f"排版失败: {str(e)}")


@router.post(
    "/layout",
    response_model=LayoutResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def layout(
    request: LayoutRequest,
    req: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    智能排版 — AI 润色 + 本地渲染

    需要验证码，消耗 API 额度。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    redis_client = getattr(req.app.state, "redis", None)
    openid = await get_openid_from_token(token, redis_client)
    if not openid:
        raise HTTPException(status_code=401, detail="登录已过期")

    try:
        await check_rate_limit(openid, "layout", redis_client=redis_client)

        theme_id = "shujuan"
        if request.options:
            theme_id = request.options.get("theme", "shujuan")

        result = await do_layout(
            content=request.content,
            theme_id=theme_id,
        )

        return LayoutResponse(
            sections=[],
            html=result["html"],
            suggested_theme=result["suggested_theme"],
            word_count=result["word_count"],
            process_time=result["process_time"],
            prompt_version=result.get("prompt_version", ""),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("智能排版异常")
        raise HTTPException(status_code=500, detail=f"排版失败: {str(e)}")


@router.get("/themes", summary="获取主题列表")
async def list_themes():
    """返回所有可用主题"""
    themes = get_all_themes()
    return {"themes": themes}