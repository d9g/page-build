# -*- coding: utf-8 -*-
"""
公众号排版小程序 — FastAPI 后端入口
注册路由、中间件、CORS、启动/关闭事件
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from config import settings
from database import db

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ===== 生命周期管理 =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭时的初始化/清理工作
    """
    # 启动时
    logger.info("=" * 50)
    logger.info("公众号排版小程序后端启动中...")

    # 校验配置
    warnings = settings.validate()
    for w in warnings:
        logger.warning(f"⚠️  {w}")

    # 初始化数据库
    await db.connect()

    # 初始化 Redis
    try:
        import redis.asyncio as aioredis
        app.state.redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        await app.state.redis.ping()
        logger.info(f"✅ Redis 已连接: {settings.REDIS_URL}")
    except Exception as e:
        logger.warning(f"⚠️  Redis 连接失败，降级为内存模式: {e}")
        app.state.redis = None

    # 检查 Prompt 文件
    from services.prompt_manager import prompt_manager
    try:
        _, version = prompt_manager.get_system_prompt()
        logger.info(f"✅ Prompt 已加载，当前版本: {version}")
    except FileNotFoundError as e:
        logger.error(f"❌ Prompt 加载失败: {e}")

    # 打印公众号池
    pool = settings.get_account_pool()
    logger.info(f"✅ 公众号池: {len(pool)} 个账号")
    for acc in pool:
        logger.info(f"   - {acc['name']} ({acc['id']})")

    logger.info(f"✅ 服务地址: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info("=" * 50)

    yield

    # 关闭时
    if app.state.redis:
        await app.state.redis.close()
    await db.close()
    logger.info("后端已关闭")


# ===== 创建 FastAPI 应用 =====
app = FastAPI(
    title="公众号排版小程序 API",
    description="AI 智能排版工具后端服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ===== CORS 配置 =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [f"https://{settings.DOMAIN}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 静态文件 =====
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
(settings.STATIC_DIR / "avatars").mkdir(exist_ok=True)
(settings.STATIC_DIR / "qrcodes").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# ===== 注册路由 =====
from api.layout import router as layout_router
from api.themes import router as themes_router
from api.auth import router as auth_router
from api.verify import router as verify_router
from api.accounts import router as accounts_router
from api.wechat import router as wechat_router
from api.admin import router as admin_router

app.include_router(layout_router)
app.include_router(themes_router)
app.include_router(auth_router)
app.include_router(verify_router)
app.include_router(accounts_router)
app.include_router(wechat_router)
app.include_router(admin_router)


# ===== 健康检查 =====
@app.get("/api/v1/health", tags=["系统"])
async def health_check():
    """健康检查接口，用于部署监控"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "domain": settings.DOMAIN,
    }


# ===== 启动入口 =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
    )
