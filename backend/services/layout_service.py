# -*- coding: utf-8 -*-
"""
排版业务逻辑 v4.0

双模式：
- do_quick_layout(): 快速排版，纯本地 Markdown → HTML
- do_layout():       智能排版，AI 润色 → Markdown → HTML
"""
import json
import re
import time
import logging
from pathlib import Path
from typing import Optional
from services.ai_service import call_ai_model, extract_content, extract_usage
from services.prompt_manager import prompt_manager
from services.markdown_renderer import render_markdown_to_html
from services.html_sanitizer import sanitize_html_for_wechat
from config import settings

logger = logging.getLogger(__name__)


# ===== 主题管理 =====

THEMES_DIR = Path(__file__).parent.parent / "themes"
_themes_cache: dict[str, dict] = {}


def load_all_themes() -> dict[str, dict]:
    """从 backend/themes/ 加载所有 JSON 主题"""
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
    """获取指定主题，不存在则返回暖棕书卷（默认）"""
    themes = load_all_themes()
    return themes.get(theme_id, themes.get("shujuan", {}))


def get_all_themes() -> list[dict]:
    """获取所有主题列表"""
    return list(load_all_themes().values())


# ===== 输入处理 =====

def clean_input(content: str) -> str:
    """清理用户输入"""
    content = re.sub(r"<[^>]+>", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = "\n".join(line.strip() for line in content.split("\n"))
    return content.strip()


def validate_input(content: str) -> Optional[str]:
    """校验输入"""
    if not content:
        return "请输入文章内容"
    if len(content) < settings.MIN_INPUT_LENGTH:
        return f"内容过短，建议至少 {settings.MIN_INPUT_LENGTH} 字"
    if len(content) > settings.MAX_INPUT_LENGTH:
        return f"内容超出 {settings.MAX_INPUT_LENGTH} 字上限"
    return None


def clean_markdown_output(ai_text: str) -> str:
    """清理 AI 返回的 Markdown（去掉 ```markdown 包裹）"""
    text = ai_text.strip()
    if text.startswith("```"):
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# ===== 快速排版（不调 AI） =====

def do_quick_layout(content: str, theme_id: str = "shujuan") -> dict:
    """
    快速排版 — 纯本地渲染

    直接将用户输入当 Markdown 解析，用预设主题渲染。
    不消耗 API 额度，毫秒级响应。
    """
    start_time = time.time()

    content = clean_input(content)
    error = validate_input(content)
    if error:
        raise ValueError(error)

    theme = get_theme(theme_id)
    html = render_markdown_to_html(content, theme)
    html = sanitize_html_for_wechat(html)

    process_time_ms = int((time.time() - start_time) * 1000)
    logger.info(f"快速排版完成 | 字数: {len(content)} | 主题: {theme_id} | {process_time_ms}ms")

    return {
        "sections": [],
        "html": html,
        "suggested_theme": theme_id,
        "word_count": len(content),
        "process_time": f"{process_time_ms}ms",
        "process_time_ms": process_time_ms,
        "mode": "quick",
    }


# ===== 智能排版（调 AI） =====

async def do_layout(content: str, theme_id: str = "shujuan") -> dict:
    """
    智能排版 — AI 润色 + 本地渲染

    AI 自动识别文本结构 → 转 Markdown → 预设主题渲染。
    """
    start_time = time.time()

    content = clean_input(content)
    error = validate_input(content)
    if error:
        raise ValueError(error)

    provider = settings.AI_PROVIDER
    model = settings.AI_MODEL

    system_prompt, prompt_version = prompt_manager.get_system_prompt()
    user_prompt = prompt_manager.get_user_prompt(content)

    logger.info(f"智能排版开始 | 字数: {len(content)} | {provider}/{model}")
    response = await call_ai_model(
        system_prompt=system_prompt,
        user_content=user_prompt,
        model=model,
        provider=provider,
    )

    ai_text = extract_content(response)
    usage = extract_usage(response)
    markdown_text = clean_markdown_output(ai_text)

    theme = get_theme(theme_id)
    html = render_markdown_to_html(markdown_text, theme)
    html = sanitize_html_for_wechat(html)

    process_time_ms = int((time.time() - start_time) * 1000)
    process_time_str = f"{process_time_ms / 1000:.1f}s"

    logger.info(f"智能排版完成 | 耗时: {process_time_str} | {provider}/{model}")

    return {
        "sections": [],
        "html": html,
        "suggested_theme": theme_id,
        "word_count": len(content),
        "process_time": process_time_str,
        "process_time_ms": process_time_ms,
        "prompt_version": prompt_version,
        "ai_model": f"{provider}/{model}",
        "ai_tokens_used": usage.get("total_tokens", 0),
        "mode": "ai",
    }