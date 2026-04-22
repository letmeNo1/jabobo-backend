from app.utils.logger import logger 

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import (
    auth, users, jabobo_config, jabobo_manager, 
    device_data_api, jabobo_knowlege, chat_config, 
    jabobo_voice, app_management
)

# --- 1. 定义禁用缓存中间件 ---
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Vary"] = "Authorization, x-username"
        return response

# 实例化 FastAPI
app = FastAPI(title="Jobobo API")

# 记录启动日志
logger.success("✨ Jabobo API 模块加载完成，正在挂载路由...")

# --- 2. 挂载中间件 ---
app.add_middleware(NoCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. 注册所有模块路由 ---
app.include_router(auth.router, prefix="/api", tags=["认证"])
app.include_router(users.router, prefix="/api", tags=["用户管理"])
app.include_router(jabobo_config.router, prefix="/api", tags=["配置管理"]) 
app.include_router(jabobo_manager.router, prefix="/api", tags=["捷宝宝管理"]) 
app.include_router(device_data_api.router, prefix="/api", tags=["设备端请求管理"]) 
app.include_router(jabobo_knowlege.router, prefix="/api", tags=["知识库管理"])
app.include_router(chat_config.router, prefix="/api", tags=["聊天差异化配置"]) 
app.include_router(jabobo_voice.router, prefix="/api", tags=["声纹管理"])
app.include_router(app_management.router, prefix="/api", tags=["APP管理"])

# 启动确认日志
logger.info("✅ 所有 API 路由注册完成，准备接收请求。")

if __name__ == "__main__":
    import uvicorn
    # 这里的端口建议与脚本中的 8007 保持一致
    uvicorn.run(app, host="0.0.0.0", port=8007)