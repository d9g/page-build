# -*- coding: utf-8 -*-
"""
Markdown 后处理器 v1.2

核心原则：默认保留原文内容，只做清理和轻量格式化。
会改变内容结构的操作（段落重组、章节降级等）仅在 preserve_content=False 时执行。
"""
import re
import logging

logger = logging.getLogger(__name__)

# 常量配置
MAX_PARAGRAPH_CHARS = 300   # 段落最大字数（仅 preserve_content=False 时拆分）
MIN_PARAGRAPH_CHARS = 20    # 段落最小字数（仅 preserve_content=False 时合并）
MAX_BOLD_PER_PARAGRAPH = 2  # 每段最多加粗数量
MAX_QUOTES = 4              # 最多引用数量（含金句）
MAX_GOLDEN_QUOTES = 3       # 最多金句数量
MAX_SECTIONS = 6            # 最多章节数量


def process_markdown(text: str, preserve_content: bool = True) -> str:
    """
    处理 AI 返回的 Markdown，清理格式问题。

    Args:
        text: AI 返回的原始 Markdown
        preserve_content: True=保留原文（默认），False=允许重组段落/章节
    """
    if not text or not text.strip():
        return text

    text = text.strip()

    # 1. 清理代码块包裹（总是执行）
    text = _clean_code_blocks(text)

    # 2. 删除 emoji（总是执行，已禁用 — WeChat 原生支持 emoji）
    # text = _remove_emoji(text)

    # 3. 过滤 AI 解释性文字（总是执行）
    text = _filter_explanations(text)

    # 4. 对话分段（总是执行，提升可读性）
    text = _split_dialogue(text)

    # 5. 金句标注处理（总是执行，验证 + 限数 + 格式化）
    text = _process_golden_quotes(text)

    if not preserve_content:
        # 以下操作会改变内容结构，仅在非保留模式下执行
        text = _normalize_paragraphs(text)
        text = _normalize_bold(text)
        text = _limit_quotes(text)
        text = _limit_sections(text)

    # 4. 清理多余空行（总是执行，但保留 Markdown 结构）
    text = _clean_empty_lines(text)

    return text.strip()


def _split_dialogue(text: str) -> str:
    """
    将连续的中文对话拆分成单独段落，提升可读性。

    规则：两个相邻引号之间的句子拆成独立段落。
    示例："第一句。""第二句。" → "第一句。"\n\n"第二句。"
    """
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('')
            continue
        # 结构行（标题、引用、列表、分割线）原样保留
        if (stripped.startswith('#')
            or stripped.startswith('>')
            or stripped.startswith('```')
            or stripped.startswith('---')
            or re.match(r'^[\-\*]\s', stripped)
            or re.match(r'^\d+\.\s', stripped)):
            result.append(line)
            continue

        # 对话行：把连续的引号序列拆开
        new_line = _split_consecutive_quotes(line)
        result.append(new_line)

    return '\n'.join(result)


def _split_consecutive_quotes(text: str) -> str:
    """
    把连续的中文对话拆开，每对引号内容单独成段。
    处理 xxx"内容1"yyy"内容2"zzz"内容3"www 的情况。
    """
    result = []
    i = 0
    buffer = ""

    while i < len(text):
        if text[i] == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                j += 1
            segment = text[i:j+1]
            k = j + 1
            while k < len(text) and text[k] in ' \t':
                k += 1
            if k < len(text) and text[k] == '"':
                result.append(buffer + segment)
                buffer = ""
                i = k
                continue
            else:
                buffer += segment
                i = j + 1
                continue
        else:
            buffer += text[i]
            i += 1

    result.append(buffer)
    return '\n\n'.join(r for r in result if r.strip())


def _clean_code_blocks(text: str) -> str:
    """去掉 ```markdown 等包裹"""
    text = re.sub(r'^```\w*\n?', '', text)
    text = re.sub(r'\n?```\w*\s*$', '', text)
    return text


def _remove_emoji(text: str) -> str:
    """删除 emoji 字符（不误删汉字和中文标点）"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U0001FA00-\U0001FA6F"  # chess/emoji symbols
        "\U0001FA70-\U0001FAFF"  # more symbols
        "\U00002600-\U000026FF"  # misc symbols
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r'', text)


def _filter_explanations(text: str) -> str:
    """过滤 AI 可能添加的解释性文字"""
    lines = text.split('\n')
    result = []
    skip_patterns = [
        r'^以下是?',
        r'^这篇文章',
        r'^我已经',
        r'^根据您的',
        r'^我为您',
        r'^排版后的',
        r'^文章排版',
        r'^这是排版',
        r'^下面是对',
        r'^（本文已排版',
        r'^希望这份',
    ]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, stripped):
                should_skip = True
                logger.debug(f"过滤解释行: {stripped[:50]}")
                break
        # 不要误删以 ** 开头的加粗文字
        if stripped.startswith('**') and not stripped.startswith('***'):
            should_skip = False
        if not should_skip:
            result.append(line)
    return '\n'.join(result)


def _normalize_paragraphs(text: str) -> str:
    """段落规范化：拆分过长段落，合并过短段落（仅在非保留模式下使用）

    确保输出中段落之间有空行分隔，避免 Markdown 渲染时段落粘连。
    """
    lines = text.split('\n')
    result = []
    buffer = ""

    def _is_structure_line(s: str) -> bool:
        """判断是否为 Markdown 结构行"""
        return (
            not s or
            s.startswith('#') or
            s.startswith('>') or
            re.match(r'^[\-\*]\s', s) or
            re.match(r'^\d+\.\s', s) or
            s.startswith('---') or
            s.startswith('```')
        )

    for line in lines:
        stripped = line.strip()

        if _is_structure_line(stripped):
            if buffer:
                _flush_buffer(result, buffer)
                buffer = ""
            result.append(line)
            continue

        # 普通段落：累加到缓冲区
        if buffer:
            buffer += " " + stripped
        else:
            buffer = stripped

        # 检查是否超过最大长度
        if len(buffer) > MAX_PARAGRAPH_CHARS:
            split_pos = _find_split_position(buffer)
            if split_pos > MIN_PARAGRAPH_CHARS:
                result.append(buffer[:split_pos])
                buffer = buffer[split_pos:].strip()
            else:
                result.append(buffer)
                buffer = ""

    # 刷新最后的缓冲
    if buffer:
        _flush_buffer(result, buffer)

    # 确保段落之间有空行分隔（Markdown 需要空行来分隔段落）
    separated = []
    for i, line in enumerate(result):
        stripped_line = line.strip()
        if _is_structure_line(stripped_line):
            separated.append(line)
        else:
            # 普通文本行：检查前一行是否也是普通文本（非空行、非结构行）
            if separated:
                prev_stripped = separated[-1].strip() if separated[-1] else ''
                if not _is_structure_line(prev_stripped) and prev_stripped:
                    # 前一行也是普通文本，插入空行分隔
                    separated.append('')
            separated.append(line)

    return '\n'.join(separated)


def _flush_buffer(result: list, buffer: str):
    """将缓冲区内容写入结果，处理短段落合并"""
    if not buffer:
        return
    if len(buffer) < MIN_PARAGRAPH_CHARS and result:
        # 短段落合并到上一段
        last = result[-1]
        if last and not last.startswith('#') and not last.startswith('>') and not last.startswith('---'):
            result[-1] = last + " " + buffer
            return
    result.append(buffer)


def _find_split_position(text: str) -> int:
    """在文本中找合适的分割位置（句号、问号、感叹号后）"""
    if not text:
        return 0
    if len(text) <= MAX_PARAGRAPH_CHARS:
        return len(text)
    # 从 MAX_PARAGRAPH_CHARS 往前找标点
    search_start = min(MAX_PARAGRAPH_CHARS, len(text) - 1)
    for i in range(search_start, MIN_PARAGRAPH_CHARS, -1):
        if i < len(text) and text[i] in '。！？.!?':
            return min(i + 1, len(text))
    # 找不到标点，在空格处分割
    for i in range(search_start, MIN_PARAGRAPH_CHARS, -1):
        if i < len(text) and text[i] == ' ':
            return min(i + 1, len(text))
    # 兜底：在 MAX_PARAGRAPH_CHARS 处分割，但不超过文本长度
    return min(MAX_PARAGRAPH_CHARS, len(text))


def _normalize_bold(text: str) -> str:
    """规范化加粗标记：每段最多 MAX_BOLD_PER_PARAGRAPH 个"""
    lines = text.split('\n')
    result = []
    for line in lines:
        # 跳过结构行
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('>') or stripped.startswith('---') or stripped.startswith('```'):
            result.append(line)
            continue

        # 统计已有加粗
        bold_count = len(re.findall(r'\*\*[^*]+\*\*', line))
        if bold_count > MAX_BOLD_PER_PARAGRAPH:
            # 保留前 MAX_BOLD_PER_PARAGRAPH 个，其余的去掉加粗
            new_line = line
            count = 0
            def repl(m):
                nonlocal count
                count += 1
                if count <= MAX_BOLD_PER_PARAGRAPH:
                    return m.group(0)
                return m.group(1)  # 去掉 ** 保留内容
            new_line = re.sub(r'\*\*([^*]+)\*\*', repl, new_line)
            result.append(new_line)
        else:
            result.append(line)
    return '\n'.join(result)


def _limit_quotes(text: str) -> str:
    """限制引用数量"""
    lines = text.split('\n')
    result = []
    quote_count = 0
    for line in lines:
        if line.strip().startswith('>'):
            quote_count += 1
            if quote_count > MAX_QUOTES:
                # 超出的引用降级为普通段落（去掉 >）
                cleaned = re.sub(r'^>\s*', '', line)
                result.append(cleaned)
                continue
        result.append(line)
    return '\n'.join(result)


def _limit_sections(text: str) -> str:
    """限制章节数量，超出的降级为加粗正文"""
    lines = text.split('\n')
    result = []
    section_count = 0
    for line in lines:
        stripped = line.strip()
        if re.match(r'^#{2,3}\s', stripped):
            section_count += 1
            if section_count > MAX_SECTIONS:
                # 降级为加粗正文
                cleaned = re.sub(r'^#{2,3}\s*', '', stripped)
                result.append(f"**{cleaned}**")
                logger.debug(f"章节超出限制，降级为加粗: {cleaned[:50]}...")
                continue
        result.append(line)
    return '\n'.join(result)


def _process_golden_quotes(text: str) -> str:
    """
    处理金句标注（> 💡 开头的引用块）

    - 规范化格式：> 💡 内容（确保 💡 后有空格）
    - 限制数量：超过 MAX_GOLDEN_QUOTES 的降级为普通引用
    - 过滤过短金句（少于10字的不是金句）
    - 确保金句不会和普通引用混淆
    """
    lines = text.split('\n')
    result = []
    golden_count = 0

    # 金句标记模式：> 💡 或 >💡 或 > · 或其他变体
    golden_pattern = re.compile(r'^(>\s*)[💡✨⭐💎★]\s*(.*)')

    for line in lines:
        stripped = line.strip()
        match = golden_pattern.match(stripped)

        if match:
            golden_count += 1
            quote_prefix = match.group(1)  # >
            content = match.group(2).strip()

            # 金句内容太短，降级为普通引用
            if len(content) < 10:
                logger.debug(f"金句过短，降级为普通引用: {content[:30]}")
                result.append(f"> {content}")
                continue

            # 超出数量限制，降级为普通引用
            if golden_count > MAX_GOLDEN_QUOTES:
                logger.debug(f"金句超出限制({MAX_GOLDEN_QUOTES})，降级: {content[:30]}")
                result.append(f"> {content}")
                continue

            # 规范化为统一格式：> 💡 内容
            result.append(f"> 💡 {content}")
        else:
            result.append(line)

    if golden_count > 0:
        logger.info(f"金句标注: {min(golden_count, MAX_GOLDEN_QUOTES)}/{golden_count} 处")

    return '\n'.join(result)


def _clean_empty_lines(text: str) -> str:
    """清理多余空行，保留 Markdown 结构

    确保段落之间有且仅有一个空行（Markdown 段落分隔标准），
    同时清理过多连续空行。
    """
    # 确保非结构文本行之间有空行分隔（Markdown 段落分隔）
    lines = text.split('\n')
    result = []

    def _is_structure(s: str) -> bool:
        """判断是否为 Markdown 结构行"""
        return (
            not s or
            s.startswith('#') or
            s.startswith('>') or
            s.startswith('```') or
            s.startswith('---') or
            re.match(r'^[\-\*]\s', s) or
            re.match(r'^\d+\.\s', s)
        )

    for i, line in enumerate(lines):
        stripped = line.strip()

        if _is_structure(stripped):
            result.append(line)
        else:
            # 普通文本行：检查前一行是否也是普通文本（非空行、非结构行）
            if result:
                prev_stripped = result[-1].strip() if result[-1] else ''
                if not _is_structure(prev_stripped) and prev_stripped:
                    # 前一行也是普通文本且不是空行，插入空行分隔
                    result.append('')
            result.append(line)

    text = '\n'.join(result)
    # 清理过多连续空行（最多保留 2 个空行 = 3 个连续换行）
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text
