# -*- coding: utf-8 -*-
"""
认证服务
微信小程序登录：code 换 session、Token 生成与验证
"""
import hashlib
import secrets
import time
import json
import logging
import httpx
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# NOTE: 使用 Redis 存储 session token，
# 如果 Redis 不可用则降级为内存存储（仅单实例有效）
_memory_sessions: dict[str, dict] = {}

# Token 有效期 2 小时
TOKEN_EXPIRE_SECONDS = 7200


async def wechat_code_to_session(code: str) -> dict:
    """
    用小程序 wx.login 获取的 code 换取 openid 和 session_key

    调用微信接口：
    GET https://api.weixin.qq.com/sns/jscode2session
    """
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.MINI_APP_ID,
        "secret": settings.MINI_APP_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        result = response.json()

    if "errcode" in result and result["errcode"] != 0:
        logger.error(f"微信登录失败: {result}")
        raise ValueError(f"微信登录失败: {result.get('errmsg', '未知错误')}")

    return {
        "openid": result["openid"],
        "session_key": result["session_key"],
    }


def generate_token(openid: str) -> str:
    """
    生成会话 token
    基于 openid + 时间戳 + 随机数生成唯一 token
    """
    raw = f"{openid}:{time.time()}:{secrets.token_hex(16)}"
    token = hashlib.sha256(raw.encode()).hexdigest()
    return token


async def save_session(
    token: str,
    openid: str,
    redis_client=None,
) -> None:
    """
    保存 session 到 Redis（优先）或内存

    session 数据结构：
    {
        "openid": "xxx",
        "created_at": 1234567890
    }
    """
    session_data = json.dumps({
        "openid": openid,
        "created_at": int(time.time()),
    })

    if redis_client:
        await redis_client.setex(
            f"session:{token}",
            TOKEN_EXPIRE_SECONDS,
            session_data,
        )
    else:
        _memory_sessions[token] = {
            "data": session_data,
            "expires_at": time.time() + TOKEN_EXPIRE_SECONDS,
        }


async def get_session(
    token: str,
    redis_client=None,
) -> Optional[dict]:
    """
    通过 token 获取 session 数据
    返回 None 表示 token 无效或已过期
    """
    if redis_client:
        data = await redis_client.get(f"session:{token}")
        if data:
            return json.loads(data)
        return None
    else:
        entry = _memory_sessions.get(token)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del _memory_sessions[token]
            return None
        return json.loads(entry["data"])


async def get_openid_from_token(
    token: str,
    redis_client=None,
) -> Optional[str]:
    """
    从 token 中提取 openid
    这是最常用的鉴权方法
    """
    session = await get_session(token, redis_client)
    if session:
        return session.get("openid")
    return None
