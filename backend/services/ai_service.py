# -*- coding: utf-8 -*-
"""
AI 服务模块
支持多个大模型厂商，统一 OpenAI 兼容格式调用

支持的模型：
- 智谱 GLM-4-Flash（免费）、GLM-4-Plus、GLM-5、GLM-5.1
- 阿里百炼 通义千问 Qwen-Plus、Qwen-Max、Qwen-Turbo
- 可扩展更多 OpenAI 兼容的模型

所有厂商均使用 OpenAI API 兼容格式：
POST base_url/chat/completions
"""
import httpx
import json
import logging
import os
from config import settings

logger = logging.getLogger(__name__)

# ===== 模型注册表 =====
# 每个模型的配置：API 地址、环境变量名、是否免费
MODEL_REGISTRY = {
    # 智谱系列
    "glm-4-flash": {
        "name": "GLM-4-Flash",
        "provider": "zhipu",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "ZHIPU_API_KEY",
        "is_free": True,
        "description": "智谱免费模型，适合日常使用",
    },
    "glm-4-plus": {
        "name": "GLM-4-Plus",
        "provider": "zhipu",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "ZHIPU_API_KEY",
        "is_free": False,
        "description": "智谱高级模型，效果更好",
    },
    "glm-5": {
        "name": "GLM-5",
        "provider": "zhipu",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "ZHIPU_API_KEY",
        "is_free": False,
        "description": "智谱旗舰模型，推理和代码能力极强",
    },
    "glm-5.1": {
        "name": "GLM-5.1",
        "provider": "zhipu",
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "api_key_env": "ZHIPU_API_KEY",
        "is_free": False,
        "description": "智谱最新旗舰（2026.04），可对标 Claude Opus",
    },
    # 阿里百炼系列
    "qwen-turbo": {
        "name": "通义千问-Turbo",
        "provider": "dashscope",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "DASHSCOPE_API_KEY",
        "is_free": False,
        "description": "阿里云通义千问轻量版，速度快",
    },
    "qwen-plus": {
        "name": "通义千问-Plus",
        "provider": "dashscope",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "DASHSCOPE_API_KEY",
        "is_free": False,
        "description": "阿里云通义千问增强版，综合性能优秀",
    },
    "qwen-max": {
        "name": "通义千问-Max",
        "provider": "dashscope",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key_env": "DASHSCOPE_API_KEY",
        "is_free": False,
        "description": "阿里云通义千问旗舰，最强效果",
    },
}


def get_available_models() -> list[dict]:
    """
    获取当前已配置 API Key 的可用模型列表

    只返回在 .env 中配置了对应 API Key 的模型，
    避免前端展示不可用的选项。
    """
    available = []
    for model_id, info in MODEL_REGISTRY.items():
        api_key = os.getenv(info["api_key_env"], "")
        if api_key:
            available.append({
                "id": model_id,
                "name": info["name"],
                "provider": info["provider"],
                "is_free": info["is_free"],
                "description": info["description"],
            })
    return available


def _get_model_config(model_id: str) -> tuple[str, str]:
    """
    获取模型的 API URL 和 API Key

    Returns:
        (api_url, api_key) 元组
    """
    info = MODEL_REGISTRY.get(model_id)
    if not info:
        raise ValueError(f"不支持的模型: {model_id}")

    api_key = os.getenv(info["api_key_env"], "")
    if not api_key:
        raise ValueError(
            f"模型 {info['name']} 的 API Key 未配置，"
            f"请在 .env 中设置 {info['api_key_env']}"
        )

    return info["api_url"], api_key


async def call_ai_model(
    system_prompt: str,
    user_content: str,
    model_id: str = "glm-4-flash",
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> dict:
    """
    统一 AI 模型调用接口

    所有厂商均使用 OpenAI 兼容的 chat/completions 格式，
    只需切换 api_url 和 api_key 即可。

    Args:
        system_prompt: 系统提示词
        user_content: 用户输入
        model_id: 模型标识（registry 中的 key）
        max_tokens: 最大输出 token 数
        temperature: 随机性（排版场景建议 0.1）

    Returns:
        完整的 API 响应 dict
    """
    api_url, api_key = _get_model_config(model_id)

    logger.info(f"AI 调用 | 模型: {model_id} | 输入长度: {len(user_content)}")

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": model_id,
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
            f"AI 完成 | 模型: {model_id} | "
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
