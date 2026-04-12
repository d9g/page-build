# -*- coding: utf-8 -*-
"""
关注验证服务
验证码生成、校验、过期管理
"""
import json
import random
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# 内存降级存储（Redis 不可用时使用）
_memory_codes: dict[str, dict] = {}


async def generate_verify_code(
    account_id: str,
    gzh_openid: str,
    redis_client=None,
) -> str:
    """
    生成 4 位数字验证码并存储

    key 格式: verify_code:{code}
    value: {"account_id": "xxx", "gzh_openid": "xxx"}
    有效期: 5 分钟
    """
    code = str(random.randint(1000, 9999))

    data = json.dumps({
        "account_id": account_id,
        "gzh_openid": gzh_openid,
    })

    if redis_client:
        await redis_client.setex(
            f"verify_code:{code}",
            settings.VERIFY_CODE_EXPIRE_SECONDS,
            data,
        )
    else:
        import time
        _memory_codes[code] = {
            "data": data,
            "expires_at": time.time() + settings.VERIFY_CODE_EXPIRE_SECONDS,
        }

    logger.info(f"验证码已生成 | code={code} | account={account_id}")
    return code


async def validate_verify_code(
    code: str,
    redis_client=None,
) -> Optional[dict]:
    """
    校验验证码

    验证逻辑：
    1. 验证码必须存在且未过期
    2. 验证码对应的公众号必须在池内（任一均可通过）
    3. 验证通过后删除验证码（一次性使用）

    返回 {"account_id": "xxx", "gzh_openid": "xxx"} 或 None
    """
    if redis_client:
        data = await redis_client.get(f"verify_code:{code}")
        if not data:
            return None
        info = json.loads(data)
    else:
        import time
        entry = _memory_codes.get(code)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del _memory_codes[code]
            return None
        info = json.loads(entry["data"])

    # 检查 account_id 是否在公众号池内
    pool = settings.get_account_pool()
    pool_ids = [acc["id"] for acc in pool]
    if info["account_id"] not in pool_ids:
        logger.warning(f"验证码 {code} 对应的公众号 {info['account_id']} 不在池内")
        return None

    # 删除已使用的验证码
    if redis_client:
        await redis_client.delete(f"verify_code:{code}")
    else:
        _memory_codes.pop(code, None)

    logger.info(f"验证码校验通过 | code={code} | account={info['account_id']}")
    return info


async def get_active_account_id(redis_client=None) -> str:
    """
    获取当前激活推广的公众号 ID
    优先级：Redis > 内存全局变量 > 池内第一个
    """
    pool = settings.get_account_pool()
    if not pool:
        return ""

    if redis_client:
        active_id = await redis_client.get("active_account")
        if active_id:
            # Redis 返回 bytes，需要解码
            if isinstance(active_id, bytes):
                active_id = active_id.decode()
            return active_id

    # 内存模式：读取全局变量
    if _active_account_id:
        return _active_account_id

    # 都没有时返回池内第一个作为默认值
    return pool[0]["id"]


async def set_active_account_id(
    account_id: str,
    redis_client=None,
) -> None:
    """
    设置当前激活推广的公众号 ID
    """
    if redis_client:
        await redis_client.set("active_account", account_id)
    else:
        # 内存模式下使用全局变量
        global _active_account_id
        _active_account_id = account_id


# 内存模式下的激活账号
_active_account_id: Optional[str] = None
