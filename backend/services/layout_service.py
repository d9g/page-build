# -*- coding: utf-8 -*-
"""
排版业务逻辑 v4.0

双模式：
- do_quick_layout(): 快速排版，纯本地 Markdown → HTML
- do_layout():       智能排版，AI 润色 → Markdown → HTML
"""
import json
import os
import re
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional
from services.ai_service import call_ai_model, extract_content, extract_usage
from services.prompt_manager import prompt_manager
from services.markdown_renderer import render_markdown_to_html
from services.html_sanitizer import sanitize_html_for_wechat
from services.markdown_post_processor import process_markdown
from config import settings

logger = logging.getLogger(__name__)


# ===== 主题管理 =====

THEMES_DIR = Path(__file__).parent.parent / "themes"
_themes_cache: dict[str, dict] = {}
_themes_cache_mtime: float = 0  # 主题目录最后修改时间


def _get_themes_dir_mtime() -> float:
    """获取主题目录中最新的文件修改时间"""
    if not THEMES_DIR.exists():
        return 0
    mtimes = [0.0]
    for f in THEMES_DIR.glob("*.json"):
        try:
            mtimes.append(os.path.getmtime(f))
        except OSError:
            pass
    return max(mtimes)


def load_all_themes() -> dict[str, dict]:
    """从 backend/themes/ 加载所有 JSON 主题（文件变更时自动刷新缓存）"""
    global _themes_cache, _themes_cache_mtime

    # 检查主题文件是否有更新
    current_mtime = _get_themes_dir_mtime()
    if _themes_cache and current_mtime == _themes_cache_mtime:
        return _themes_cache

    # 缓存失效，重新加载
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
    _themes_cache_mtime = current_mtime
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
    text = text.strip()

    # 检测并清理大量重复引号序列（glm-4-flash 模型退化问题）
    # 连续6个以上引号视为垃圾内容
    if re.search(r'"{6,}', text):
        # 替换连续引号序列为空格，保留正常短引用
        text = re.sub(r'"{6,}', ' ', text)
        logger.warning(f"检测到 AI 返回的引号序列，已清理")

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
    try:
        response = await asyncio.wait_for(
            call_ai_model(
                system_prompt=system_prompt,
                user_content=user_prompt,
                model=model,
                provider=provider,
            ),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        logger.error("AI 排版超时（120秒）")
        raise RuntimeError("排版超时，请稍后重试或缩短文章内容")

    ai_text = extract_content(response)
    usage = extract_usage(response)

    # 保存调试日志
    _save_debug_log(content, ai_text, "01_ai_raw")

    markdown_text = clean_markdown_output(ai_text)

    # 内容质量检查：清理后字数少于输入的 20% 视为 AI 生成失败
    if len(markdown_text) < len(content) * 0.2:
        logger.warning(
            f"AI 返回内容过短（{len(markdown_text)} < {int(len(content) * 0.2)}），“"
            f"可能是 glm-4-flash 模型退化导致，请稍后重试"
        )
        raise RuntimeError(
            f"生成内容异常（字数过少），请稍后重试"
        )

    # Markdown 后处理（保留原文内容，只清理格式）
    markdown_text = process_markdown(markdown_text, preserve_content=True)

    # 保存后处理结果
    _save_debug_log(content, markdown_text, "02_processed")

    theme = get_theme(theme_id)
    html = render_markdown_to_html(markdown_text, theme)
    html = sanitize_html_for_wechat(html)

    # 保存最终 HTML
    _save_debug_log(content, html, "03_final_html")

    process_time_ms = int((time.time() - start_time) * 1000)
    process_time_str = f"{process_time_ms / 1000:.1f}s"

    logger.info(f"智能排版完成 | 耗时: {process_time_str} | {provider}/{model}")

    return {
        "sections": [],
        "html": html,
        "markdown": markdown_text,
        "suggested_theme": theme_id,
        "word_count": len(content),
        "process_time": process_time_str,
        "process_time_ms": process_time_ms,
        "prompt_version": prompt_version,
        "ai_model": f"{provider}/{model}",
        "ai_tokens_used": usage.get("total_tokens", 0),
        "mode": "ai",
    }


DEBUG_LOG_DIR = Path("/tmp/page-build-debug")
DEBUG_LOG_MAX_AGE_HOURS = 24  # 调试日志保留 24 小时


def _cleanup_debug_logs():
    """清理过期的调试日志文件"""
    try:
        if not DEBUG_LOG_DIR.exists():
            return
        import time as _time
        cutoff = _time.time() - DEBUG_LOG_MAX_AGE_HOURS * 3600
        cleaned = 0
        for f in DEBUG_LOG_DIR.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                cleaned += 1
        if cleaned:
            logger.info(f"清理调试日志: {cleaned} 个文件")
    except Exception as e:
        logger.warning(f"清理调试日志失败: {e}")


def _save_debug_log(original: str, content: str, stage: str):
    """保存调试日志到本地文件（调试用，自动清理过期文件）"""
    try:
        DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{stage}.md"
        filepath = DEBUG_LOG_DIR / filename
        header = f"<!-- Stage: {stage} | Original length: {len(original)} | Content length: {len(content)} -->\n\n"
        filepath.write_text(header + content, encoding="utf-8")
        # 每次保存时顺便清理旧日志
        _cleanup_debug_logs()
    except Exception as e:
        logger.warning(f"保存调试日志失败: {e}")