# -*- coding: utf-8 -*-
"""
Pydantic 数据模型
定义所有 API 请求体和响应体的数据结构
"""
from pydantic import BaseModel, Field
from typing import Optional


# ===== 排版相关 =====

class LayoutRequest(BaseModel):
    """AI 排版请求"""
    content: str = Field(..., min_length=50, max_length=8000, description="待排版的文章原文")
    options: Optional[dict] = Field(default=None, description="排版选项")


class LayoutSection(BaseModel):
    """排版结果中的一个区块"""
    type: str = Field(..., description="区块类型: title/subtitle/paragraph/quote/divider/list")
    content: Optional[str] = Field(default=None, description="区块内容")
    highlights: Optional[list[str]] = Field(default=None, description="需要加粗的关键词")
    items: Optional[list[str]] = Field(default=None, description="列表项（type=list时使用）")


class LayoutResponse(BaseModel):
    """AI 排版响应"""
    sections: list[LayoutSection] = Field(..., description="结构化排版区块")
    html: str = Field(..., description="完整 HTML（可直接复制到公众号）")
    suggested_theme: str = Field(default="default", description="AI 推荐的主题")
    word_count: int = Field(..., description="原文字数")
    process_time: str = Field(..., description="处理耗时")
    prompt_version: str = Field(..., description="使用的 Prompt 版本")


# ===== 主题相关 =====

class ThemeStyle(BaseModel):
    """主题样式定义"""
    title_color: str = "#333333"
    title_font_size: int = 20
    body_color: str = "#3f3f3f"
    body_font_size: int = 15
    line_height: float = 1.8
    accent_color: str = "#07C160"
    bg_color: str = "#ffffff"
    quote_color: str = "#f6f6f6"
    quote_border_color: str = "#07C160"
    divider_style: str = "dots"


class ThemeItem(BaseModel):
    """主题项"""
    id: str
    name: str
    preview: str = ""
    styles: ThemeStyle
    is_premium: bool = False


# ===== 认证相关 =====

class LoginRequest(BaseModel):
    """微信登录请求"""
    code: str = Field(..., description="wx.login 获取的 code")


class LoginResponse(BaseModel):
    """微信登录响应"""
    token: str = Field(..., description="会话 token")
    verified: bool = Field(..., description="是否已验证关注")
    quota: int = Field(default=10, description="剩余排版次数（每小时）")


# ===== 关注验证相关 =====

class VerifyRequest(BaseModel):
    """验证码校验请求"""
    code: str = Field(..., min_length=4, max_length=4, description="4 位验证码")


class VerifyResponse(BaseModel):
    """验证码校验响应"""
    success: bool
    message: str = ""
    valid_days: int = 0


class ActiveAccountResponse(BaseModel):
    """当前推广账号响应"""
    account: dict
    keyword: str = "排版"
    verify_valid_days: int = 30


class UserStatusResponse(BaseModel):
    """用户状态响应"""
    verified: bool
    verified_account: Optional[str] = None
    expires_at: Optional[str] = None
    layout_count: int = 0


# ===== 管理接口相关 =====

class SwitchAccountRequest(BaseModel):
    """切换推广账号请求"""
    admin_key: str = Field(..., description="管理员密钥")
    account_id: str = Field(..., description="目标公众号 ID")
    reason: Optional[str] = Field(default=None, description="切换原因备注")


class SwitchPromptRequest(BaseModel):
    """切换 Prompt 版本请求"""
    admin_key: str = Field(..., description="管理员密钥")
    version: str = Field(..., description="目标 Prompt 版本号")


# ===== 通用 =====

class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str
