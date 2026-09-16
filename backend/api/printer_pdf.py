# -*- coding: utf-8 -*-
"""
文字打印工具 PDF 生成 API

POST /api/printer/generate-pdf
body: {"token": "account:openid:expires_at_ts", "text": "...", "title": "..."}
返回: application/pdf 文件流

设计要点 (2026-09-16):
- 走 page-build 后端生成, 用 reportlab + 霞鹜文楷 (TTF 单文件) 解决中文乱码
- 文件名: webyoung.cn_YYYYMMDDHHmmss.pdf (东八区 14 位时间戳)
- 每页画浅灰色 webyoung.cn 45° 旋转水印 (防伪)
- 接收 token (前端 verify 通过后拿到) 校验过期时间
- token 设计: account_id:gzh_openid:expires_at_ts, 三段用 : 分隔

与前端约定:
- 按钮顺序: 美化 → 打印 / 导出 PDF, 都触发 requireVerify()
- 通过后前端用 localStorage 里的 token 调此端点
"""
import io
import logging
import re
import time
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/printer", tags=["打印工具"])

# 注册中文字体 (霞鹜文楷 TTF 单文件, system-wide 已有)
# 注册一次, 全局复用
_FONT_NAME = "WenKai"
try:
    pdfmetrics.registerFont(TTFont(_FONT_NAME, "/usr/share/fonts/truetype/lxgw-wenkai/LXGWWenKai-Regular.ttf"))
except Exception as e:
    logger.error(f"中文字体注册失败: {e}")
    raise


class GeneratePdfRequest(BaseModel):
    """PDF 生成请求"""
    token: str = Field(..., description="verify 端点返回的 token")
    text: str = Field(..., min_length=1, max_length=50000, description="要写入 PDF 的文本")
    title: str = Field(default="", description="PDF 标题 (可选,默认空)")


def _validate_token(token: str) -> dict:
    """
    校验 token 格式和有效期
    token 格式: account_id:gzh_openid:expires_at_ts

    Returns:
        {"account_id": ..., "gzh_openid": ..., "expires_at": int}

    Raises:
        HTTPException 401/403
    """
    parts = token.split(":")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="token 格式错误")

    account_id, gzh_openid, expires_str = parts
    try:
        expires_at = int(expires_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="token 过期时间无效")

    if int(time.time()) > expires_at:
        raise HTTPException(status_code=401, detail="token 已过期,请重新激活")

    return {
        "account_id": account_id,
        "gzh_openid": gzh_openid,
        "expires_at": expires_at,
    }


def _format_cst_timestamp(ts: int) -> str:
    """
    时间戳转东八区 14 位字符串: YYYYMMDDHHmmss
    """
    from datetime import datetime, timezone, timedelta

    cst = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
    return cst.strftime("%Y%m%d%H%M%S")


def _wrap_text(text: str, font: str, font_size: float, max_width: float):
    """
    简单换行: 按字符宽度估算, 中文按 1.0 em, 英文按 0.5 em
    reportlab stringWidth 已可用, 用 canvas.stringWidth

    Returns: list[str]
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue

        current = ""
        for ch in paragraph:
            test = current + ch
            width = stringWidth(test, font, font_size)
            if width > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
    return lines


@router.post(
    "/generate-pdf",
    summary="生成 PDF (文字打印工具)",
    response_class=Response,
)
async def generate_pdf(body: GeneratePdfRequest):
    """
    生成带 webyoung.cn 水印的 PDF 文件, 中文支持 (霞鹜文楷 TTF)

    Returns:
        application/pdf stream with Content-Disposition: webyoung.cn_<ts>.pdf
    """
    # 1. 校验 token
    info = _validate_token(body.token)

    # 2. 准备 PDF
    buf = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)

    # 字体大小 / 颜色
    font_size = 12  # pt
    line_height = font_size * 1.8
    margin_x = 20 * mm
    margin_y = 25 * mm
    top_y = page_h - margin_y

    # 文本宽度
    text_max_width = page_w - 2 * margin_x

    # 行高
    line_height_pt = line_height

    # 3. 写标题 (可选)
    current_y = top_y
    if body.title.strip():
        c.setFont(_FONT_NAME, 16)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margin_x, current_y, body.title.strip())
        current_y -= 24

    # 4. 写正文 (按行换页)
    c.setFont(_FONT_NAME, font_size)
    c.setFillColorRGB(0, 0, 0)

    lines = _wrap_text(body.text, _FONT_NAME, font_size, text_max_width)
    bottom_y = margin_y

    for line in lines:
        if line == "":
            current_y -= line_height_pt * 0.5
            continue

        if current_y < bottom_y:
            c.showPage()
            current_y = top_y
            c.setFont(_FONT_NAME, font_size)
            c.setFillColorRGB(0, 0, 0)

        c.drawString(margin_x, current_y, line)
        current_y -= line_height_pt

    # 5. 在每页画水印 (45° 旋转, 浅灰色 webyoung.cn)
    page_count = c.getPageNumber()
    for page_idx in range(1, page_count + 1):
        c.showPage()  # 先翻到下一页, 再回退
    # 上面多翻了一页, 重新画水印到所有页 (page 1 ~ page_count)
    # 因为 canvas 只能操作当前页, 所以要遍历所有页

    # reportlab canvas 没有内建的 "go to page N" API, 用 _pageNumber + _pages
    # 简单方法: 重新生成 PDF

    # 方案: 重新构建一份完整 PDF (上面 for 已经循环, 当前在 page_count+1)
    # 简化: 直接重新生成, 把水印合并到每页绘制流程

    # ============ 重新生成: 一次性绘制正文 + 水印 ============
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    current_y = top_y

    # 标题
    if body.title.strip():
        c.setFont(_FONT_NAME, 16)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margin_x, current_y, body.title.strip())
        current_y -= 24

    # 先记录有哪些内容要画, 再统一生成
    c.setFont(_FONT_NAME, font_size)
    c.setFillColorRGB(0, 0, 0)

    pages_data = []  # [[(text, y), ...], ...]

    current_page_lines = []
    for line in lines:
        if line == "":
            # 空行也消耗空间
            if current_y - line_height_pt < bottom_y:
                pages_data.append(current_page_lines)
                current_page_lines = []
                current_y = top_y
            current_page_lines.append((line, current_y))
            current_y -= line_height_pt * 0.5
            continue

        if current_y < bottom_y:
            pages_data.append(current_page_lines)
            current_page_lines = []
            current_y = top_y

        current_page_lines.append((line, current_y))
        current_y -= line_height_pt

    if current_page_lines:
        pages_data.append(current_page_lines)

    # 绘制所有页
    for page_idx, page_lines in enumerate(pages_data):
        if page_idx > 0:
            c.showPage()

        # 1. 先画水印 (底色)
        c.saveState()
        c.translate(page_w / 2, page_h / 2)
        c.rotate(45)
        c.setFont(_FONT_NAME, 36)
        c.setFillColorRGB(0.78, 0.78, 0.78)  # 浅灰 #C8C8C8
        c.setStrokeColorRGB(0.78, 0.78, 0.78)
        # 水印中心画文字, 用 align center
        from reportlab.pdfbase.pdfmetrics import stringWidth
        watermark_text = "webyoung.cn"
        wm_w = stringWidth(watermark_text, _FONT_NAME, 36)
        c.drawString(-wm_w / 2, -18, watermark_text)
        c.restoreState()

        # 2. 再画正文 (上色, 覆盖水印)
        c.setFont(_FONT_NAME, font_size)
        c.setFillColorRGB(0, 0, 0)
        for line, y in page_lines:
            if line:
                c.drawString(margin_x, y, line)

    # 标题页特殊处理
    if body.title.strip():
        # 标题已经在第一页顶部画了, 不需要单独画水印页
        # 但前面水印逻辑会跳过第一页画水印, 因为 title 写在 current_y=top_y 上
        pass

    c.save()
    buf.seek(0)

    # 6. 文件名
    ts14 = _format_cst_timestamp(int(time.time()))
    filename = f"webyoung.cn_{ts14}.pdf"

    # 7. 返回
    pdf_bytes = buf.getvalue()
    logger.info(
        f"PDF 生成成功 | size={len(pdf_bytes)}B | pages={len(pages_data)} | "
        f"account={info['account_id']} | filename={filename}"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )