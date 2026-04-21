# 🚀 Jabobo 后端管理系统 (FastAPI)

本项目是基于 **FastAPI** 架构的捷宝宝（Jabobo）后台服务，负责处理用户认证、设备绑定、人设配置及记忆同步。

## 🛠 项目架构

后端采用模块化路由设计，核心逻辑分布如下：

* **认证 (`auth.py`)**: 负责用户登录、Token 验证。
* **用户管理 (`users.py`)**: 后台管理账号的增删改查。
* **配置管理 (`jabobo_config.py`)**: 负责 AI 人设（Persona）与记忆（Memory）的读取与同步。
* **捷宝宝管理 (`jabobo_manager.py`)**: 负责设备的绑定（Bind）、解绑（Unbind）与换绑（Rebind）。

---

## 📚 API 路由总览

主应用在 `app/main.py` 中统一通过 `app.include_router(..., prefix="/api")` 注册路由，因此以下接口的完整前缀均为 `/api`。

### 认证模块 (`auth.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/login` | 用户登录，签发对应端 Token |
| `POST` | `/api/logout` | 当前端登出，清除当前端 Token |
| `POST` | `/api/logout/all` | 全端登出，清除所有端 Token |

### 用户管理模块 (`users.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/users` | 获取后台用户列表 |
| `POST` | `/api/users/{username}` | 删除指定用户及其配置 |
| `PUT` | `/api/users/password` | 修改用户密码 |
| `POST` | `/api/users` | 创建新用户 |

### 配置与设备管理模块 (`jabobo_config.py` / `jabobo_manager.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/user/config` | 获取设备配置 / 用户配置 |
| `POST` | `/api/user/sync-config` | 同步设备人设与记忆 |
| `GET` | `/api/user/jabobo_ids` | 获取用户已绑定的设备 ID 列表 |
| `POST` | `/api/user/bind` | 绑定新设备 |
| `DELETE` | `/api/user/unbind` | 解绑设备 |
| `PUT` | `/api/user/rebind` | 设备换绑并迁移数据 |

### 设备端接口模块 (`device_data_api.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/user/device/full_data` | 按设备 ID 获取全量设备数据，无需鉴权 |
| `PUT` | `/api/user/device/update_version` | 更新设备的 `current_version` 或 `expected_version` |
| `GET` | `/api/xiaozhi/otaMag/download/{filename}` | 下载 OTA 固件 |
| `HEAD` | `/api/xiaozhi/otaMag/download/{filename}` | 检查 OTA 固件是否存在，不返回文件体 |
| `POST` | `/api/user/device/ota` | 处理设备 OTA 请求，返回升级信息、激活信息和 websocket 地址 |
| `POST` | `/api/user/device/ota/activate` | 设备轮询激活状态 |

### 知识库模块 (`jabobo_knowlege.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/user/upload-kb` | 上传知识库文件 |
| `GET` | `/api/user/list-kb` | 获取知识库文件列表 |
| `POST` | `/api/user/delete-kb` | 删除知识库文件 |
| `POST` | `/api/user/generate-rag-prompt` | 根据知识库生成 RAG Prompt |

### 聊天配置模块 (`chat_config.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/config/server-base` | 获取服务端基础配置 |
| `POST` | `/api/config/agent-models` | 获取 Agent 模型配置 |
| `PUT` | `/api/agent/saveMemory/{mac_address}` | 保存设备短期记忆 |

### 声纹与音频模块 (`jabobo_voice.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/agent/chat-history/report` | 上报设备聊天历史和音频数据 |
| `POST` | `/api/user/upload-audio` | 上传音频文件 |
| `GET` | `/api/user/list-audio` | 获取音频文件列表 |
| `POST` | `/api/user/delete-audio` | 删除音频文件 |
| `POST` | `/api/voiceprint/register` | 注册声纹 |
| `GET` | `/api/voiceprint/list` | 获取声纹列表 |
| `POST` | `/api/voiceprint/delete` | 删除声纹 |

### APP 管理模块 (`app_management.py`)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/app/latest-version` | 获取最新 APP 版本信息 |
| `GET` | `/api/app/download` | 下载 APP 安装包 |
| `GET` | `/api/app/ios-plist` | 获取 iOS 安装描述文件 |

### 路由说明与注意事项

| 项目 | 说明 |
| --- | --- |
| 公共前缀 | 所有接口默认挂载在 `/api` 下 |
| 自动文档 | 启动服务后可通过 `/docs` 和 `/redoc` 查看接口详情 |
| 固件下载 | `/api/xiaozhi/otaMag/download/{filename}` 同时支持 `GET` 与 `HEAD` |
| 路由冲突 | `/api/user/config` 当前在 `jabobo_config.py` 和 `jabobo_manager.py` 中都定义了 `GET` 路由。按 `app/main.py` 的注册顺序，当前会先命中 `jabobo_config.py` 对应实现，后续建议统一路径语义 |

---

## 📂 快速启动

### 1. 数据库环境

确保 Docker 容器 `jabobo_final_mysql` 正在运行：

```bash
./db.sh start

```

### 2. 启动后端服务

在项目根目录下，执行以下命令（手动指定 **8007** 端口）：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload

```

*注：代码中的 `if __name__ == "__main__"` 默认端口为 5000，但在命令行中通过 `--port 8007` 启动会覆盖该设置，建议以 8007 为准。*

### 3. 在线文档

服务启动后，访问以下地址查看自动生成的 API 交互文档：

* **Swagger UI**: `http://localhost:8007/docs`
* **ReDoc**: `http://localhost:8007/redoc`

---

## 🖥 数据库维护工具 (`db.sh`)

项目目录下内置了 `db.sh` 脚本，封装了对 MySQL 的常用操作：

| 指令 | 说明 |
| --- | --- |
| `./db.sh index` | 检查 `user_personas` 表索引（排查数据冲突关键） |
| `./db.sh list` | 查看当前所有设备绑定的详细数据 |
| `./db.sh users` | 查看当前后台所有管理员账号 |
| `./db.sh "SQL"` | 执行自定义 SQL 命令 |
| `./db.sh` | 进入交互式 MySQL 终端 |

---



## ⚠️ 开发与部署注意事项

### 1. 跨域配置 (CORS)

当前配置允许 **所有来源 (`*`)** 访问。在生产环境下部署时，建议在 `app.add_middleware` 中将 `allow_origins` 限制为前端的实际域名。

### 2. 端口占用排查

如果 8007 端口无法启动，请使用以下工具清理进程：

```bash
lsof -i:8007
kill -9 <PID>

```

### 3. OTA 固件与 APP 安装包路径

固件文件（`.bin`）和 APP 安装包（`.apk`/`.ipa`）的存储路径通过环境变量配置：

| 环境变量 | 本地默认值 | 用途 |
| --- | --- | --- |
| `OTA_DIR` | `OTA`（仓库目录） | OTA 固件文件存放路径 |
| `APP_PACKAGE_DIR` | `app/app_packages`（仓库目录） | APK/IPA 安装包存放路径 |

**本地开发**：`.env` 中配置为仓库内的相对路径（如 `OTA_DIR=OTA`），文件直接放在仓库中。

**ACA 部署**：配置 Azure volume mount，将存储盘挂载到容器内（如 `/mnt/ota`），然后设置环境变量 `OTA_DIR=/mnt/ota`、`APP_PACKAGE_DIR=/mnt/app_packages`。这样更新固件或安装包时只需替换挂载盘中的文件，无需重新构建镜像。

### 4. 数据库表修复

若发现 `rebind`（换绑）操作导致数据异常，请运行此命令确保联合唯一索引存在：

```bash
./db.sh "ALTER TABLE user_personas ADD UNIQUE KEY uk_user_device (username, jabobo_id);"

```