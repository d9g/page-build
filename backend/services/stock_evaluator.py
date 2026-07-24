# -*- coding: utf-8 -*-
"""
股票异步评估 worker
收到任务后调用 bidding-tool 内部接口，拿到评分后存入 Redis

由 wechat.py 用 asyncio.create_task() 触发，不阻塞 5 秒同步响应
"""
import logging
from typing import Optional

from config import settings
from services.stock_task_service import save_result, save_error

logger = logging.getLogger(__name__)

# 评估接口超时（秒）：bidding 内部含 5 分钟缓存命中(快) + 实时评估(慢,含同步补采)
_EVAL_TIMEOUT = 30


async def evaluate_stock_async(
    task_id: str,
    stock_code: str,
    redis_client=None,
) -> None:
    """异步评估单只股票

    流程:
        1. 调 bidding-tool 内部接口 POST /api/internal/ai-eval/run
        2. code=0 → save_result 存评分
        3. code!=0 → save_error 存错误信息
        4. 异常 → save_error

    Args:
        task_id: 任务 ID
        stock_code: 6 位股票代码
        redis_client: Redis 客户端
    """
    logger.info(f"[stock_eval] 开始评估 | task_id={task_id} | stock={stock_code}")

    try:
        import httpx
    except ImportError:
        logger.error("[stock_eval] httpx 未安装，请 pip install httpx")
        await save_error(task_id, "服务端缺少 httpx 依赖", redis_client)
        return

    try:
        async with httpx.AsyncClient(timeout=_EVAL_TIMEOUT) as client:
            resp = await client.post(
                settings.BIDDING_INTERNAL_URL,
                json={
                    "stock_code": stock_code,
                    "force_refresh": True,  # 粉丝查询走实时评估，跳过缓存
                },
            )
            data = resp.json()

        if data.get("code") == 0 and data.get("data"):
            await save_result(task_id, data["data"], redis_client)
            logger.info(
                f"[stock_eval] 评估完成 | task_id={task_id} | stock={stock_code} | "
                f"ai_score={data['data'].get('ai_score')} | msg={data.get('message')}"
            )
        else:
            err = data.get("message", "评估失败（未知原因）")
            await save_error(task_id, err, redis_client)
            logger.warning(f"[stock_eval] 评估失败 | task_id={task_id} | err={err}")

    except httpx.TimeoutException:
        await save_error(task_id, "评估超时，请稍后重试", redis_client)
        logger.error(f"[stock_eval] 评估超时 | task_id={task_id} | timeout={_EVAL_TIMEOUT}s")
    except Exception as e:
        await save_error(task_id, f"评估异常: {e}", redis_client)
        logger.exception(f"[stock_eval] 评估异常 | task_id={task_id}: {e}")
