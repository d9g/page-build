# -*- coding: utf-8 -*-
"""
HTML 清洗与生成模块
确保 AI 生成的 HTML 100% 兼容微信公众号编辑器

微信公众号编辑器限制严格：
- 只支持内联 style，不支持 class/id/外联 CSS
- 不支持 position/float 等布局属性
- 原生 <ul>/<ol> 列表样式会被破坏，需转为 flexbox section
- 不支持 animation/transition 等动画属性

借鉴 xiaohu-wechat-format 项目的微信兼容处理方案：
- CJK 自动间距（中英文/数字间加空格）
- 列表渲染使用 section + flexbox（而非 <ul>/<ol>）
- 加粗标点修复（中文标点移到 <strong> 外部）
"""
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 微信公众号编辑器不支持的 CSS 属性
UNSUPPORTED_CSS_PROPERTIES = [
    "position", "float", "display", "flex", "grid",
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
    4. 转换 <ul>/<ol> 为 flexbox section（微信会破坏原生列表）
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

    # 微信会破坏原生列表，转为 flexbox section
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
    将 <ul>/<ol> 转换为 section + flexbox 布局

    微信公众号编辑器会破坏原生列表的缩进和样式，
    借鉴 xiaohu-wechat-format 的方案，改用 section 模拟列表
    """
    # 处理无序列表
    for ul_tag in soup.find_all("ul"):
        wrapper = soup.new_tag("section")
        for i, li in enumerate(ul_tag.find_all("li", recursive=False)):
            row = soup.new_tag("section", style=(
                "display:flex;align-items:flex-start;"
                "margin-bottom:8px;"
            ))
            # 圆点标记
            bullet = soup.new_tag("section", style=(
                "min-width:8px;width:8px;height:8px;"
                "border-radius:50%;background:#07C160;"
                "margin-right:10px;margin-top:7px;flex-shrink:0;"
            ))
            text_el = soup.new_tag("section", style=(
                "flex:1;line-height:1.7;"
            ))
            text_el.append(BeautifulSoup(li.decode_contents(), "lxml").body or "")
            row.append(bullet)
            row.append(text_el)
            wrapper.append(row)
        ul_tag.replace_with(wrapper)

    # 处理有序列表
    for ol_tag in soup.find_all("ol"):
        wrapper = soup.new_tag("section")
        for i, li in enumerate(ol_tag.find_all("li", recursive=False), 1):
            row = soup.new_tag("section", style=(
                "display:flex;align-items:flex-start;"
                "margin-bottom:8px;"
            ))
            # 数字序号
            num = soup.new_tag("section", style=(
                "display:inline-flex;align-items:center;"
                "justify-content:center;width:22px;height:22px;"
                "min-width:22px;border-radius:50%;background:#f0f0f0;"
                "color:#07C160;font-size:13px;font-weight:bold;"
                "margin-right:10px;margin-top:2px;flex-shrink:0;"
            ))
            num.string = str(i)
            text_el = soup.new_tag("section", style=(
                "flex:1;line-height:1.7;"
            ))
            text_el.append(BeautifulSoup(li.decode_contents(), "lxml").body or "")
            row.append(num)
            row.append(text_el)
            wrapper.append(row)
        ol_tag.replace_with(wrapper)


def _clean_css(style: str) -> str:
    """移除不支持的 CSS 属性"""
    for prop in UNSUPPORTED_CSS_PROPERTIES:
        # 匹配属性名及其值（到分号或字符串结尾）
        style = re.sub(rf"{prop}\s*:[^;]*;?", "", style, flags=re.IGNORECASE)
    # 清理多余空格和分号
    style = re.sub(r";\s*;", ";", style)
    style = re.sub(r"^\s*;\s*", "", style)
    return style.strip()


# ===== HTML 生成 =====

def build_html_from_sections(
    sections: list[dict],
    theme: dict,
) -> str:
    """
    根据结构化的 sections 和主题样式生成 HTML

    支持的 section type:
    - title: 主标题 (h1)
    - subtitle: 副标题 (h2)
    - paragraph: 正文段落 (p)
    - quote: 引用块 (blockquote)
    - divider: 分隔线
    - list: 列表（使用 flexbox section，微信兼容）
    - callout: 高亮提示框
    - dialogue: 对话气泡
    """
    html_parts = []
    styles = theme.get("styles", {})

    # 提取主题参数（带默认值）
    title_color = styles.get("title_color", "#333333")
    title_font_size = styles.get("title_font_size", 20)
    body_color = styles.get("body_color", "#3f3f3f")
    body_font_size = styles.get("body_font_size", 15)
    line_height = styles.get("line_height", 1.8)
    accent_color = styles.get("accent_color", "#07C160")
    bg_color = styles.get("bg_color", "#ffffff")
    quote_color = styles.get("quote_color", "#f6f6f6")
    quote_border_color = styles.get("quote_border_color", "#07C160")
    divider_style = styles.get("divider_style", "dots")

    for section in sections:
        section_type = section.get("type", "paragraph")
        content = section.get("content", "")

        # 文本处理管线：CJK 间距 → 加粗标点修复
        if content:
            content = add_cjk_spacing(content)
            content = fix_bold_punctuation(content)

        # 处理关键词加粗
        highlights = section.get("highlights", [])
        if highlights and content:
            for keyword in highlights:
                content = content.replace(
                    keyword,
                    f'<strong style="color:{accent_color}">{keyword}</strong>',
                )

        if section_type == "title":
            html_parts.append(
                f'<h1 style="color:{title_color};font-size:{title_font_size}px;'
                f'font-weight:bold;text-align:center;margin:24px 0 16px;'
                f'line-height:1.4;">{content}</h1>'
            )

        elif section_type == "subtitle":
            html_parts.append(
                f'<h2 style="color:{title_color};font-size:{body_font_size + 2}px;'
                f'font-weight:bold;margin:20px 0 12px;padding-left:10px;'
                f'border-left:3px solid {accent_color};">{content}</h2>'
            )

        elif section_type == "paragraph":
            html_parts.append(
                f'<p style="color:{body_color};font-size:{body_font_size}px;'
                f'line-height:{line_height};margin-bottom:16px;'
                f'text-indent:2em;">{content}</p>'
            )

        elif section_type == "quote":
            html_parts.append(
                f'<blockquote style="background:{quote_color};'
                f'border-left:3px solid {quote_border_color};'
                f'padding:12px 16px;margin:16px 0;border-radius:4px;">'
                f'<p style="color:#666;font-size:{body_font_size - 1}px;'
                f'margin:0;line-height:{line_height};">{content}</p>'
                f'</blockquote>'
            )

        elif section_type == "divider":
            divider_text = "· · ·" if divider_style == "dots" else "———"
            html_parts.append(
                f'<p style="text-align:center;color:#ccc;margin:24px 0;'
                f'letter-spacing:8px;">{divider_text}</p>'
            )

        elif section_type == "list":
            # 使用 flexbox section 替代原生 <ul>，微信兼容
            items = section.get("items", [])
            if items:
                li_parts = []
                for item in items:
                    item = add_cjk_spacing(item)
                    li_parts.append(
                        f'<section style="display:flex;align-items:flex-start;margin-bottom:8px;">'
                        f'<section style="min-width:8px;width:8px;height:8px;'
                        f'border-radius:50%;background:{accent_color};'
                        f'margin-right:10px;margin-top:7px;flex-shrink:0;"></section>'
                        f'<section style="flex:1;color:{body_color};'
                        f'font-size:{body_font_size}px;line-height:{line_height};">'
                        f'{item}</section></section>'
                    )
                html_parts.append(
                    f'<section style="margin:12px 0;">{"".join(li_parts)}</section>'
                )

        elif section_type == "callout":
            # 高亮提示框（借鉴 xiaohu-wechat-format 的 callout 组件）
            callout_title = section.get("title", "")
            html_parts.append(
                f'<section style="background:{quote_color};'
                f'border-left:3px solid {accent_color};'
                f'padding:16px;margin:16px 0;border-radius:4px;">'
                f'<p style="font-weight:bold;color:{accent_color};'
                f'font-size:{body_font_size}px;margin:0 0 8px 0;">'
                f'{callout_title}</p>'
                f'<p style="color:{body_color};font-size:{body_font_size - 1}px;'
                f'line-height:{line_height};margin:0;">'
                f'{content}</p></section>'
            )

        elif section_type == "dialogue":
            # 对话气泡（适用于访谈/采访类文章）
            speaker = section.get("speaker", "")
            # 偶数行靠左，奇数行靠右（简化处理）
            html_parts.append(
                f'<section style="margin:8px 0;">'
                f'<section style="display:flex;align-items:flex-start;gap:8px;">'
                f'<section style="min-width:60px;font-size:{body_font_size - 1}px;'
                f'color:{accent_color};font-weight:bold;line-height:{line_height};">'
                f'{speaker}</section>'
                f'<section style="flex:1;background:{quote_color};'
                f'border-radius:8px;padding:10px 14px;'
                f'font-size:{body_font_size}px;color:{body_color};'
                f'line-height:{line_height};">{content}</section>'
                f'</section></section>'
            )

    full_html = "\n".join(html_parts)
    # 最终清洗，确保微信兼容
    return sanitize_html_for_wechat(full_html)
