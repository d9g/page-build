# 公众号文章排版小程序 — 产品需求文档

> 版本 v4.0 | 更新日期 2026-04-22

## 一、产品概述

微信小程序，帮助公众号运营者将文章内容快速转换为精美的公众号排版格式。

### 核心功能

| 功能 | 说明 | 技术实现 |
|------|------|---------|
| **⚡ 快速排版** | 用户粘贴 Markdown → 直接渲染 | 本地 mistune 渲染，不调 AI |
| **🤖 智能排版** | 用户粘贴纯文本 → AI 润色+分段 → 渲染 | 后端调 AI → Markdown → 渲染 |

### 技术栈

- **前端**：微信小程序原生开发
- **后端**：Python FastAPI + mistune v3
- **AI**：阿里 DashScope / 智谱 GLM（通过 .env 配置切换）
- **渲染引擎**：基于 article-tools 预设系统的自定义渲染器

---

## 二、页面流程

```
首页（输入）           结果页（预览+调参）
┌───────────┐        ┌──────────────────┐
│ textarea  │        │  预览区 (50vh)     │
│           │        │  ┌──────────────┐  │
│           │  ──→   │  │ rich-text    │  │
│           │        │  └──────────────┘  │
├───────────┤        ├──────────────────┤
│ ⚡快速  🤖智能 │    │  主题选择         │
└───────────┘        │  滑块调整         │
                     │  [复制] [重排]     │
                     └──────────────────┘
```

---

## 三、主题系统

### 主题列表（7 个）

| 主题 ID | 名称 | 主色 | 适用场景 | 类别 |
|---------|------|------|---------|------|
| `shujuan` | 暖棕书卷 | `#C96442` 暖橙棕 | 文化/散文/深度内容 | 通用（默认） |
| `jijian` | 黑白极简 | `#1A1A1A` 纯黑 | 科普/专业/知识类 | 通用 |
| `keji` | 科技蓝调 | `#2563EB` 科技蓝 | 互联网/产品/技术 | 通用 |
| `hupo` | 琥珀橙调 | `#E08A2E` 琥珀橙 | 情感/生活/故事 | 通用 |
| `zhenghong` | 正红宣调 | `#C41E3A` 正红 | 节庆/党建/品牌 | 通用 |
| `gufeng` | 古风玄幻 | `#C9A96E` 暖金 | 修仙/玄幻小说 | 小说 |
| `xuanyi` | 悬疑推理 | `#C0392B` 血红 | 悬疑/推理小说 | 小说 |

### 主题使用统计

后端记录每次排版使用的主题 ID，定期统计使用最多的主题自动设为默认。

### 预设系统

来自 [article-tools](https://github.com/zhijunio/article-tools) 项目，100+ 种元素预设：

- **h1 标题**：9 种（素净/下划/左竖条/卡片填充/双细线/标签形/斜纹...）
- **h2 标题**：11 种（素净/左竖条/下划线/虚线/胶囊/短底线/方括号/背景块...）
- **h3 标题**：8 种（素净/圆点/箭头/下划线/标签背景/波浪底...）
- **段落**：5 种（标准/首行缩进/两端对齐/宽松行距/缩进+两端）
- **引用**：8 种（左竖条/左竖条+底/卡片/边框/居中楷体/虚线框/提示...）
- **分割线**：7 种（细线/虚线/短线/渐变/菱形/星号/三点）
- **列表**：无序 10 种 + 有序 7 种
- **代码块**：5 种
- **表格**：5 种

---

## 四、API 设计

### 排版接口

```
POST /api/v1/layout/quick    # 快速排版（不调 AI，需登录）
POST /api/v1/layout           # 智能排版（调 AI，需验证码）
GET  /api/v1/themes           # 获取主题列表
```

### 请求格式

```json
{
  "content": "文章内容...",
  "options": {
    "theme": "shujuan"
  }
}
```

### 响应格式

```json
{
  "html": "<section>...</section>",
  "suggested_theme": "shujuan",
  "word_count": 1500,
  "process_time": "120ms",
  "mode": "quick"
}
```

---

## 五、验证机制

| 功能 | 验证要求 |
|------|---------|
| 快速排版 | 需要登录（关注公众号验证码） |
| 智能排版 | 需要登录 + 验证码 |

验证流程：用户在公众号内发送关键词 → 获取验证码 → 在小程序内输入验证码。

---

## 六、后端目录结构

```
backend/
├── api/
│   └── layout.py           # 排版 API（/layout/quick + /layout）
├── services/
│   ├── presets.py           # 100+ 种元素预设（从 article-tools 移植）
│   ├── markdown_renderer.py # 基于预设系统的 mistune 渲染器
│   ├── layout_service.py    # 排版业务逻辑（快速/智能双模式）
│   ├── ai_service.py        # AI 模型调用
│   ├── prompt_manager.py    # Prompt 管理
│   └── html_sanitizer.py    # HTML 清洗（微信兼容）
├── themes/
│   ├── shujuan.json         # 暖棕书卷（默认）
│   ├── jijian.json          # 黑白极简
│   ├── keji.json            # 科技蓝调
│   ├── hupo.json            # 琥珀橙调
│   ├── zhenghong.json       # 正红宣调
│   ├── gufeng.json          # 古风玄幻
│   └── xuanyi.json          # 悬疑推理
├── config.py
├── main.py
└── .env
```

## 七、前端目录结构

```
miniapp/
├── pages/
│   ├── index/               # 首页（双按钮入口）
│   │   ├── index.wxml
│   │   ├── index.js
│   │   └── index.wxss
│   └── result/              # 结果页（上预览+下调参）
│       ├── result.wxml
│       ├── result.js
│       └── result.wxss
├── components/
│   └── verify-modal/        # 验证码弹窗组件
├── utils/
│   ├── request.js           # 网络请求封装
│   ├── auth.js              # 登录鉴权
│   └── storage.js           # 本地存储（草稿等）
└── app.js
```

---

## 八、参考项目

- [zhijunio/article-tools](https://github.com/zhijunio/article-tools) — 预设系统、主题配置
- [eternityspring/article-tools](https://github.com/eternityspring/article-tools) — 排版渲染思路
