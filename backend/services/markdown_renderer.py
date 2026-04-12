# -*- coding: utf-8 -*-
"""
微信公众号 Markdown 渲染器

基于 mistune v3 的自定义渲染器，将 Markdown 转为微信兼容的内联样式 HTML。

设计原则：
- 每个 HTML 元素的样式完全由主题 JSON 控制
- 所有样式内联（微信不支持 class/外联 CSS）
- 列表用 flexbox section 替代原生 <ul>/<ol>（微信兼容）
- 标题/引用增加装饰元素（色条/引号/渐变背景）

借鉴 xiaohu-wechat-format 项目的排版思路。
"""
import mistune
import logging
from services.html_sanitizer import add_cjk_spacing, fix_bold_punctuation

logger = logging.getLogger(__name__)


class WechatRenderer(mistune.HTMLRenderer):
    """
    微信公众号专用 Markdown 渲染器

    将标准 Markdown 元素转为内联样式 HTML，所有样式参数
    从 theme_styles 字典读取，实现主题与代码解耦。
    """

    def __init__(self, theme_styles: dict):
        super().__init__()
        self._s = theme_styles
        # 追踪列表项序号（有序列表）
        self._list_item_index = 0
        self._in_ordered_list = False

    # ===== 辅助方法 =====

    def _get(self, key: str, default: str = "") -> str:
        """读取主题参数，带默认值"""
        return self._s.get(key, default)

    # ===== 块级元素 =====

    def heading(self, text: str, level: int, **attrs) -> str:
        """
        标题渲染

        h1: 文章标题 — 居中 + 下方装饰色条
        h2: 小标题 — 左侧色块 + 渐变背景条
        h3: 三级标题 — 加粗带色
        """
        text = add_cjk_spacing(text)

        if level == 1:
            color = self._get("h1_color", "#333333")
            size = self._get("h1_font_size", 22)
            align = self._get("h1_text_align", "center")
            margin = self._get("h1_margin", "32px 0 12px")
            spacing = self._get("h1_letter_spacing", "1px")
            lh = self._get("h1_line_height", 1.4)
            dec_color = self._get("h1_decoration_color",
                                  self._get("strong_color", "#07C160"))
            dec_width = self._get("h1_decoration_width", "40px")

            return (
                f'<section style="text-align:{align};margin:{margin};'
                f'padding:0 16px;">'
                f'<h1 style="color:{color};font-size:{size}px;'
                f'font-weight:bold;line-height:{lh};margin:0 0 12px;'
                f'letter-spacing:{spacing};">{text}</h1>'
                f'<section style="width:{dec_width};height:3px;'
                f'background:{dec_color};margin:0 auto;'
                f'border-radius:2px;"></section></section>\n'
            )

        elif level == 2:
            color = self._get("h2_color", self._get("h1_color", "#333333"))
            size = self._get("h2_font_size", 18)
            border_color = self._get("h2_border_left_color",
                                     self._get("strong_color", "#07C160"))
            bg = self._get("h2_bg_color",
                           self._get("blockquote_bg", "#f6f6f6"))

            return (
                f'<section style="margin:28px 0 16px;padding:10px 14px;'
                f'border-left:4px solid {border_color};'
                f'background:linear-gradient(90deg,{bg},transparent);">'
                f'<h2 style="color:{color};font-size:{size}px;'
                f'font-weight:bold;margin:0;line-height:1.5;'
                f'letter-spacing:0.5px;">{text}</h2></section>\n'
            )

        else:
            # h3+
            color = self._get("h1_color", "#333333")
            accent = self._get("strong_color", "#07C160")
            size = self._get("p_font_size", 15) + 1
            return (
                f'<h3 style="color:{color};font-size:{size}px;'
                f'font-weight:bold;margin:20px 0 10px;'
                f'padding-left:8px;border-left:3px solid {accent};'
                f'line-height:1.5;">{text}</h3>\n'
            )

    def paragraph(self, text: str) -> str:
        """正文段落 — 首行缩进 + 字间距"""
        text = add_cjk_spacing(text)
        text = fix_bold_punctuation(text)

        color = self._get("p_color", "#3f3f3f")
        size = self._get("p_font_size", 15)
        lh = self._get("p_line_height", 1.8)
        mb = self._get("p_margin_bottom", "16px")
        indent = self._get("p_text_indent", "2em")
        spacing = self._get("p_letter_spacing", "0.5px")

        return (
            f'<p style="color:{color};font-size:{size}px;'
            f'line-height:{lh};margin:0 0 {mb};'
            f'text-indent:{indent};letter-spacing:{spacing};">'
            f'{text}</p>\n'
        )

    def block_quote(self, text: str) -> str:
        """引用块 — 左边框 + 浅背景 + 引号装饰"""
        bg = self._get("blockquote_bg", "#f6f6f6")
        border = self._get("blockquote_border_color",
                           self._get("strong_color", "#07C160"))
        color = self._get("blockquote_text_color", "#555")
        size = self._get("p_font_size", 15)
        lh = self._get("p_line_height", 1.8)
        font_style = self._get("blockquote_font_style", "italic")

        # 去掉内层 <p> 的 margin 和 indent（引用块内不需要缩进）
        inner = text.replace("text-indent:2em;", "text-indent:0;")
        inner = inner.replace(f"color:{self._get('p_color', '#3f3f3f')}",
                              f"color:{color}")

        return (
            f'<section style="margin:20px 0;padding:16px 20px 16px 18px;'
            f'background:{bg};border-left:4px solid {border};'
            f'border-radius:0 8px 8px 0;">'
            f'<section style="color:{border};font-size:24px;'
            f'font-weight:bold;line-height:1;margin-bottom:6px;">'
            f'&#x201C;</section>'
            f'{inner}</section>\n'
        )

    def thematic_break(self) -> str:
        """分割线 --- """
        style = self._get("hr_style", "dots")
        color = self._get("hr_color", self._get("strong_color", "#07C160"))

        if style == "dots":
            return (
                f'<section style="text-align:center;margin:28px 0;'
                f'color:{color};letter-spacing:12px;font-size:14px;">'
                f'&#x25CF; &#x25CF; &#x25CF;</section>\n'
            )
        elif style == "gradient":
            return (
                f'<section style="margin:28px auto;width:30%;height:1px;'
                f'background:linear-gradient(90deg,transparent,'
                f'{color},transparent);"></section>\n'
            )
        else:
            return (
                f'<section style="margin:28px auto;width:40%;height:1px;'
                f'background:{color};opacity:0.3;"></section>\n'
            )

    def list(self, text: str, ordered: bool, **attrs) -> str:
        """
        列表容器

        微信编辑器会破坏原生 <ul>/<ol>，
        所以不输出列表标签，直接用 section 包裹列表项。
        """
        self._in_ordered_list = ordered
        self._list_item_index = 0
        return f'<section style="margin:16px 0;padding-left:4px;">{text}</section>\n'

    def list_item(self, text: str, **attrs) -> str:
        """
        列表项 — 用 flexbox section 替代原生 <li>

        无序列表：圆点 + 文本
        有序列表：数字圆圈 + 文本
        """
        self._list_item_index += 1
        bullet_color = self._get("list_bullet_color",
                                 self._get("strong_color", "#07C160"))
        text_color = self._get("list_text_color",
                               self._get("p_color", "#3f3f3f"))
        size = self._get("p_font_size", 15)
        lh = self._get("p_line_height", 1.8)

        # 去掉内层 <p> 标签（列表项内不需要段落包裹）
        inner = text.strip()
        if inner.startswith("<p "):
            # 提取 <p ...>content</p> 中的 content
            import re
            m = re.match(r'<p[^>]*>(.*)</p>', inner, re.DOTALL)
            if m:
                inner = m.group(1)

        inner = add_cjk_spacing(inner)

        if self._in_ordered_list:
            # 有序列表：数字圆圈
            return (
                f'<section style="display:flex;align-items:flex-start;'
                f'margin-bottom:10px;">'
                f'<section style="min-width:22px;width:22px;height:22px;'
                f'border-radius:50%;background:{bullet_color}20;'
                f'color:{bullet_color};font-size:12px;font-weight:bold;'
                f'text-align:center;line-height:22px;margin-right:10px;'
                f'margin-top:2px;flex-shrink:0;">'
                f'{self._list_item_index}</section>'
                f'<section style="flex:1;color:{text_color};'
                f'font-size:{size}px;line-height:{lh};'
                f'letter-spacing:0.5px;">{inner}</section></section>\n'
            )
        else:
            # 无序列表：圆点
            return (
                f'<section style="display:flex;align-items:flex-start;'
                f'margin-bottom:10px;">'
                f'<section style="min-width:6px;width:6px;height:6px;'
                f'border-radius:50%;background:{bullet_color};'
                f'margin-right:12px;margin-top:8px;flex-shrink:0;">'
                f'</section>'
                f'<section style="flex:1;color:{text_color};'
                f'font-size:{size}px;line-height:{lh};'
                f'letter-spacing:0.5px;">{inner}</section></section>\n'
            )

    def block_code(self, code: str, info: str = None, **attrs) -> str:
        """代码块"""
        bg = self._get("code_bg", "#f5f5f5")
        color = self._get("code_color", "#333")
        size = self._get("code_font_size", 13)

        return (
            f'<section style="background:{bg};padding:14px 16px;'
            f'border-radius:6px;margin:16px 0;overflow-x:auto;">'
            f'<pre style="margin:0;font-family:Consolas,monospace;'
            f'font-size:{size}px;color:{color};line-height:1.6;'
            f'white-space:pre-wrap;word-break:break-all;">'
            f'{code}</pre></section>\n'
        )

    # ===== 行内元素 =====

    def strong(self, text: str) -> str:
        """加粗 — 使用主题强调色"""
        color = self._get("strong_color", "#07C160")
        return f'<strong style="color:{color};font-weight:bold;">{text}</strong>'

    def emphasis(self, text: str) -> str:
        """斜体"""
        return f'<em style="font-style:italic;">{text}</em>'

    def codespan(self, text: str) -> str:
        """行内代码"""
        bg = self._get("code_bg", "#f5f5f5")
        color = self._get("code_color", "#e74c3c")
        size = self._get("code_font_size", 13)
        return (
            f'<code style="background:{bg};color:{color};'
            f'font-size:{size}px;padding:2px 6px;border-radius:3px;'
            f'font-family:Consolas,monospace;">{text}</code>'
        )

    def link(self, text: str, url: str, title: str = None) -> str:
        """链接 — 微信编辑器中链接不可点击，仅保留样式"""
        color = self._get("strong_color", "#07C160")
        return f'<span style="color:{color};">{text}</span>'

    def image(self, text: str, url: str, title: str = None) -> str:
        """图片"""
        return (
            f'<section style="text-align:center;margin:16px 0;">'
            f'<img src="{url}" style="max-width:100%;border-radius:4px;" />'
            f'</section>\n'
        )


def render_markdown_to_html(markdown_text: str, theme: dict) -> str:
    """
    将 Markdown 文本转为微信兼容的主题化 HTML

    流程：
    1. 创建基于主题样式的自定义渲染器
    2. mistune 解析 Markdown → 自定义 HTML
    3. 用全局容器包裹（背景色 + 内边距）

    Args:
        markdown_text: AI 返回的 Markdown 文本
        theme: 主题配置字典（含 styles 子字典）

    Returns:
        微信兼容的内联样式 HTML
    """
    styles = theme.get("styles", {})
    renderer = WechatRenderer(styles)
    md = mistune.create_markdown(renderer=renderer)

    html_body = md(markdown_text)

    # 全局容器包裹
    bg_color = styles.get("bg_color", "#ffffff")
    padding = styles.get("content_padding", "20px 16px")
    full_html = (
        f'<section style="background:{bg_color};padding:{padding};">'
        f'{html_body}'
        f'</section>'
    )

    return full_html
