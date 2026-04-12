# -*- coding: utf-8 -*-
"""
排版 API — 普通 POST 返回
模型配置在后端 .env 中，前端不感知
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
    AI 排版接口

    前端只传 content 和 theme，模型由后端 .env 控制。
    """
    # Token 鉴权
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    redis_client = getattr(req.app.state, "redis", None)
    openid = await get_openid_from_token(token, redis_client)
    if not openid:
        raise HTTPException(status_code=401, detail="登录已过期")

    try:
        # 频率限制
        await check_rate_limit(openid, "layout", redis_client=redis_client)

        # 解析主题
        theme_id = "default"
        if request.options:
            theme_id = request.options.get("theme", "default")

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
            prompt_version=result["prompt_version"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("排版接口异常")
        raise HTTPException(status_code=500, detail=f"排版失败: {str(e)}")