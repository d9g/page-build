# -*- coding: utf-8 -*-
"""
排版业务逻辑

架构 v3.0：AI 返回 Markdown → mistune 渲染器 → 主题化内联样式 HTML

主题系统：从 backend/themes/*.json 动态加载，运营无需改代码即可新增主题
"""
import json
import re
import time
import logging
from pathlib import Path
from typing import Optional
from services.ai_service import call_glm4_flash, extract_content, extract_usage
from services.prompt_manager import prompt_manager
from services.markdown_renderer import render_markdown_to_html
from services.html_sanitizer import sanitize_html_for_wechat
from config import settings

logger = logging.getLogger(__name__)


# ===== 主题管理（从 JSON 文件加载） =====

THEMES_DIR = Path(__file__).parent.parent / "themes"
_themes_cache: dict[str, dict] = {}


def load_all_themes() -> dict[str, dict]:
    """
    从 backend/themes/ 目录加载所有 JSON 主题文件

    每个 JSON 文件定义一个主题，文件名即主题 ID。
    启动后缓存在内存中，重启服务刷新。
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


# ===== 核心排版流程 =====

def clean_markdown_output(ai_text: str) -> str:
    """
    清理 AI 返回的 Markdown 文本

    AI 有时会在输出前后加上 ```markdown 代码块标记，
    需要去掉这些不需要的包裹。
    """
    text = ai_text.strip()

    # 去掉 ```markdown ... ``` 包裹
    if text.startswith("```"):
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


async def do_layout(content: str, theme_id: str = "default") -> dict:
    """
    执行排版（v3.0 Markdown 架构）

    流程：
    1. 清理用户输入
    2. 调用 AI 将纯文本转为 Markdown
    3. 用 mistune + WechatRenderer 将 Markdown 转为主题化 HTML
    4. 微信兼容性清洗
    5. 返回结果
    """
    start_time = time.time()

    content = clean_input(content)
    error = validate_input(content)
    if error:
        raise ValueError(error)

    # 加载 Prompt
    system_prompt, prompt_version = prompt_manager.get_system_prompt()
    user_prompt = prompt_manager.get_user_prompt(content)

    # 调用 AI（返回 Markdown）
    logger.info(f"开始排版 | 字数: {len(content)} | Prompt: {prompt_version}")
    response = await call_glm4_flash(
        system_prompt=system_prompt,
        user_content=user_prompt,
    )

    ai_text = extract_content(response)
    usage = extract_usage(response)

    # 清理 AI 输出的 Markdown
    markdown_text = clean_markdown_output(ai_text)

    # 加载主题 + 渲染 Markdown → HTML
    theme = get_theme(theme_id)
    html = render_markdown_to_html(markdown_text, theme)

    # 微信兼容性最终清洗
    html = sanitize_html_for_wechat(html)

    process_time_ms = int((time.time() - start_time) * 1000)
    process_time_str = f"{process_time_ms / 1000:.1f}s"

    logger.info(f"排版完成 | 耗时: {process_time_str} | Markdown 长度: {len(markdown_text)}")

    return {
        "sections": [],  # v3.0 不再返回 JSON sections，前端不依赖此字段
        "html": html,
        "suggested_theme": theme_id,
        "word_count": len(content),
        "process_time": process_time_str,
        "process_time_ms": process_time_ms,
        "prompt_version": prompt_version,
        "ai_model": "glm-4-flash",
        "ai_tokens_used": usage.get("total_tokens", 0),
    }


def get_all_themes() -> list[dict]:
    """获取所有主题"""
    return list(load_all_themes().values())