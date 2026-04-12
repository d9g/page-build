# 公众号文章排版小程序

一个极简的 AI 智能排版工具。用户粘贴文章 → 一键 AI 排版 → 微调主题 → 复制到公众号。

## 技术栈

| 组件 | 技术 |
|------|------|
| 小程序前端 | 微信原生小程序（WXML + WXSS + JS）|
| 后端 | Python FastAPI |
| AI 模型 | 智谱 GLM-4-Flash（免费）|
| 数据库 | SQLite（可扩展为 MySQL）|
| 缓存 | Redis |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/pb-layout.git
cd pb-layout
```

### 2. 后端安装

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的真实配置
```

### 3. 配置环境变量

编辑 `backend/.env`，填入以下必要配置：

```bash
# 必填 — 智谱 AI API Key（在 https://open.bigmodel.cn/ 获取）
ZHIPU_API_KEY=your_key_here

# 必填 — 微信小程序 AppID 和 AppSecret
MINI_APP_ID=your_app_id
MINI_APP_SECRET=your_app_secret

# 必填 — 管理密钥（自定义复杂字符串）
ADMIN_SECRET_KEY=your_random_secret

# 至少配置一个公众号
ACCOUNT_A_ID=account_a
ACCOUNT_A_NAME=你的公众号名称
# ... 详见 .env.example
```

### 4. 启动后端

```bash
cd backend

# 开发模式（支持热重载）
DEBUG=true python main.py

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看 API 文档（仅 DEBUG 模式）。

### 5. 小程序开发

1. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 导入 `miniapp/` 目录
3. 修改 `miniapp/config/api.js` 中的 API 地址
4. 编译预览

## 项目结构

```
pb-layout/
├── backend/               # 后端（FastAPI）
│   ├── api/               # API 路由
│   ├── services/          # 业务逻辑
│   ├── models/            # 数据模型
│   ├── middleware/         # 中间件
│   ├── prompts/           # Prompt 版本管理
│   ├── main.py            # 入口
│   └── config.py          # 配置
├── miniapp/               # 小程序前端
│   ├── pages/             # 4 个页面
│   ├── components/        # 组件
│   └── utils/             # 工具函数
└── deploy/                # 部署配置
```

## 服务器部署

详见 `deploy/` 目录下的配置文件：

```bash
# 1. 配置 Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/pb-layout
# 修改域名和 SSL 证书路径
sudo ln -s /etc/nginx/sites-available/pb-layout /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 2. 配置 systemd 服务
sudo cp deploy/pb-layout.service /etc/systemd/system/
# 修改路径
sudo systemctl daemon-reload
sudo systemctl enable pb-layout
sudo systemctl start pb-layout
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 微信登录 |
| POST | `/api/v1/layout` | AI 排版 |
| GET | `/api/v1/themes` | 主题列表 |
| GET | `/api/v1/accounts/active` | 当前推广公众号 |
| POST | `/api/v1/verify` | 验证码校验 |
| POST | `/api/v1/wechat/callback/{id}` | 公众号回调 |
| GET | `/api/v1/health` | 健康检查 |

## 许可证

MIT License
