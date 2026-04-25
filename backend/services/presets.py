# -*- coding: utf-8 -*-
"""
元素样式预设库

移植自 article-tools 项目的 PRESETS 系统。
每个 Markdown 元素有多种视觉预设可选，主题通过 preset ID 引用。

样式模板占位符：
  {c}   → 主色（brand）
  {cbg} → 柔色（brandSoft）
  {fs}  → 字号
  {lh}  → 行高
  {ls}  → 字间距
  {tc}  → 文本色
"""

# NOTE: 字体族预设，供主题 global.fontFamily 引用
FONT_FAMILIES = {
    "serif-zh": "'PingFang SC', 'Songti SC', 'Source Han Serif SC', 'Noto Serif CJK SC', serif",
    "sans-zh": "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif",
    "fangsong": "'FangSong', 'STFangsong', '仿宋', serif",
    "kaiti": "'KaiTi', 'STKaiti', '楷体', serif",
    "mixed": "'Source Serif Pro', Georgia, 'PingFang SC', serif",
    "rounded": "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
}

PRESETS: dict[str, dict[str, dict]] = {

    # ============ H1 标题 ============
    "h1": {
        "plain": {
            "name": "素净居中",
            "style": "text-align:center;font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;line-height:1.4;",
        },
        "underline": {
            "name": "下划装饰",
            "style": "text-align:center;font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;padding-bottom:12px;border-bottom:2px solid {c};line-height:1.4;",
        },
        "leftbar": {
            "name": "左竖条",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;padding-left:14px;border-left:5px solid {c};line-height:1.4;",
        },
        "diamond": {
            "name": "左右菱形",
            "style": "text-align:center;font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;line-height:1.4;",
            "prefix": "◆ ", "suffix": " ◆",
        },
        "cardfill": {
            "name": "卡片填充",
            "style": "text-align:center;font-size:{fs}px;font-weight:700;color:#fff;margin:28px 0 20px;padding:16px 18px;background:{c};border-radius:10px;line-height:1.4;",
        },
        "softcard": {
            "name": "柔和底色",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;padding:14px 18px;background:{cbg};border-radius:8px;line-height:1.4;",
        },
        "doubleline": {
            "name": "双细线",
            "style": "text-align:center;font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;padding:14px 0;border-top:1px solid {c};border-bottom:1px solid {c};line-height:1.4;",
        },
        "tagline": {
            "name": "标签形",
            "style": "font-size:{fs}px;font-weight:700;color:#fff;margin:28px 0 20px;display:inline-block;padding:8px 18px 8px 14px;background:{c};border-radius:0 24px 24px 0;line-height:1.4;",
        },
        "stripes": {
            "name": "斜纹背景",
            "style": "text-align:center;font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 20px;padding:16px;background:repeating-linear-gradient(-45deg,{cbg},{cbg} 8px,transparent 8px,transparent 16px);border-radius:8px;line-height:1.4;",
        },
    },

    # ============ H2 标题 ============
    "h2": {
        "plain": {
            "name": "素净",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;line-height:1.45;",
        },
        "leftbar": {
            "name": "左竖条",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;padding-left:12px;border-left:4px solid {c};line-height:1.45;",
        },
        "underline": {
            "name": "下划线",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;padding-bottom:8px;border-bottom:2px solid {c};line-height:1.45;",
        },
        "dashed": {
            "name": "虚线底",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;padding-bottom:8px;border-bottom:1px dashed {c};line-height:1.45;",
        },
        "cornerbrace": {
            "name": "方角装饰",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;padding:4px 12px;border-top:2px solid {c};border-left:2px solid {c};display:inline-block;line-height:1.45;",
        },
        "pillsolid": {
            "name": "胶囊填充",
            "style": "font-size:{fs}px;font-weight:700;color:#fff;margin:28px 0 16px;display:inline-block;padding:6px 16px;background:{c};border-radius:999px;line-height:1.45;",
        },
        "pillsoft": {
            "name": "胶囊柔色",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;display:inline-block;padding:6px 16px;background:{cbg};border-radius:999px;line-height:1.45;",
        },
        "shortbar": {
            "name": "短粗底线",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;padding-bottom:8px;background-image:linear-gradient({c},{c});background-repeat:no-repeat;background-size:36px 3px;background-position:left bottom;line-height:1.45;",
        },
        "hash": {
            "name": "井号装饰",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;line-height:1.45;",
            "prefix": "# ",
        },
        "bracket": {
            "name": "方括号",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;line-height:1.45;",
            "prefix": "【", "suffix": "】",
        },
        "withbg": {
            "name": "背景块",
            "style": "font-size:{fs}px;font-weight:700;color:{c};margin:28px 0 16px;padding:10px 14px;background:{cbg};border-radius:6px;line-height:1.45;",
        },
    },

    # ============ H3 标题 ============
    "h3": {
        "plain": {
            "name": "素净",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;line-height:1.5;",
        },
        "bulletbefore": {
            "name": "圆点前缀",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;line-height:1.5;",
            "prefix": "● ",
        },
        "arrow": {
            "name": "箭头前缀",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;line-height:1.5;",
            "prefix": "▸ ",
        },
        "underline": {
            "name": "细下划线",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;padding-bottom:6px;border-bottom:1px solid {c};line-height:1.5;",
        },
        "leftbar": {
            "name": "左细条",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;padding-left:10px;border-left:3px solid {c};line-height:1.5;",
        },
        "emojispark": {
            "name": "闪光符号",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;line-height:1.5;",
            "prefix": "✦ ",
        },
        "labelbg": {
            "name": "标签背景",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;display:inline-block;padding:3px 10px;background:{cbg};border-radius:4px;line-height:1.5;",
        },
        "wave": {
            "name": "波浪底",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:22px 0 12px;padding-bottom:4px;background-image:linear-gradient(transparent 85%,{c} 85%);background-size:100% 2px;background-repeat:no-repeat;background-position:bottom;line-height:1.5;",
        },
    },

    # ============ H4 标题 ============
    "h4": {
        "plain": {
            "name": "素净",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:18px 0 10px;line-height:1.55;",
        },
        "dot": {
            "name": "圆点",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:18px 0 10px;line-height:1.55;",
            "prefix": "· ",
        },
        "arrow": {
            "name": "箭头",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:18px 0 10px;line-height:1.55;",
            "prefix": "→ ",
        },
        "caret": {
            "name": "尖号",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:18px 0 10px;line-height:1.55;",
            "prefix": "‣ ",
        },
        "caps": {
            "name": "小型大写",
            "style": "font-size:{fs}px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{c};margin:18px 0 10px;line-height:1.55;",
        },
        "softpill": {
            "name": "柔色胶囊",
            "style": "font-size:{fs}px;font-weight:600;color:{c};margin:18px 0 10px;display:inline-block;padding:2px 10px;background:{cbg};border-radius:10px;line-height:1.55;",
        },
    },

    # ============ 正文段落 ============
    "p": {
        "normal": {
            "name": "标准",
            "style": "font-size:{fs}px;line-height:{lh};color:{c};margin:14px 0;letter-spacing:{ls}px;",
        },
        "indent": {
            "name": "首行缩进",
            "style": "font-size:{fs}px;line-height:{lh};color:{c};margin:14px 0;text-indent:2em;letter-spacing:{ls}px;",
        },
        "justify": {
            "name": "两端对齐",
            "style": "font-size:{fs}px;line-height:{lh};color:{c};margin:14px 0;text-align:justify;letter-spacing:{ls}px;",
        },
        "loose": {
            "name": "宽松行距",
            "style": "font-size:{fs}px;line-height:{lh};color:{c};margin:18px 0;letter-spacing:{ls}px;",
        },
        "indentjust": {
            "name": "缩进+两端",
            "style": "font-size:{fs}px;line-height:{lh};color:{c};margin:14px 0;text-indent:2em;text-align:justify;letter-spacing:{ls}px;",
        },
    },

    # ============ 引用 ============
    "blockquote": {
        "leftbar": {
            "name": "左竖条",
            "style": "border-left:4px solid {c};padding:8px 14px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:transparent;",
        },
        "leftbar-bg": {
            "name": "左竖条+底",
            "style": "border-left:4px solid {c};padding:12px 16px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:{cbg};border-radius:0 6px 6px 0;",
        },
        "card": {
            "name": "卡片式",
            "style": "padding:14px 18px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:{cbg};border-radius:8px;",
        },
        "outlined": {
            "name": "边框卡片",
            "style": "padding:14px 18px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:transparent;border:1px solid {c};border-radius:8px;",
        },
        "center": {
            "name": "居中楷体",
            "style": "padding:14px 20px;margin:20px 40px;color:{tc};font-size:{fs}px;line-height:1.85;text-align:center;font-style:italic;border-top:1px solid {c};border-bottom:1px solid {c};",
        },
        "soft": {
            "name": "柔色纯底",
            "style": "padding:14px 18px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:{cbg};border-radius:4px;",
        },
        "dashedbox": {
            "name": "虚线框",
            "style": "padding:12px 16px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:transparent;border:1px dashed {c};border-radius:6px;",
        },
        "notice": {
            "name": "提示样式",
            "style": "padding:12px 14px 12px 18px;margin:16px 0;color:{tc};font-size:{fs}px;line-height:1.75;background:{cbg};border-left:3px solid {c};border-radius:0 4px 4px 0;",
        },
    },

    # ============ 代码块 ============
    "pre": {
        "lightgrey": {
            "name": "浅灰",
            "style": "background:#F6F4EF;color:#2B2016;border-radius:8px;padding:14px 16px;font-size:13px;line-height:1.7;white-space:pre-wrap;word-break:break-word;font-family:'SF Mono','JetBrains Mono',Menlo,Consolas,monospace;margin:16px 0;",
        },
        "warm-paper": {
            "name": "米白纸本",
            "style": "background:#FAF7F0;color:#3D2E20;border:1px solid #EAE3D4;border-radius:8px;padding:14px 16px;font-size:13px;line-height:1.7;white-space:pre-wrap;word-break:break-word;font-family:'SF Mono',Menlo,Consolas,monospace;margin:16px 0;",
        },
        "github-light": {
            "name": "GitHub 浅",
            "style": "background:#F6F8FA;color:#24292F;border:1px solid #D0D7DE;border-radius:6px;padding:14px 16px;font-size:13px;line-height:1.7;white-space:pre-wrap;word-break:break-word;font-family:'SF Mono',Menlo,Consolas,monospace;margin:16px 0;",
        },
        "subtle-border": {
            "name": "细框素",
            "style": "background:#FFFFFF;color:#2B2016;border:1px solid #E4DED2;border-radius:4px;padding:14px 16px;font-size:13px;line-height:1.7;white-space:pre-wrap;word-break:break-word;font-family:'SF Mono',Menlo,Consolas,monospace;margin:16px 0;",
        },
        "accent-bar": {
            "name": "左侧色条",
            "style": "background:#F6F4EF;color:#2B2016;border-left:4px solid {c};border-radius:0 6px 6px 0;padding:14px 16px;font-size:13px;line-height:1.7;white-space:pre-wrap;word-break:break-word;font-family:'SF Mono',Menlo,Consolas,monospace;margin:16px 0;",
        },
    },

    # ============ 行内代码 ============
    "code": {
        "pill-soft": {
            "name": "柔色胶囊",
            "style": "background:{cbg};color:{c};padding:2px 6px;border-radius:4px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:0.92em;",
        },
        "filled": {
            "name": "主色填充",
            "style": "background:{c};color:#fff;padding:2px 6px;border-radius:4px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:0.92em;",
        },
        "grey-ink": {
            "name": "灰底墨字",
            "style": "background:#F0EBE0;color:#2B2016;padding:2px 6px;border-radius:3px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:0.92em;",
        },
        "mark": {
            "name": "荧光笔",
            "style": "background:{cbg};color:{c};padding:0 4px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:0.95em;font-weight:600;",
        },
    },

    # ============ 无序列表 ============
    "ul": {
        "disc": {"name": "实心圆", "marker": "●"},
        "circle": {"name": "空心圆", "marker": "○"},
        "square": {"name": "方块", "marker": "■"},
        "diamond": {"name": "菱形", "marker": "◆"},
        "arrow": {"name": "箭头", "marker": "▸"},
        "dash": {"name": "短横", "marker": "—"},
        "check": {"name": "对勾", "marker": "✓"},
        "star": {"name": "星号", "marker": "✦"},
        "heart": {"name": "爱心", "marker": "♥"},
        "flower": {"name": "花饰", "marker": "❋"},
    },

    # ============ 有序列表 ============
    "ol": {
        "arabic": {"name": "阿拉伯数字", "format": "{n}."},
        "paren": {"name": "括号", "format": "{n})"},
        "circled": {"name": "圆圈数字", "format": "circled"},
        "square": {"name": "方块数字", "format": "square"},
        "dot": {"name": "句点", "format": "{n}．"},
        "chinese": {"name": "中文数字", "format": "chinese"},
        "bracket": {"name": "方括号", "format": "[{n}]"},
    },

    # ============ 链接 ============
    "a": {
        "underline": {
            "name": "下划线",
            "style": "color:{c};text-decoration-line:underline;text-decoration-thickness:1px;text-underline-offset:3px;",
        },
        "bold": {
            "name": "加粗无下划线",
            "style": "color:{c};text-decoration:none;font-weight:600;",
        },
        "dashed": {
            "name": "虚下划线",
            "style": "color:{c};text-decoration:none;border-bottom:1px dashed {c};padding-bottom:1px;",
        },
        "plain": {
            "name": "无装饰",
            "style": "color:{c};text-decoration:none;",
        },
    },

    # ============ 图片 ============
    "img": {
        "plain": {
            "name": "直角素净",
            "imgStyle": "display:block;max-width:100%;margin:16px auto;border-radius:0;",
        },
        "rounded": {
            "name": "小圆角",
            "imgStyle": "display:block;max-width:100%;margin:16px auto;border-radius:8px;",
        },
        "shadow": {
            "name": "柔和阴影",
            "imgStyle": "display:block;max-width:100%;margin:16px auto;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.12);",
        },
        "bordered": {
            "name": "边框素描",
            "imgStyle": "display:block;max-width:100%;margin:16px auto;border-radius:4px;border:1px solid #E4DED2;padding:6px;background:#fff;",
        },
    },

    # ============ 分割线 ============
    "hr": {
        "thin": {
            "name": "细线",
            "style": "border:none;border-top:1px solid {c};margin:28px 0;",
        },
        "dashed": {
            "name": "虚线",
            "style": "border:none;border-top:1px dashed {c};margin:28px 0;",
        },
        "short": {
            "name": "短线居中",
            "style": "border:none;height:2px;background:{c};width:60px;margin:28px auto;",
        },
        "gradient": {
            "name": "渐变淡出",
            "style": "border:none;height:1px;background:linear-gradient(90deg,transparent,{c},transparent);margin:28px 0;",
        },
        "diamond": {
            "name": "菱形装饰",
            "decorative": "◆ ◆ ◆",
            "style": "border:none;text-align:center;color:{c};font-size:14px;margin:28px 0;letter-spacing:8px;",
        },
        "star": {
            "name": "星号装饰",
            "decorative": "✦ ✦ ✦",
            "style": "border:none;text-align:center;color:{c};font-size:14px;margin:28px 0;letter-spacing:8px;",
        },
        "three-dots": {
            "name": "三点",
            "decorative": "• • •",
            "style": "border:none;text-align:center;color:{c};font-size:14px;margin:28px 0;letter-spacing:10px;",
        },
    },

    # ============ 表格 ============
    "table": {
        "plain": {
            "name": "素净",
            "tableStyle": "border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;",
            "thStyle": "border:1px solid {c};padding:8px 12px;background:transparent;color:{c};font-weight:600;text-align:left;",
            "tdStyle": "border:1px solid #e8e8e8;padding:8px 12px;",
        },
        "zebra": {
            "name": "斑马纹",
            "tableStyle": "border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;",
            "thStyle": "padding:10px 12px;background:{c};color:#fff;font-weight:600;text-align:left;",
            "tdStyle": "padding:8px 12px;border-bottom:1px solid #e8e8e8;",
        },
        "borderless": {
            "name": "无边框",
            "tableStyle": "border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;",
            "thStyle": "padding:10px 12px;border-bottom:2px solid {c};color:{c};font-weight:600;text-align:left;",
            "tdStyle": "padding:8px 12px;border-bottom:1px solid #e8e8e8;",
        },
        "softbg": {
            "name": "柔底表头",
            "tableStyle": "border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;",
            "thStyle": "padding:10px 12px;background:{cbg};color:{c};font-weight:600;text-align:left;",
            "tdStyle": "padding:8px 12px;border-bottom:1px solid #e8e8e8;",
        },
        "card": {
            "name": "卡片式",
            "tableStyle": "border-collapse:separate;border-spacing:0;width:100%;margin:16px 0;font-size:14px;border:1px solid #e8e8e8;border-radius:8px;overflow:hidden;",
            "thStyle": "padding:10px 12px;background:{c};color:#fff;font-weight:600;text-align:left;",
            "tdStyle": "padding:8px 12px;border-bottom:1px solid #e8e8e8;",
        },
    },
}


def get_preset(element: str, preset_id: str) -> dict:
    """
    获取指定元素的预设样式

    Args:
        element: 元素类型（h1/h2/p/blockquote 等）
        preset_id: 预设 ID（plain/leftbar/cardfill 等）

    Returns:
        预设字典，找不到则返回该元素的第一个预设
    """
    element_presets = PRESETS.get(element, {})
    if preset_id in element_presets:
        return element_presets[preset_id]
    # 回退到第一个预设
    if element_presets:
        return next(iter(element_presets.values()))
    return {}


def resolve_style(style_template: str, theme_cfg: dict, global_cfg: dict) -> str:
    """
    将样式模板中的占位符替换为主题实际值

    Args:
        style_template: 含 {c}/{cbg}/{fs} 等占位符的样式字符串
        theme_cfg: 该元素的主题配置（如 h1 的 color/fontSize）
        global_cfg: 全局主题配置（brand/brandSoft/ink）
    """
    brand = global_cfg.get("brand", "#333333")
    brand_soft = global_cfg.get("brandSoft", "#f0f0f0")
    ink = global_cfg.get("ink", "#333333")

    return (
        style_template
        .replace("{c}", theme_cfg.get("color", brand))
        .replace("{cbg}", theme_cfg.get("bgColor", brand_soft))
        .replace("{fs}", str(theme_cfg.get("fontSize", 16)))
        .replace("{lh}", str(theme_cfg.get("lineHeight", 1.75)))
        .replace("{ls}", str(theme_cfg.get("letterSpacing", 0.3)))
        .replace("{tc}", theme_cfg.get("textColor", ink))
    )
