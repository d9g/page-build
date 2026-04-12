# -*- coding: utf-8 -*-
"""
排版业务逻辑

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
_themes_cache: dict[str, dict] = {}


def load_all_themes() -> dict[str, dict]:
    """
    从 backend/themes/ 目录加载所有 JSON 主题文件

    每个 JSON 文件定义一个主题，文件名即主题 ID。
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
        # 找到第一个换行后的内容
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # 第一尝试：直接解析
    try:
        sections = json.loads(text)
        if isinstance(sections, list):
            return sections
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 直接解析失败: {e}")
    
    # 第二尝试：逐个解析（提取每个完整的 JSON 对象）
    import re
    
    # 用更精确的正则：匹配完整的 {...} 对象
    # 包括嵌套的内容如 "items": [...]
    sections = []
    
    # 简化处理：将整个字符串中的控制字符替换掉
    # 在 JSON 字符串值内部，换行符需要转义
    fixed_text = text
    
    # 方法：逐字符扫描，在字符串值内部转义控制字符
    result = []
    in_string = False
    escape_next = False
    
    for char in fixed_text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        
        if char == '\\' and in_string:
            result.append(char)
            escape_next = True
            continue
        
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        
        if in_string:
            # 在字符串内部，转义控制字符
            if char == '\n':
                result.append(' ')
            elif char == '\t':
                result.append(' ')
            elif char == '\r':
                result.append('')
            else:
                result.append(char)
        else:
            result.append(char)
    
    fixed_text = ''.join(result)
    
    try:
        sections = json.loads(fixed_text)
        if isinstance(sections, list):
            logger.info(f"JSON 修复成功 | 区块数: {len(sections)}")
            return sections
    except json.JSONDecodeError as e2:
        logger.error(f"JSON 解析最终失败: {e2}")
    
    # 第三尝试：正则提取（最后的手段）
    # 匹配简单对象 {"type":"xxx","content":"..."}
    pattern = r'\{"type"\s*:\s*"[^"]+"\s*,\s*"content"\s*:\s*"[^"]*"\s*\}'
    matches = re.findall(pattern, fixed_text, re.IGNORECASE)
    
    for match in matches:
        try:
            obj = json.loads(match)
            sections.append(obj)
        except:
            continue
    
    if sections:
        logger.info(f"正则提取成功 | 区块数: {len(sections)}")
        return sections
    
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
    theme = get_theme(theme_id)
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
    return list(load_all_themes().values())