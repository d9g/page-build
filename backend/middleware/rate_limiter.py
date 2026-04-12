# -*- coding: utf-8 -*-
"""
频率限制中间件
基于 Redis 滑动窗口算法，防止接口被滥用

支持 Redis 和内存两种模式：
- Redis 模式：支持多实例部署
- 内存模式：仅单实例有效，MVP 阶段可用
"""
import time
import logging
from typing import Optional
from fastapi import HTTPException
from config import settings

logger = logging.getLogger(__name__)

# 内存模式存储
_memory_records: dict[str, list[float]] = {}


async def check_rate_limit(
    openid: str,
    action: str = "layout",
    limit: Optional[int] = None,
    window: int = 3600,
    redis_client=None,
) -> None:
    """
    滑动窗口频率限制

    默认规则：排版接口每用户每小时最多 10 次
    超限时抛出 HTTPException(429)

    参数:
        openid: 用户标识
        action: 操作类型（用于区分不同接口的限制）
        limit: 窗口内最大次数（默认使用配置值）
        window: 窗口大小（秒），默认 1 小时
        redis_client: Redis 客户端（可选）
    """
    if limit is None:
        limit = settings.RATE_LIMIT_PER_HOUR

    key = f"rate_limit:{action}:{openid}"
    now = time.time()

    if redis_client:
        # Redis 滑动窗口实现
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[2]
    else:
        # 内存模式
        if key not in _memory_records:
            _memory_records[key] = []

        # 清理过期记录
        _memory_records[key] = [
            t for t in _memory_records[key] if t > now - window
        ]
        # 添加当前请求
        _memory_records[key].append(now)
        count = len(_memory_records[key])

    if count > limit:
        remaining_seconds = int(window - (now - _memory_records.get(key, [now])[0]))
        logger.warning(
            f"频率限制触发 | openid={openid[:8]}... | action={action} | "
            f"count={count}/{limit}"
        )
        raise HTTPException(
            status_code=429,
            detail=f"操作过于频繁，请 {remaining_seconds // 60} 分钟后再试",
        )
