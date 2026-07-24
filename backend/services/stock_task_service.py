# -*- coding: utf-8 -*-
"""
股票查询任务服务
基于 Redis 的异步任务管理（创建/查询/存结果），内存降级兜底

任务状态机: pending → done / error
任务数据结构（Redis JSON）:
    {
        "task_id": "xxx",
        "stock_code": "002218",
        "openid": "openid_xxx",
        "status": "pending" | "done" | "error",
        "result": {...17字段评分},
        "error": "错误信息",
        "created_at": 1234567890,
        "done_at": 1234567890
    }

Redis key: stock_task:{task_id}
TTL: settings.STOCK_TASK_TTL_SECONDS（默认 24 小时）
"""
import json
import time
import uuid
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# 内存降级存储（Redis 不可用时使用）
_memory_tasks: dict = {}

# MsgId 去重缓存（防微信 5 秒重试 3 次导致重复创建任务）
# key: msg_id, value: task_id
_memory_msgid_map: dict = {}

_TASK_KEY_PREFIX = "stock_task:"
_MSGID_KEY_PREFIX = "stock_msgid:"


def _now() -> int:
    return int(time.time())


async def create_task(
    stock_code: str,
    openid: str,
    msg_id: str = "",
    redis_client=None,
) -> Optional[str]:
    """创建查询任务

    Args:
        stock_code: 6 位股票代码
        openid: 粉丝 openid
        msg_id: 微信消息 ID（用于去重，防 5 秒重试 3 次重复创建）
        redis_client: Redis 客户端（None 时走内存）

    Returns:
        task_id（已存在则返回已有的 task_id），失败返回 None
    """
    # MsgId 去重：同一消息 3 次重试只创建一次任务
    if msg_id:
        existing = await _get_task_by_msgid(msg_id, redis_client)
        if existing:
            logger.info(f"[stock_task] MsgId 去重命中 | msg_id={msg_id} | task_id={existing}")
            return existing

    task_id = uuid.uuid4().hex[:16]
    task_data = {
        "task_id": task_id,
        "stock_code": stock_code,
        "openid": openid[:32],  # 只存前 32 位，够用且省空间
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": _now(),
        "done_at": None,
    }

    ttl = settings.STOCK_TASK_TTL_SECONDS

    if redis_client:
        try:
            await redis_client.setex(
                f"{_TASK_KEY_PREFIX}{task_id}",
                ttl,
                json.dumps(task_data, ensure_ascii=False),
            )
            # MsgId 映射也存一份（60 秒足够覆盖 3 次重试窗口）
            if msg_id:
                await redis_client.setex(
                    f"{_MSGID_KEY_PREFIX}{msg_id}",
                    60,
                    task_id,
                )
            logger.info(f"[stock_task] 任务已创建 | task_id={task_id} | stock={stock_code}")
            return task_id
        except Exception as e:
            logger.warning(f"[stock_task] Redis 写入失败，降级内存: {e}")

    # 内存模式
    _memory_tasks[task_id] = {
        "data": json.dumps(task_data, ensure_ascii=False),
        "expires_at": _now() + ttl,
    }
    if msg_id:
        _memory_msgid_map[msg_id] = {"task_id": task_id, "expires_at": _now() + 60}
    logger.info(f"[stock_task] 任务已创建(内存) | task_id={task_id} | stock={stock_code}")
    return task_id


async def get_task(task_id: str, redis_client=None) -> Optional[dict]:
    """查询任务状态和结果

    Returns:
        任务字典（含 status/result 等），不存在返回 None
    """
    if redis_client:
        try:
            raw = await redis_client.get(f"{_TASK_KEY_PREFIX}{task_id}")
            if raw:
                return json.loads(raw)
            return None
        except Exception as e:
            logger.warning(f"[stock_task] Redis 读取失败，降级内存: {e}")

    # 内存模式
    entry = _memory_tasks.get(task_id)
    if not entry:
        return None
    if _now() > entry["expires_at"]:
        del _memory_tasks[task_id]
        return None
    return json.loads(entry["data"])


async def save_result(
    task_id: str,
    result: dict,
    redis_client=None,
) -> bool:
    """保存评估结果，标记任务为 done

    Returns:
        True 成功，False 任务不存在
    """
    task = await get_task(task_id, redis_client)
    if not task:
        logger.warning(f"[stock_task] 保存结果失败：任务不存在 | task_id={task_id}")
        return False

    task["status"] = "done"
    task["result"] = result
    task["done_at"] = _now()

    ttl = settings.STOCK_TASK_TTL_SECONDS
    if redis_client:
        try:
            await redis_client.setex(
                f"{_TASK_KEY_PREFIX}{task_id}",
                ttl,
                json.dumps(task, ensure_ascii=False),
            )
            logger.info(f"[stock_task] 结果已保存 | task_id={task_id} | status=done")
            return True
        except Exception as e:
            logger.warning(f"[stock_task] Redis 写入失败，降级内存: {e}")

    # 内存模式
    _memory_tasks[task_id] = {
        "data": json.dumps(task, ensure_ascii=False),
        "expires_at": _now() + ttl,
    }
    return True


async def save_error(
    task_id: str,
    error: str,
    redis_client=None,
) -> bool:
    """保存错误信息，标记任务为 error"""
    task = await get_task(task_id, redis_client)
    if not task:
        return False

    task["status"] = "error"
    task["error"] = error
    task["done_at"] = _now()

    ttl = settings.STOCK_TASK_TTL_SECONDS
    if redis_client:
        try:
            await redis_client.setex(
                f"{_TASK_KEY_PREFIX}{task_id}",
                ttl,
                json.dumps(task, ensure_ascii=False),
            )
            return True
        except Exception as e:
            logger.warning(f"[stock_task] Redis 写入失败，降级内存: {e}")

    _memory_tasks[task_id] = {
        "data": json.dumps(task, ensure_ascii=False),
        "expires_at": _now() + ttl,
    }
    return True


async def _get_task_by_msgid(msg_id: str, redis_client=None) -> Optional[str]:
    """通过 MsgId 查已创建的 task_id（去重用）"""
    if redis_client:
        try:
            task_id = await redis_client.get(f"{_MSGID_KEY_PREFIX}{msg_id}")
            if task_id:
                return task_id if isinstance(task_id, str) else task_id.decode()
            return None
        except Exception:
            pass

    entry = _memory_msgid_map.get(msg_id)
    if not entry:
        return None
    if _now() > entry["expires_at"]:
        del _memory_msgid_map[msg_id]
        return None
    return entry["task_id"]
