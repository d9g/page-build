# -*- coding: utf-8 -*-
"""排版业务逻辑"""
import json
import re
import time
import logging
import httpx
from typing import Optional
from services.ai_service import call_glm4_flash, extract_content, extract_usage
from services.prompt_manager import prompt_manager
from services.html_sanitizer import build_html_from_sections
from config import settings

logger = logging.getLogger(__name__)

# 默认主题配置
DEFAULT_THEMES = {
    "default": {
        "id": "default",
        "name": "默认",
        "styles": {
            "title_color": "#333333",
            "title_font_size": 20,
            "body_color": "#3f3f3f",
            "body_font_size": 15,
            "line_height": 1.8,
            "accent_color": "#07C160",
            "bg_color": "#ffffff",
            "quote_color": "#f6f6f6",
            "quote_border_color": "#07C160",
            "divider_style": "dots",
        },
        "is_premium": False,
    },
    "warm": {
        "id": "warm",
        "name": "暖橙",
        "styles": {
            "title_color": "#2d2d2d",
            "body_color": "#4a4a4a",
            "accent_color": "#ff7f50",
            "quote_border_color": "#ff7f50",
        },
        "is_premium": False,
    },
    "blue": {
        "id": "blue",
        "name": "清蓝",
        "styles": {
            "title_color": "#1a1a2e",
            "body_color": "#333355",
            "accent_color": "#4a90d9",
            "quote_border_color": "#4a90d9",
        },
        "is_premium": False,
    },
}


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


def parse_ai_response(ai_text: str) -> list[dict]:
    """解析 AI 返回的 JSON"""
    text = ai_text.strip()
    
    # 去掉 markdown 代码块标记
    if text.startswith("```"):
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
    except json.JSONDecodeError as e:
        logger.warning(f"AI JSON 解析失败，尝试修复: {e}")
        
        # 方法：逐行构建 JSON 对象
        # AI 返回的是 JSON 数组，但内部可能有问题
        # 尝试提取每个 {...} 对象单独解析
        
        import re
        
        # 提取所有 JSON 对象
        pattern = r'\{[^{}]*"type"[^{}]*"content"[^{}]*\}'
        objects = re.findall(pattern, text, re.DOTALL)
        
        if not objects:
            # 尝试更宽松的匹配
            pattern2 = r'\{"type":\s*"[^"]+",\s*"content":\s*"[^"]*"\}'
            objects = re.findall(pattern2, text)
        
        sections = []
        for obj_text in objects:
            try:
                # 清理控制字符
                cleaned = obj_text.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
                obj = json.loads(cleaned)
                sections.append(obj)
            except:
                continue
        
        # 也尝试提取 divider 和 list 类型
        divider_pattern = r'\{"type":\s*"divider"\}'
        for obj_text in re.findall(divider_pattern, text):
            sections.append({"type": "divider"})
        
        list_pattern = r'\{"type":\s*"list",\s*"items":\s*\[[^\]]*\]\}'
        for obj_text in re.findall(list_pattern, text):
            try:
                obj = json.loads(obj_text)
                sections.append(obj)
            except:
                continue
        
        if sections:
            logger.info(f"JSON 修复成功，提取到 {len(sections)} 个区块")
            return sections
        
        logger.error(f"AI JSON 解析失败（无法修复）\n原文: {text[:500]}")
        raise ValueError("排版结果解析失败，请重试")


async def do_layout(content: str, theme_id: str = "default") -> dict:
    """执行排版"""
    start_time = time.time()

    content = clean_input(content)
    error = validate_input(content)
    if error:
        raise ValueError(error)

    # 加载 Prompt
    system_prompt, prompt_version = prompt_manager.get_system_prompt()
    user_prompt = prompt_manager.get_user_prompt(content)

    # 调用 AI
    logger.info(f"开始排版 | 字数: {len(content)} | Prompt: {prompt_version}")
    response = await call_glm4_flash(
        system_prompt=system_prompt,
        user_content=user_prompt,
    )

    ai_text = extract_content(response)
    usage = extract_usage(response)
    sections = parse_ai_response(ai_text)

    # 生成 HTML
    theme = DEFAULT_THEMES.get(theme_id, DEFAULT_THEMES["default"])
    html = build_html_from_sections(sections, theme)

    process_time_ms = int((time.time() - start_time) * 1000)
    process_time_str = f"{process_time_ms / 1000:.1f}s"

    logger.info(f"排版完成 | 区块数: {len(sections)} | 耗时: {process_time_str}")

    return {
        "sections": sections,
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
    return list(DEFAULT_THEMES.values())