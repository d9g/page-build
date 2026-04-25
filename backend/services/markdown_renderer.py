# -*- coding: utf-8 -*-
"""
微信公众号 Markdown 渲染器 v4.0

基于 PRESETS 预设系统，将 Markdown 转为微信兼容的内联样式 HTML。
每个元素的样式由主题 JSON 中的 preset ID 决定，不再硬编码。
"""
import re
import mistune
import logging
from services.presets import PRESETS, FONT_FAMILIES, get_preset, resolve_style
from services.html_sanitizer import add_cjk_spacing, fix_bold_punctuation

logger = logging.getLogger(__name__)

# NOTE: 中文数字映射，供有序列表 chinese 格式使用
_CHINESE_NUMS = "零一二三四五六七八九十"
# NOTE: 圆圈数字映射，供有序列表 circled 格式使用
_CIRCLED_NUMS = "⓪①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def _format_ol_number(n: int, fmt: str) -> str:
    """格式化有序列表序号"""
    if fmt == "circled":
        return _CIRCLED_NUMS[n] if n < len(_CIRCLED_NUMS) else f"{n}"
    if fmt == "chinese":
        return _CHINESE_NUMS[n] if n <= 10 else f"{n}"
    if fmt == "square":
        return str(n)
    return fmt.replace("{n}", str(n))


class WechatRenderer(mistune.HTMLRenderer):
    """
    微信公众号专用渲染器 v4.0

    通过 PRESETS 预设系统，每个元素根据主题配置的 preset ID
    查找对应样式模板，替换占位符后生成内联样式 HTML。
    """

    def __init__(self, theme: dict):
        super().__init__()
        self._theme = theme
        self._global = theme.get("global", {})
        self._brand = self._global.get("brand", "#333333")
        self._brand_soft = self._global.get("brandSoft", "#f0f0f0")
        self._ink = self._global.get("ink", "#333333")
        self._list_item_index = 0
        self._in_ordered_list = False

    def _cfg(self, element: str) -> dict:
        """获取某个元素的主题配置"""
        return self._theme.get(element, {})

    def _resolve(self, element: str) -> str:
        """获取元素的完整解析后样式字符串"""
        cfg = self._cfg(element)
        preset_id = cfg.get("preset", "plain")
        preset = get_preset(element, preset_id)
        style_tpl = preset.get("style", "")
        return resolve_style(style_tpl, cfg, self._global)

    # ===== 块级元素 =====

    def heading(self, text: str, level: int, **attrs) -> str:
        """标题渲染 — 根据 h1/h2/h3/h4 的 preset 渲染"""
        text = add_cjk_spacing(text)
        element = f"h{level}" if level <= 4 else "h4"
        cfg = self._cfg(element)
        preset_id = cfg.get("preset", "plain")
        preset = get_preset(element, preset_id)
        style = resolve_style(preset.get("style", ""), cfg, self._global)

        # 处理前缀/后缀装饰
        prefix = preset.get("prefix", "")
        suffix = preset.get("suffix", "")
        inner = f"{prefix}{text}{suffix}"

        tag = f"h{level}" if level <= 4 else "h4"
        return f'<{tag} style="{style}">{inner}</{tag}>\n'

    def paragraph(self, text: str) -> str:
        """正文段落"""
        # 检测 ASCII 树状结构
        if re.search(r'[├└│┌┐┘┬┴┼─]+|\|.*--', text):
            return self._render_ascii_block(text)

        text = add_cjk_spacing(text)
        text = fix_bold_punctuation(text)

        style = self._resolve("p")
        return f'<p style="{style}">{text}</p>\n'

    def _render_ascii_block(self, text: str) -> str:
        """ASCII 树状结构渲染为等宽代码块"""
        pre_style = self._resolve("pre") or (
            "background:#F6F4EF;padding:14px 16px;border-radius:8px;"
            "font-size:13px;line-height:1.7;white-space:pre-wrap;"
            "word-break:break-word;font-family:Consolas,monospace;margin:16px 0;"
        )
        return (
            f'<section style="{pre_style}">'
            f'<pre style="margin:0;font-family:Consolas,monospace;'
            f'font-size:13px;color:{self._ink};line-height:1.6;'
            f'white-space:pre-wrap;word-break:break-word;">'
            f'{text}</pre></section>\n'
        )

    def block_quote(self, text: str) -> str:
        """引用块"""
        style = self._resolve("blockquote")
        # 去掉内层 <p> 的 text-indent（引用内不需要缩进）
        inner = text.replace("text-indent:2em;", "text-indent:0;")
        return f'<section style="{style}">{inner}</section>\n'

    def thematic_break(self) -> str:
        """分割线 ---"""
        cfg = self._cfg("hr")
        preset_id = cfg.get("preset", "thin")
        preset = get_preset("hr", preset_id)
        style = resolve_style(preset.get("style", ""), cfg, self._global)
        decorative = preset.get("decorative", "")

        if decorative:
            return f'<section style="{style}">{decorative}</section>\n'
        return f'<hr style="{style}" />\n'

    def list(self, text: str, ordered: bool, **attrs) -> str:
        """列表容器 — 用 section 替代原生 ul/ol"""
        self._in_ordered_list = ordered
        self._list_item_index = 0
        return f'<section style="margin:16px 0;padding-left:4px;">{text}</section>\n'

    def list_item(self, text: str, **attrs) -> str:
        """列表项 — flexbox 布局"""
        self._list_item_index += 1
        p_cfg = self._cfg("p")
        size = p_cfg.get("fontSize", 16)
        lh = p_cfg.get("lineHeight", 1.75)

        # 去掉内层 <p> 标签
        inner = text.strip()
        m = re.match(r'<p[^>]*>(.*)</p>', inner, re.DOTALL)
        if m:
            inner = m.group(1)
        inner = add_cjk_spacing(inner)

        if self._in_ordered_list:
            return self._render_ol_item(inner, size, lh)
        return self._render_ul_item(inner, size, lh)

    def _render_ul_item(self, inner: str, size: int, lh: float) -> str:
        """无序列表项"""
        cfg = self._cfg("ul")
        color = cfg.get("color", self._brand)
        preset_id = cfg.get("preset", "disc")
        preset = get_preset("ul", preset_id)
        marker = preset.get("marker", "●")

        return (
            f'<section style="display:flex;align-items:flex-start;margin-bottom:10px;">'
            f'<section style="min-width:18px;color:{color};font-size:14px;'
            f'line-height:{size * lh}px;flex-shrink:0;margin-right:8px;">'
            f'{marker}</section>'
            f'<section style="flex:1;color:{self._ink};font-size:{size}px;'
            f'line-height:{lh};letter-spacing:0.3px;">{inner}</section></section>\n'
        )

    def _render_ol_item(self, inner: str, size: int, lh: float) -> str:
        """有序列表项"""
        cfg = self._cfg("ol")
        color = cfg.get("color", self._brand)
        preset_id = cfg.get("preset", "arabic")
        preset = get_preset("ol", preset_id)
        fmt = preset.get("format", "{n}.")
        label = _format_ol_number(self._list_item_index, fmt)

        # 方块数字用特殊样式
        if fmt == "square":
            return (
                f'<section style="display:flex;align-items:flex-start;margin-bottom:10px;">'
                f'<section style="min-width:22px;height:22px;background:{color};'
                f'color:#fff;font-size:12px;font-weight:600;text-align:center;'
                f'line-height:22px;border-radius:3px;margin-right:10px;'
                f'margin-top:2px;flex-shrink:0;">{label}</section>'
                f'<section style="flex:1;color:{self._ink};font-size:{size}px;'
                f'line-height:{lh};">{inner}</section></section>\n'
            )

        return (
            f'<section style="display:flex;align-items:flex-start;margin-bottom:10px;">'
            f'<section style="min-width:22px;color:{color};font-size:14px;'
            f'font-weight:600;flex-shrink:0;margin-right:8px;'
            f'line-height:{size * lh}px;">{label}</section>'
            f'<section style="flex:1;color:{self._ink};font-size:{size}px;'
            f'line-height:{lh};">{inner}</section></section>\n'
        )

    def block_code(self, code: str, info: str = None, **attrs) -> str:
        """代码块"""
        style = self._resolve("pre")
        return (
            f'<section style="{style}">'
            f'<pre style="margin:0;white-space:pre-wrap;word-break:break-word;">'
            f'{code}</pre></section>\n'
        )

    # ===== 行内元素 =====

    def strong(self, text: str) -> str:
        """加粗"""
        color = self._cfg("bold").get("color", self._brand)
        return f'<strong style="color:{color};font-weight:bold;">{text}</strong>'

    def emphasis(self, text: str) -> str:
        """斜体"""
        color = self._cfg("italic").get("color", self._ink)
        return f'<em style="font-style:italic;color:{color};">{text}</em>'

    def strikethrough(self, text: str) -> str:
        """删除线"""
        return f'<del style="text-decoration:line-through;color:#999;">{text}</del>'

    def codespan(self, text: str) -> str:
        """行内代码"""
        style = self._resolve("code")
        return f'<code style="{style}">{text}</code>'

    def link(self, text: str, url: str, title: str = None) -> str:
        """链接 — 微信编辑器中链接不可点击"""
        style = self._resolve("a")
        return f'<span style="{style}">{text}</span>'

    def image(self, text: str, url: str, title: str = None) -> str:
        """图片"""
        cfg = self._cfg("img")
        preset_id = cfg.get("preset", "rounded")
        preset = get_preset("img", preset_id)
        img_style = preset.get("imgStyle", "display:block;max-width:100%;margin:16px auto;")
        return (
            f'<section style="text-align:center;margin:16px 0;">'
            f'<img src="{url}" style="{img_style}" />'
            f'</section>\n'
        )

    # ===== 表格 =====

    def table(self, text: str) -> str:
        """表格容器"""
        cfg = self._cfg("table")
        preset_id = cfg.get("preset", "plain")
        preset = get_preset("table", preset_id)
        table_style = resolve_style(
            preset.get("tableStyle", ""), cfg, self._global
        )
        return (
            f'<section style="margin:16px 0;overflow-x:auto;">'
            f'<table style="{table_style}">{text}</table></section>\n'
        )

    def table_head(self, text: str) -> str:
        return f'<thead>{text}</thead>'

    def table_body(self, text: str) -> str:
        return f'<tbody>{text}</tbody>'

    def table_row(self, text: str) -> str:
        return f'<tr>{text}</tr>'

    def table_cell(self, text: str, align: str = None, head: bool = False) -> str:
        """表格单元格"""
        cfg = self._cfg("table")
        preset_id = cfg.get("preset", "plain")
        preset = get_preset("table", preset_id)

        align_css = f"text-align:{align};" if align else ""

        if head:
            th_style = resolve_style(
                preset.get("thStyle", ""), cfg, self._global
            )
            return f'<th style="{th_style}{align_css}">{text}</th>'

        td_style = resolve_style(
            preset.get("tdStyle", ""), cfg, self._global
        )
        return f'<td style="{td_style}{align_css}">{text}</td>'


def render_markdown_to_html(markdown_text: str, theme: dict) -> str:
    """
    将 Markdown 文本转为微信兼容的主题化 HTML

    Args:
        markdown_text: Markdown 文本
        theme: 主题配置字典（新格式，含 global/h1/h2/p 等）
    """
    renderer = WechatRenderer(theme)
    md = mistune.create_markdown(
        renderer=renderer,
        plugins=['table', 'strikethrough'],
    )
    html_body = md(markdown_text)

    # 全局容器
    g = theme.get("global", {})
    bg = g.get("bg", "#ffffff")
    font_id = g.get("fontFamily", "sans-zh")
    font_family = FONT_FAMILIES.get(font_id, FONT_FAMILIES["sans-zh"])

    return (
        f'<section style="background:{bg};padding:20px 16px;'
        f'font-family:{font_family};">'
        f'{html_body}</section>'
    )
