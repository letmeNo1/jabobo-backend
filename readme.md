# 🚀 Jabobo 后端管理系统 (FastAPI)

本项目是基于 **FastAPI** 架构的捷宝宝（Jabobo）后台服务，负责处理用户认证、设备绑定、人设配置及记忆同步。

## 🛠 项目架构

后端采用模块化路由设计，核心逻辑分布如下：

* **认证 (`auth.py`)**: 负责用户登录、Token 验证。
* **用户管理 (`users.py`)**: 后台管理账号的增删改查。
* **配置管理 (`jabobo_config.py`)**: 负责 AI 人设（Persona）与记忆（Memory）的读取与同步。
* **捷宝宝管理 (`jabobo_manager.py`)**: 负责设备的绑定（Bind）、解绑（Unbind）与换绑（Rebind）。

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

### 3. 数据库表修复

若发现 `rebind`（换绑）操作导致数据异常，请运行此命令确保联合唯一索引存在：

```bash
./db.sh "ALTER TABLE user_personas ADD UNIQUE KEY uk_user_device (username, jabobo_id);"

```