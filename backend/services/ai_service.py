# -*- coding: utf-8 -*-
"""
AI 服务模块
支持多厂商多模型，按 provider + model 路由调用

设计思路：
- provider 决定用哪个 API 地址和 Key
- model 决定调哪个模型
- 同一个模型（如 glm-5）可能同时出现在多个平台上
"""
import httpx
import json
import logging
import os
from config import settings

logger = logging.getLogger(__name__)

# ===== 厂商注册表 =====
# 每个厂商：API 地址 + .env 中的 Key 名
PROVIDER_REGISTRY = {
    "zhipu": {
        "name": "智谱 AI",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "ZHIPU_API_KEY",
    },
    "dashscope": {
        "name": "阿里百炼",
        # Coding Plan 专属 Base URL（sk-sp-xxxxx Key 必须用这个）
        # 通用按量付费 URL：https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
        "api_url": "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
        "api_key_env": "DASHSCOPE_API_KEY",
    },
}

# 默认厂商（未指定 provider 时使用）
DEFAULT_PROVIDER = "zhipu"
# 默认模型
DEFAULT_MODEL = "glm-4-flash"


def get_available_providers() -> list[dict]:
    """
    获取当前已配置 API Key 的可用厂商列表

    只返回在 .env 中配置了 Key 的厂商。
    """
    available = []
    for provider_id, info in PROVIDER_REGISTRY.items():
        api_key = os.getenv(info["api_key_env"], "")
        if api_key:
            available.append({
                "id": provider_id,
                "name": info["name"],
            })
    return available


def _get_provider_config(provider_id: str) -> tuple[str, str]:
    """
    获取厂商的 API URL 和 API Key

    Returns:
        (api_url, api_key) 元组
    """
    info = PROVIDER_REGISTRY.get(provider_id)
    if not info:
        raise ValueError(f"不支持的厂商: {provider_id}")

    api_key = os.getenv(info["api_key_env"], "")
    if not api_key:
        raise ValueError(
            f"厂商 {info['name']} 的 API Key 未配置，"
            f"请在 .env 中设置 {info['api_key_env']}"
        )

    return info["api_url"], api_key


async def call_ai_model(
    system_prompt: str,
    user_content: str,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> dict:
    """
    统一 AI 模型调用接口

    Args:
        system_prompt: 系统提示词
        user_content: 用户输入
        model: 模型名称（如 glm-4-flash, glm-5, qwen-max）
        provider: 厂商 ID（zhipu / dashscope）
        max_tokens: 最大输出 token 数
        temperature: 随机性（排版场景建议 0.1）

    Returns:
        完整的 API 响应 dict
    """
    api_url, api_key = _get_provider_config(provider)

    logger.info(f"AI 调用 | 厂商: {provider} | 模型: {model} | 输入长度: {len(user_content)}")

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": model,
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
            f"AI 完成 | {provider}/{model} | "
            f"输入: {usage.get('prompt_tokens', 0)} | "
            f"输出: {usage.get('completion_tokens', 0)} | "
            f"总计: {usage.get('total_tokens', 0)}"
        )

        return result


def extract_content(response: dict) -> str:
    """从 API 响应中提取生成的文本内容"""
    choices = response.get("choices", [])
    if not choices:
        raise ValueError("AI 返回结果为空")
    return choices[0].get("message", {}).get("content", "")


def extract_usage(response: dict) -> dict:
    """从 API 响应中提取 token 使用量信息"""
    return response.get("usage", {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })
