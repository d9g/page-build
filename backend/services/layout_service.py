# -*- coding: utf-8 -*-
"""
排版业务逻辑
编排整个排版流程：输入校验 → Prompt 加载 → AI 调用 → 结果解析 → HTML 生成

主题系统：从 backend/themes/*.json 动态加载，运营无需改代码即可新增主题
"""
import json
import re
import time
import logging
import httpx
from pathlib import Path
from typing import Optional
from services.ai_service import call_glm4_flash, extract_content, extract_usage
from services.prompt_manager import prompt_manager
from services.html_sanitizer import build_html_from_sections
from config import settings

logger = logging.getLogger(__name__)


# ===== 主题管理（从 JSON 文件加载） =====

THEMES_DIR = Path(__file__).parent.parent / "themes"

# 主题缓存，启动时加载一次
_themes_cache: dict[str, dict] = {}


def load_all_themes() -> dict[str, dict]:
    """
    从 backend/themes/ 目录加载所有 JSON 主题文件

    每个 JSON 文件定义一个主题，文件名即主题 ID。
    借鉴 xiaohu-wechat-format 的方案，主题与代码完全解耦。
    """
    global _themes_cache
    if _themes_cache:
        return _themes_cache

    themes = {}
    if not THEMES_DIR.exists():
        logger.warning(f"主题目录不存在: {THEMES_DIR}")
        return themes

    for json_file in sorted(THEMES_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            theme_id = data.get("id", json_file.stem)
            themes[theme_id] = data
            logger.debug(f"加载主题: {theme_id} ({data.get('name', '')})")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"主题文件解析失败: {json_file.name} - {e}")

    logger.info(f"已加载 {len(themes)} 个主题")
    _themes_cache = themes
    return themes


def get_theme(theme_id: str) -> dict:
    """获取指定主题，不存在则返回 default"""
    themes = load_all_themes()
    return themes.get(theme_id, themes.get("default", {}))


def clean_input(content: str) -> str:
    """
    清理用户输入
    移除 HTML 标签和多余空白，保留纯文本
    """
    # 移除 HTML 标签
    content = re.sub(r"<[^>]+>", "", content)
    # 合并多余空行（保留段落结构）
    content = re.sub(r"\n{3,}", "\n\n", content)
    # 移除行首行尾空格
    content = "\n".join(line.strip() for line in content.split("\n"))
    return content.strip()


def validate_input(content: str) -> Optional[str]:
    """
    校验输入内容
    返回错误信息字符串，通过则返回 None
    """
    if not content:
        return "请输入文章内容"
    if len(content) < settings.MIN_INPUT_LENGTH:
        return f"内容过短，建议至少 {settings.MIN_INPUT_LENGTH} 字"
    if len(content) > settings.MAX_INPUT_LENGTH:
        return f"内容超出 {settings.MAX_INPUT_LENGTH} 字上限"
    return None


def parse_ai_response(ai_text: str) -> list[dict]:
    """
    解析 AI 返回的 JSON 数组

    AI 有时会在 JSON 前后添加 markdown 代码块标记，
    需要清理后再解析
    """
    # 移除 markdown 代码块标记
    text = ai_text.strip()
    if text.startswith("```"):
        # 移除首行（可能是 ```json）
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        sections = json.loads(text)
        if not isinstance(sections, list):
            raise ValueError("AI 返回的不是 JSON 数组")
        return sections
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"AI 返回的 JSON 解析失败: {e}\n原文: {text[:500]}")
        # 抛出异常而非静默降级，让前端提示用户重试
        raise ValueError("排版结果解析失败，请点击「重新排版」再试一次")


async def do_layout(
    content: str,
    theme_id: str = "default",
) -> dict:
    """
    执行排版流程

    返回包含 sections、html、统计信息的完整结果
    """
    start_time = time.time()

    # 1. 清理输入
    content = clean_input(content)
    error = validate_input(content)
    if error:
        raise ValueError(error)

    # 2. 内容安全检测（微信 msgSecCheck）
    await check_content_security(content)

    # 3. 加载 Prompt
    system_prompt, prompt_version = prompt_manager.get_system_prompt()
    user_prompt = prompt_manager.get_user_prompt(content)
    model_params = prompt_manager.get_model_params()

    # 4. 调用 AI
    logger.info(f"开始排版 | 字数: {len(content)} | Prompt: {prompt_version}")
    response = await call_glm4_flash(
        system_prompt=system_prompt,
        user_content=user_prompt,
        max_tokens=model_params.get("max_tokens", 4096),
        temperature=model_params.get("temperature", 0.3),
    )

    # 5. 解析结果
    ai_text = extract_content(response)
    usage = extract_usage(response)
    sections = parse_ai_response(ai_text)

    # 6. 生成 HTML
    theme = get_theme(theme_id)
    html = build_html_from_sections(sections, theme)

    # 7. 计算耗时
    process_time_ms = int((time.time() - start_time) * 1000)
    process_time_str = f"{process_time_ms / 1000:.1f}s"

    logger.info(
        f"排版完成 | 字数: {len(content)} | 区块数: {len(sections)} | "
        f"耗时: {process_time_str} | tokens: {usage.get('total_tokens', 0)}"
    )

    return {
        "sections": sections,
        "html": html,
        "suggested_theme": theme_id,
        "word_count": len(content),
        "process_time": process_time_str,
        "process_time_ms": process_time_ms,
        "prompt_version": prompt_version,
        "ai_model": model_params.get("model", "glm-4-flash"),
        "ai_tokens_used": usage.get("total_tokens", 0),
    }


async def check_content_security(content: str) -> None:
    """
    调用微信内容安全 API 检测用户输入
    防止违规内容经 AI 排版后发布到公众号

    NOTE: 需要小程序的 access_token，通过微信服务端 API 获取
    """
    if not settings.MINI_APP_ID or not settings.MINI_APP_SECRET:
        # 未配置小程序凭据时跳过检测（开发环境）
        logger.warning("⚠️ 内容安全检测未启用，建议配置 MINI_APP_ID/MINI_APP_SECRET")
        return

    try:
        # 获取 access_token
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": settings.MINI_APP_ID,
                    "secret": settings.MINI_APP_SECRET,
                },
            )
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            if not access_token:
                logger.warning(f"access_token 获取失败: {token_data}")
                return

            # 调用内容安全接口
            check_res = await client.post(
                f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={access_token}",
                json={
                    "version": 2,
                    "scene": 1,
                    "content": content[:5000],
                },
            )
            check_data = check_res.json()

            if check_data.get("errcode") == 0:
                result = check_data.get("result", {})
                if result.get("suggest") == "risky":
                    label = result.get("label", "未知")
                    logger.warning(f"内容安全检测不通过 | label={label}")
                    raise ValueError("输入内容包含违规信息，无法排版")
            else:
                # API 调用失败时不阻断主流程
                logger.warning(f"msgSecCheck 调用失败: {check_data}")
    except ValueError:
        raise
    except Exception as e:
        # 安全检测失败不应阻断主流程
        logger.warning(f"内容安全检测异常，跳过: {e}")


def get_all_themes() -> list[dict]:
    """获取所有主题配置"""
    return list(load_all_themes().values())
