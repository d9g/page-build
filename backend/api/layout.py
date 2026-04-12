# -*- coding: utf-8 -*-
"""排版 API - SSE 流式返回"""
import logging
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from models.schemas import LayoutRequest, LayoutResponse, LayoutSection, ErrorResponse
from services.layout_service import do_layout
from services.auth_service import get_openid_from_token
from middleware.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["排版"])


@router.post("/layout/stream")
async def layout_stream(
    request: LayoutRequest,
    req: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    AI 排版接口（SSE 流式返回）
    
    返回格式：
    event: progress
    data: {"status": "processing", "message": "正在分析文章结构..."}
    
    event: progress
    data: {"status": "processing", "message": "正在 AI 智能排版..."}
    
    event: complete
    data: {"sections": [...], "html": "...", ...}
    
    event: error
    data: {"message": "错误信息"}
    """
    # Token 鉴权
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    redis_client = getattr(req.app.state, "redis", None)
    openid = await get_openid_from_token(token, redis_client)
    if not openid:
        raise HTTPException(status_code=401, detail="登录已过期")

    async def generate():
        try:
            # 频率限制
            await check_rate_limit(openid, "layout", redis_client=redis_client)

            theme_id = "default"
            if request.options:
                theme_id = request.options.get("theme", "default")

            # 发送进度心跳（保持连接，避免超时）
            yield f"event: progress\ndata: {json.dumps({'status': 'processing', 'message': '正在分析文章结构...', 'progress': 15})}\n\n"
            
            await asyncio.sleep(0.5)
            
            yield f"event: progress\ndata: {json.dumps({'status': 'processing', 'message': '正在 AI 智能排版...', 'progress': 30})}\n\n"

            # 执行排版
            result = await do_layout(content=request.content, theme_id=theme_id)

            # 发送进度更新
            yield f"event: progress\ndata: {json.dumps({'status': 'processing', 'message': '生成 HTML...', 'progress': 80})}\n\n"

            await asyncio.sleep(0.3)

            # 发送完成结果
            response_data = {
                "sections": result["sections"],
                "html": result["html"],
                "suggested_theme": result["suggested_theme"],
                "word_count": result["word_count"],
                "process_time": result["process_time"],
                "prompt_version": result["prompt_version"],
                "progress": 100,
            }
            yield f"event: complete\ndata: {json.dumps(response_data)}\n\n"

        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        except Exception as e:
            logger.exception("排版接口异常")
            yield f"event: error\ndata: {json.dumps({'message': f'排版失败: {str(e)}'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


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
    """AI 排版接口（普通返回，可能超时）"""
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

        theme_id = "default"
        if request.options:
            theme_id = request.options.get("theme", "default")

        result = await do_layout(content=request.content, theme_id=theme_id)

        return LayoutResponse(
            sections=[LayoutSection(**s) for s in result["sections"]],
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