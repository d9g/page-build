# -*- coding: utf-8 -*-
"""
排版 API — 普通 POST 返回
支持 provider + model 双维度选择 AI 模型
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from models.schemas import LayoutRequest, LayoutResponse, ErrorResponse
from services.layout_service import do_layout
from services.ai_service import get_available_providers
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

    支持 options 中传入：
    - theme: 主题 ID（默认 default）
    - provider: 厂商 ID（zhipu / dashscope，默认 zhipu）
    - model: 模型名称（如 glm-4-flash / glm-5 / qwen-max，默认 glm-4-flash）
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

        # 解析选项
        theme_id = "default"
        provider = "zhipu"
        model = "glm-4-flash"
        if request.options:
            theme_id = request.options.get("theme", "default")
            provider = request.options.get("provider", "zhipu")
            model = request.options.get("model", "glm-4-flash")

        result = await do_layout(
            content=request.content,
            theme_id=theme_id,
            model=model,
            provider=provider,
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


@router.get("/providers", summary="获取可用 AI 厂商列表")
async def list_providers():
    """返回当前已配置 API Key 的可用厂商"""
    providers = get_available_providers()
    return {"providers": providers}