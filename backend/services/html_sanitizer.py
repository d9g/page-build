# -*- coding: utf-8 -*-
"""
HTML 清洗模块
确保 HTML 100% 兼容微信公众号编辑器

v3.0 架构中，HTML 由 markdown_renderer.py 生成，
本模块只负责最终清洗和微信兼容性处理。

微信公众号编辑器限制严格：
- 只支持内联 style，不支持 class/id/外联 CSS
- 不支持 position/float 等布局属性
- 原生 <ul>/<ol> 列表样式会被破坏，需转为 flexbox section
- 不支持 animation/transition 等动画属性

借鉴 xiaohu-wechat-format 项目的微信兼容处理方案。
"""
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 微信公众号编辑器不支持的 CSS 属性
UNSUPPORTED_CSS_PROPERTIES = [
    "position", "float",
    "animation", "transition", "transform",
    "box-shadow", "text-shadow",
    "overflow", "z-index", "opacity",
]

# 允许保留的 HTML 属性
ALLOWED_ATTRS = {"style", "src", "href", "colspan", "rowspan"}


# ===== 微信兼容性文本处理 =====

def add_cjk_spacing(text: str) -> str:
    """
    中英文/数字间自动加空格

    规则：
    - 中文字符与英文字母/数字之间加空格
    - 不影响已有空格、HTML 标签内的属性
    """
    if not text:
        return text

    # 中文后接英文/数字
    text = re.sub(
        r'([\u4e00-\u9fff\u3400-\u4dbf])([A-Za-z0-9])',
        r'\1 \2', text,
    )
    # 英文/数字后接中文
    text = re.sub(
        r'([A-Za-z0-9])([\u4e00-\u9fff\u3400-\u4dbf])',
        r'\1 \2', text,
    )
    return text


def fix_bold_punctuation(text: str) -> str:
    """
    加粗标点修复

    微信编辑器中加粗的中文标点会显示异常，
    将 **文字，** 修正为 **文字**，
    """
    # 匹配 </strong> 前的中文标点，移到标签后面
    chinese_puncts = r'[，。！？；：、》）】」』）]'
    text = re.sub(
        rf'({chinese_puncts})(</strong>)',
        r'\2\1', text,
    )
    return text


# ===== HTML 清洗 =====

def sanitize_html_for_wechat(html: str) -> str:
    """
    清洗 HTML，确保兼容微信公众号编辑器

    处理逻辑：
    1. 移除不支持的标签（script/iframe/video 等）
    2. 移除 class、id 等不支持的属性
    3. 清除 style 中不支持的 CSS 属性
    4. 转换残余 <ul>/<ol> 为 flexbox section（安全兜底）
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # 移除危险标签和微信编辑器不支持的标签
    unsupported_tags = [
        "script", "iframe", "embed", "object", "link", "meta",
        "video", "audio", "canvas", "svg",
        "form", "input", "select", "textarea", "button",
        "style", "base", "noscript",
    ]
    for tag_name in unsupported_tags:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 兜底处理：如果 HTML 中残存 <ul>/<ol>，转为 flexbox
    _convert_lists_to_flexbox(soup)

    # 清洗每个标签的属性
    for tag in soup.find_all(True):
        # 只保留允许的属性
        attrs_to_keep = {}
        for attr_name, attr_value in tag.attrs.items():
            if attr_name in ALLOWED_ATTRS:
                attrs_to_keep[attr_name] = attr_value
        tag.attrs = attrs_to_keep

        # 清洗 style 中不支持的属性
        if tag.get("style"):
            tag["style"] = _clean_css(tag["style"])

    # 提取 body 内容（lxml 会自动添加 html/body 标签）
    body = soup.find("body")
    if body:
        return "".join(str(child) for child in body.children)
    return str(soup)


def _convert_lists_to_flexbox(soup: BeautifulSoup) -> None:
    """
    将 <ul>/<ol> 转换为 section + flexbox 布局（兜底处理）

    正常情况下 markdown_renderer 已经输出 flexbox 列表，
    此函数仅作为安全兜底。
    """
    for ul_tag in soup.find_all("ul"):
        wrapper = soup.new_tag("section")
        for li in ul_tag.find_all("li", recursive=False):
            row = soup.new_tag("section", style=(
                "display:flex;align-items:flex-start;margin-bottom:8px;"
            ))
            bullet = soup.new_tag("section", style=(
                "min-width:6px;width:6px;height:6px;"
                "border-radius:50%;background:#07C160;"
                "margin-right:12px;margin-top:8px;flex-shrink:0;"
            ))
            text_el = soup.new_tag("section", style="flex:1;line-height:1.7;")
            text_el.append(BeautifulSoup(li.decode_contents(), "lxml").body or "")
            row.append(bullet)
            row.append(text_el)
            wrapper.append(row)
        ul_tag.replace_with(wrapper)

    for ol_tag in soup.find_all("ol"):
        wrapper = soup.new_tag("section")
        for i, li in enumerate(ol_tag.find_all("li", recursive=False), 1):
            row = soup.new_tag("section", style=(
                "display:flex;align-items:flex-start;margin-bottom:8px;"
            ))
            num = soup.new_tag("section", style=(
                "min-width:22px;width:22px;height:22px;"
                "border-radius:50%;background:#f0f0f0;"
                "color:#07C160;font-size:12px;font-weight:bold;"
                "text-align:center;line-height:22px;"
                "margin-right:10px;margin-top:2px;flex-shrink:0;"
            ))
            num.string = str(i)
            text_el = soup.new_tag("section", style="flex:1;line-height:1.7;")
            text_el.append(BeautifulSoup(li.decode_contents(), "lxml").body or "")
            row.append(num)
            row.append(text_el)
            wrapper.append(row)
        ol_tag.replace_with(wrapper)


def _clean_css(style: str) -> str:
    """移除不支持的 CSS 属性"""
    for prop in UNSUPPORTED_CSS_PROPERTIES:
        style = re.sub(rf"{prop}\s*:[^;]*;?", "", style, flags=re.IGNORECASE)
    style = re.sub(r";\s*;", ";", style)
    style = re.sub(r"^\s*;\s*", "", style)
    return style.strip()
