# -*- coding: utf-8 -*-
"""
AI 服务模块
封装智谱 GLM-4-Flash API 调用
"""
import httpx
import json
import logging
from config import settings

logger = logging.getLogger(__name__)


async def call_glm4_flash(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> dict:
    """
    调用智谱 GLM-4-Flash 模型（普通模式）
    返回完整的 API 响应数据

    temperature 设为 0.3——排版场景需要较低的随机性，
    确保同一篇文章多次排版结果一致
    """
    if not settings.ZHIPU_API_KEY:
        raise ValueError("ZHIPU_API_KEY 未配置")

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            settings.ZHIPU_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.ZHIPU_API_KEY}",
            },
            json={
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        result = response.json()

        # 记录 token 使用量
        usage = result.get("usage", {})
        logger.info(
            f"AI 调用完成 | 输入 tokens: {usage.get('prompt_tokens', 0)} | "
            f"输出 tokens: {usage.get('completion_tokens', 0)} | "
            f"总计: {usage.get('total_tokens', 0)}"
        )

        return result




def extract_content(response: dict) -> str:
    """
    从 API 响应中提取生成的文本内容
    """
    choices = response.get("choices", [])
    if not choices:
        raise ValueError("AI 返回结果为空")
    return choices[0].get("message", {}).get("content", "")


def extract_usage(response: dict) -> dict:
    """
    从 API 响应中提取 token 使用量信息
    """
    return response.get("usage", {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })
