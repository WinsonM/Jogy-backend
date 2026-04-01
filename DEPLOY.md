# Jogy Backend 部署指南

## 目录

1. [架构总览](#架构总览)
2. [本地开发部署](#本地开发部署)
3. [服务器生产部署](#服务器生产部署)
4. [各服务说明](#各服务说明)
5. [SMTP 邮件配置](#smtp-邮件配置)
6. [SSL 证书配置](#ssl-证书配置)
7. [Flutter 前端连接配置](#flutter-前端连接配置)
8. [常用运维命令](#常用运维命令)
9. [故障排查](#故障排查)

---

## 架构总览

```
                    ┌─────────────────────────────┐
                    │         Nginx (443/80)       │
                    │  - HTTPS 终端               │
                    │  - 静态文件 /uploads/        │
                    │  - WebSocket 代理            │
                    │  - API 反向代理 + 限流        │
                    └──────┬──────────┬────────────┘
                           │          │
              ┌────────────▼──┐  ┌────▼────────────┐
              │ FastAPI (8000)│  │ /uploads/ 目录   │
              │ - REST API    │  │ (Nginx 直接服务) │
              │ - WebSocket   │  └─────────────────┘
              └──┬────────┬───┘
                 │        │
        ┌────────▼──┐  ┌──▼────────┐
        │ PostgreSQL │  │   Redis   │
        │ + PostGIS  │  │  (缓存/   │
        │  (5432)    │  │  验证码/  │
        │            │  │  位置)    │
        └────────────┘  └───────────┘
```

**服务清单：**

| 服务 | 镜像/技术 | 端口 | 作用 |
|------|----------|------|------|
| **Nginx** | nginx:alpine | 80, 443 | HTTPS, 反向代理, 静态文件, WebSocket |
| **Backend** | Python 3.12 + FastAPI | 8000 | REST API + WebSocket |
| **PostgreSQL** | postgis/postgis:16-3.4 | 5432 | 主数据库 + 地理空间查询 |
| **Redis** | redis:7-alpine | 6379 | 验证码存储, 位置缓存, 限流 |

---

## 本地开发部署

### 前置要求

- Docker Desktop（已安装）
- Python 3.10+（已安装）
- Git

### 步骤

```bash
# 1. 进入项目目录
cd ~/Desktop/Jogy-backend

# 2. 复制环境配置
cp .env.example .env
# 编辑 .env，填入你的配置（本地开发可保持默认值）

# 3. 启动 PostgreSQL + Redis
docker compose up -d

# 4. 等待服务启动（约 5-10 秒）
docker compose ps
# 确认两个服务都是 healthy 状态

# 5. 安装 Python 依赖
pip install -e ".[dev]"

# 6. 运行数据库迁移
alembic upgrade head

# 7. 启动后端开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 8. 验证
# 浏览器打开 http://localhost:8000/docs  —— 看到 Swagger UI 即成功
# 浏览器打开 http://localhost:8000/health —— 看到 {"status": "healthy"}
```

### 本地开发时前端连接

```dart
// lib/core/constants/api_constants.dart
// iOS 模拟器:
static const String baseUrl = 'http://localhost:8000/api/v1';
// Android 模拟器:
static const String baseUrl = 'http://10.0.2.2:8000/api/v1';
// 真机调试（替换为你电脑的局域网 IP）:
static const String baseUrl = 'http://192.168.x.x:8000/api/v1';
```

---

## 服务器生产部署

### 推荐服务器配置（小体量）

- **云服务商：** 阿里云 / 腾讯云 / AWS Lightsail
- **最低配置：** 2核 CPU, 2GB RAM, 40GB SSD
- **系统：** Ubuntu 22.04 LTS
- **预算参考：** 阿里云轻量 ~60元/月, AWS Lightsail ~$5/月

### 第一步：服务器初始化

```bash
# SSH 登录服务器
ssh root@your-server-ip

# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh
# 安装 Docker Compose (已包含在新版 Docker 中)

# 创建部署用户（可选但推荐）
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
su - deploy
```

### 第二步：上传代码

```bash
# 方式一：Git（推荐）
# 在服务器上
cd ~
git clone https://github.com/your-username/Jogy-backend.git
cd Jogy-backend

# 方式二：SCP 直传
# 在本地
scp -r ~/Desktop/Jogy-backend deploy@your-server-ip:~/Jogy-backend
```

### 第三步：配置环境变量

```bash
cd ~/Jogy-backend
cp .env.example .env
```

**编辑 `.env` 文件，必须修改以下项：**

```bash
# 关闭调试模式
DEBUG=false

# 数据库密码（设一个强密码）
POSTGRES_PASSWORD=这里换成你的强密码

# JWT 密钥（必须更换！运行下面命令生成）
# python3 -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_SECRET_KEY=生成的随机字符串粘贴在这里

# API 签名密钥
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
API_SIGNATURE_SECRET=另一个随机字符串

# Redis 密码
REDIS_PASSWORD=设一个Redis密码

# SMTP 配置（参见下方 SMTP 章节）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 第四步：配置 Nginx 域名

```bash
# 编辑 nginx 配置，替换域名
sed -i 's/your-domain.com/你的实际域名/g' nginx/nginx.conf
```

### 第五步：申请 SSL 证书

```bash
# 先注释掉 nginx.conf 中的 443 server 块，只保留 80 端口
# 然后启动服务获取证书

# 安装 certbot
apt install certbot -y

# 创建 SSL 目录
mkdir -p nginx/ssl

# 获取 Let's Encrypt 证书
certbot certonly --standalone -d 你的域名 \
  --email your-email@example.com --agree-tos

# 复制证书到项目目录
cp /etc/letsencrypt/live/你的域名/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/你的域名/privkey.pem nginx/ssl/

# 设置自动续期（证书 90 天过期）
crontab -e
# 添加一行：
# 0 3 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/你的域名/*.pem ~/Jogy-backend/nginx/ssl/ && docker compose -f docker-compose.prod.yml restart nginx
```

### 第六步：启动全部服务

```bash
# 构建并启动（首次）
docker compose -f docker-compose.prod.yml up -d --build

# 等待所有服务 healthy
docker compose -f docker-compose.prod.yml ps

# 运行数据库迁移
docker compose -f docker-compose.prod.yml exec backend \
  alembic upgrade head

# 验证
curl https://你的域名/health
# 应返回 {"status": "healthy"}
```

### 第七步：更新前端连接地址

```dart
// lib/core/constants/api_constants.dart
static const String baseUrl = 'https://你的域名/api/v1';
```

WebSocket 连接：
```dart
// wss://你的域名/api/v1/ws?token=xxx
```

---

## 各服务说明

### PostgreSQL + PostGIS

- **作用：** 主数据库，存储用户、帖子、评论、消息等所有业务数据
- **PostGIS 扩展：** 提供地理空间索引（GIST），用于 Discover 功能的 viewport 帖子查询
- **数据持久化：** Docker volume `postgres_data`，容器重建不丢数据
- **备份：**
  ```bash
  # 手动备份
  docker compose -f docker-compose.prod.yml exec postgres \
    pg_dump -U postgres jogy > backup_$(date +%Y%m%d).sql

  # 恢复
  cat backup_20260331.sql | docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U postgres jogy
  ```

### Redis

- **作用：**
  - 邮件验证码存储（5 分钟 TTL）
  - 用户位置 geo-index（实时位置同步）
  - API 限流计数器（token bucket）
  - 通用缓存
- **数据持久化：** Docker volume `redis_data`（RDB 快照）
- **生产建议：** 设置密码（`REDIS_PASSWORD`）

### FastAPI Backend

- **作用：** 所有业务逻辑、REST API、WebSocket
- **运行方式：** Uvicorn ASGI server，2 个 worker 进程
- **上传文件：** 存储到 `/app/uploads/` 目录（Docker volume）
- **WebSocket：** 单进程内存管理连接，适合小体量
- **日志查看：**
  ```bash
  docker compose -f docker-compose.prod.yml logs -f backend
  ```

### Nginx

- **作用：**
  - HTTPS 终端（TLS 1.2/1.3）
  - HTTP → HTTPS 自动跳转
  - 反向代理 API 请求到 backend:8000
  - WebSocket 代理（长连接）
  - 直接提供 `/uploads/` 静态文件（不经过 Python，性能更好）
  - 请求限流（30 req/s per IP）
- **为什么需要 Nginx：**
  - Uvicorn 不适合直接暴露到公网
  - 静态文件由 Nginx 直接提供，吞吐量远高于 Python
  - SSL 终端、安全头、限流都由 Nginx 处理

---

## SMTP 邮件配置

### 方案一：Gmail（推荐国际用户）

1. 登录 Google Account → 安全性 → 两步验证（必须开启）
2. 安全性 → 应用专用密码 → 生成一个 16 位密码
3. 配置：
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=生成的16位应用专用密码
   ```

### 方案二：QQ 邮箱（推荐国内用户）

1. 登录 QQ 邮箱 → 设置 → 账户 → POP3/SMTP 服务 → 开启
2. 获取授权码
3. 配置：
   ```
   SMTP_HOST=smtp.qq.com
   SMTP_PORT=587
   SMTP_USER=你的QQ号@qq.com
   SMTP_PASSWORD=获取的授权码
   ```

### 方案三：163 邮箱

```
SMTP_HOST=smtp.163.com
SMTP_PORT=587
SMTP_USER=your-email@163.com
SMTP_PASSWORD=授权码
```

---

## SSL 证书配置

### 方案一：Let's Encrypt（免费，推荐）

需要一个域名指向你的服务器 IP。参见上方「第五步」。

### 方案二：暂不配置 SSL（仅本地/测试）

如果暂时不需要 HTTPS，修改 `nginx/nginx.conf`：
- 删除 443 server 块
- 80 server 块的 `return 301` 改为反向代理配置
- 前端用 `http://` 连接

**注意：** 生产环境必须使用 HTTPS，否则：
- iOS App Transport Security 会阻止 HTTP 请求
- 密码和 token 在传输中明文暴露

---

## Flutter 前端连接配置

部署完成后，修改前端一个文件即可连接到服务器：

```dart
// lib/core/constants/api_constants.dart

class ApiConstants {
  // 正式环境
  static const String baseUrl = 'https://你的域名/api/v1';

  // ...其余不变
}
```

WebSocket 连接（在 chat_page.dart 中使用时）：
```dart
final wsUrl = 'wss://你的域名/api/v1/ws?token=$accessToken';
```

上传的图片 URL 格式：
```
https://你的域名/uploads/images/20260331_abc123.jpg
```

---

## 常用运维命令

```bash
# ---- 服务管理 ----
# 查看所有服务状态
docker compose -f docker-compose.prod.yml ps

# 查看日志（实时跟踪）
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx

# 重启单个服务
docker compose -f docker-compose.prod.yml restart backend

# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 停止并删除数据（危险！）
docker compose -f docker-compose.prod.yml down -v


# ---- 代码更新 ----
# 拉取最新代码
git pull origin main

# 重新构建并启动（不停机）
docker compose -f docker-compose.prod.yml up -d --build backend

# 运行新的数据库迁移
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head


# ---- 数据库 ----
# 进入 PostgreSQL 交互终端
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres jogy

# 备份数据库
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres jogy | gzip > backup_$(date +%Y%m%d).sql.gz

# 查看数据库大小
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('jogy'));"


# ---- Redis ----
# 进入 Redis 终端
docker compose -f docker-compose.prod.yml exec redis redis-cli

# 查看所有验证码
docker compose -f docker-compose.prod.yml exec redis redis-cli KEYS "verify:*"


# ---- 磁盘 ----
# 查看上传文件大小
du -sh uploads/

# 清理 Docker 无用镜像
docker system prune -f
```

---

## 故障排查

### 问题：backend 启动失败

```bash
# 查看详细日志
docker compose -f docker-compose.prod.yml logs backend

# 常见原因：
# 1. 数据库连接失败 → 检查 POSTGRES_PASSWORD 是否一致
# 2. Redis 连接失败 → 检查 REDIS_URL 和 REDIS_PASSWORD
# 3. 端口冲突 → netstat -tlnp | grep 8000
```

### 问题：Nginx 502 Bad Gateway

```bash
# backend 可能还没启动完成
docker compose -f docker-compose.prod.yml ps
# 确认 backend 状态为 healthy

# 或者 backend 崩溃了
docker compose -f docker-compose.prod.yml logs backend --tail 50
```

### 问题：WebSocket 连接失败

```bash
# 确认 Nginx WebSocket 代理配置正确
# 检查 nginx/nginx.conf 中 /api/v1/ws 的 proxy_pass 配置

# 测试 WebSocket（需安装 wscat）
npm install -g wscat
wscat -c "wss://你的域名/api/v1/ws?token=你的token"
```

### 问题：邮件发送失败

```bash
# 进入 backend 容器测试
docker compose -f docker-compose.prod.yml exec backend python3 -c "
import asyncio, aiosmtplib
from email.message import EmailMessage
msg = EmailMessage()
msg['Subject'] = 'Test'
msg['From'] = 'your@email.com'
msg['To'] = 'your@email.com'
msg.set_content('Test email')
asyncio.run(aiosmtplib.send(msg, hostname='smtp.gmail.com', port=587,
    username='your@email.com', password='your-app-password', start_tls=True))
print('OK')
"
```

### 问题：上传的图片无法访问

```bash
# 检查文件是否存在
docker compose -f docker-compose.prod.yml exec backend ls -la uploads/images/

# 检查 Nginx 是否能读取
docker compose -f docker-compose.prod.yml exec nginx ls -la /app/uploads/images/

# 确认 volume 挂载正确
docker compose -f docker-compose.prod.yml exec nginx cat /etc/nginx/nginx.conf | grep uploads
```
