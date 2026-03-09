# IPTV 组播流媒体质量实时监测系统

一个完整的300路组播流媒体质量实时监测系统，支持：

- **Python探针层**：300路并发 UDP 组播接收，MPEG-TS 解析（PAT/PMT/SDT/EIT），黑屏/冻屏/静音/爆音/丢包/CC错误/PCR抖动/码率异常检测
- **存储层**：InfluxDB（时序指标）+ SQLite（频道配置/告警历史）+ Redis（实时状态缓存）
- **FastAPI 后端**：REST API + WebSocket 实时推送
- **Vue3 Web 大屏**：ECharts 实时图表，300路节目4色交通灯状态
- **音频告警**：Web Speech API TTS 语音播报，5分钟抑制 + 多路聚合
- **缩略图**：每5秒截取，告警时刻截图永久保留
- **仿真模式**：本地视频文件模拟组播源，可手动触发各类故障
- **Docker Compose**：一键部署所有服务

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  UDP 组播源 (239.1.1.1 ~ 239.1.2.44, port 1234)            │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │  Probe 服务 (10进程)   │
         │  每进程 30路 asyncio  │
         │  TS解析/视频/音频分析  │
         └──┬──────────┬────────┘
            │          │
     ┌──────▼──┐  ┌───▼──────┐
     │InfluxDB │  │  Redis   │
     │时序数据  │  │实时状态   │
     └──────┬──┘  └───┬──────┘
            │         │ Pub/Sub
         ┌──▼─────────▼────┐
         │  FastAPI 后端    │
         │  REST API       │
         │  WebSocket      │
         └──────┬──────────┘
                │
         ┌──────▼──────────┐
         │  Vue3 前端大屏   │
         │  ECharts图表     │
         │  TTS语音告警     │
         └─────────────────┘
```

## 部署方式

本系统支持两种部署方式：

| 部署方式 | 适用场景 | 优点 | 缺点 |
|---------|---------|------|------|
| **Docker Compose** | 生产环境、快速部署 | 环境一致、易于管理、一键启动 | 需要安装 Docker |
| **独立部署** | 开发调试、资源受限 | 灵活可控、无需容器 | 配置较复杂、依赖管理 |

---

## 方式一：Docker Compose 一键部署（推荐生产环境）

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 宿主机支持 IP 组播（用于接收 UDP 组播流）
- 至少 4GB 可用内存
- 至少 20GB 可用磁盘空间

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd iptv-monitor

# 创建数据目录
mkdir -p data/db data/thumbnails data/videos

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，修改 INFLUXDB_PASSWORD 等敏感配置
```

**环境变量说明：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INFLUXDB_PASSWORD` | (必填) | InfluxDB 管理员密码 |
| `INFLUXDB_TOKEN` | `iptv-monitor-super-secret-token-2024` | InfluxDB 访问令牌 |
| `INFLUXDB_ORG` | `iptv` | InfluxDB 组织名 |
| `INFLUXDB_BUCKET` | `metrics` | InfluxDB 存储桶名 |
| `WORKER_COUNT` | `10` | 探针 Worker 进程数 |
| `CHANNELS_PER_WORKER` | `30` | 每个 Worker 处理的频道数 |

### 2. 初始化数据库

```bash
# 初始化 SQLite 数据库和 300 路频道配置
docker compose run --rm api python3 /app/scripts/init_db.py
```

### 3. 准备仿真测试视频（可选）

如果使用仿真模式（无真实组播源），需要准备测试视频：

```bash
# 使用 ffmpeg 生成测试视频
ffmpeg -f lavfi -i testsrc=duration=600:size=1280x720:rate=25 \
       -f lavfi -i sine=frequency=1000:duration=600 \
       -c:v libx264 -crf 23 -c:a aac \
       data/videos/testsrc.mp4

# 或使用已有视频文件
cp /path/to/your/test.mp4 data/videos/
```

### 4. 配置组播网络

探针服务使用 `network_mode: host` 接收组播流，需确保宿主机配置正确：

```bash
# 确认宿主机组播路由
ip route show 224.0.0.0/4

# 若未配置，添加组播路由（替换 eth0 为实际网卡名）
ip route add 224.0.0.0/4 dev eth0

# 防火墙开放 UDP 1234 端口
iptables -I INPUT -p udp --dport 1234 -j ACCEPT
# 或使用 firewalld
firewall-cmd --add-port=1234/udp --permanent
firewall-cmd --reload
```

**注意事项：**
- 组播路由配置在重启后会丢失，建议添加到 `/etc/rc.local` 或网络配置文件中
- 如果宿主机有多个网卡，需确保组播流从正确的网卡进入

### 5. 启动所有服务

```bash
# 构建并启动所有服务
docker compose up -d

# 查看启动日志
docker compose logs -f

# 查看服务状态
docker compose ps
```

服务启动顺序（自动处理）：
1. InfluxDB → 2. Redis → 3. Probe/API → 4. Frontend

### 6. 验证运行状态

```bash
# 检查服务健康状态
docker compose ps

# 检查 API 健康端点
curl http://localhost:8000/health

# 检查频道数据
curl http://localhost:8000/api/v1/channels | jq '.[0]'

# 检查实时状态（需在仿真模式或有真实组播源时才有数据）
curl http://localhost:8000/api/v1/channels/stats/overview
```

### 7. 访问系统

服务启动成功后，可通过以下地址访问：

- **大屏前端**：http://localhost
- **API 接口**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs
- **InfluxDB 管理界面**：http://localhost:8086
  - 用户名：`admin`
  - 密码：`.env` 文件中配置的 `INFLUXDB_PASSWORD`

### 常用运维命令

```bash
# 停止所有服务
docker compose stop

# 启动所有服务
docker compose start

# 重启某个服务
docker compose restart probe

# 查看日志
docker compose logs -f probe
docker compose logs -f api

# 更新镜像并重新部署
docker compose pull
docker compose up -d --build

# 清理所有数据（谨慎操作）
docker compose down -v
```

---

## 方式二：非 Docker 独立部署（开发/调试环境）

### 前置要求

- **Python 3.12+**（用于 probe 和 api 服务）
- **Node.js 20+**（用于前端构建）
- **ffmpeg 5.0+**（用于视频分析和截帧）
- **SQLite 3**（数据库）
- **Redis 7+**（实时状态缓存）
- **InfluxDB 2.7+**（时序数据存储）
- **Nginx**（可选，用于前端服务）

### 1. 安装系统依赖

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install -y python3.12 python3-pip python3-venv \
                     nodejs npm \
                     ffmpeg \
                     sqlite3 \
                     redis-server \
                     nginx

# 安装 InfluxDB 2.7
wget -q https://repos.influxdata.com/influxdata-archive_compat.key
cat influxdata-archive_compat.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg > /dev/null
echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg] https://repos.influxdata.com/debian stable main' | sudo tee /etc/apt/sources.list.d/influxdata.list
sudo apt update
sudo apt install -y influxdb2
sudo systemctl enable influxdb
sudo systemctl start influxdb
```

**CentOS/RHEL:**

```bash
sudo yum install -y python3.12 python3-pip \
                     nodejs npm \
                     ffmpeg \
                     sqlite \
                     redis \
                     nginx

# 安装 InfluxDB 2.7
sudo yum install -y https://dl.influxdata.com/influxdb/releases/influxdb2-2.7.10.x86_64.rpm
sudo systemctl enable influxdb
sudo systemctl start influxdb
```

### 2. 配置基础服务

**配置 InfluxDB:**

```bash
# 启动 InfluxDB
sudo systemctl start influxdb

# 初始化 InfluxDB（首次运行）
influx setup \
  --username admin \
  --password your_secure_password \
  --org iptv \
  --bucket metrics \
  --token iptv-monitor-super-secret-token-2024 \
  --force

# 验证连接
influx ping
```

**配置 Redis:**

```bash
# 启动 Redis
sudo systemctl start redis-server

# 配置 Redis 内存限制（可选）
# 编辑 /etc/redis/redis.conf
# maxmemory 2gb
# maxmemory-policy allkeys-lru
sudo systemctl restart redis-server

# 验证连接
redis-cli ping
```

### 3. 部署探针服务（Probe）

```bash
# 创建探针目录
cd /opt
sudo mkdir -p iptv-monitor/probe
sudo chown $USER:$USER iptv-monitor/probe

# 复制探针代码（假设从项目目录）
cp -r /path/to/iptv-monitor/probe/* /opt/iptv-monitor/probe/

# 创建 Python 虚拟环境
cd /opt/iptv-monitor/probe
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建数据目录
sudo mkdir -p /data/db /data/thumbnails /data/videos
sudo chown -R $USER:$USER /data

# 初始化数据库
cd /opt/iptv-monitor
python3 scripts/init_db.py

# 设置环境变量（创建 .env 文件）
cat > /opt/iptv-monitor/probe/.env << 'EOF'
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=iptv-monitor-super-secret-token-2024
INFLUXDB_ORG=iptv
INFLUXDB_BUCKET=metrics
REDIS_URL=redis://localhost:6379
SQLITE_PATH=/data/db/iptv.db
THUMBNAIL_DIR=/data/thumbnails
SIM_VIDEO_DIR=/data/videos
WORKER_COUNT=10
CHANNELS_PER_WORKER=30
EOF

# 手动启动测试（前台运行）
cd /opt/iptv-monitor/probe
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

**配置 systemd 服务（生产环境）:**

```bash
# 创建运行用户
sudo useradd -r -s /bin/false iptv

# 复制 systemd 服务文件
sudo cp /opt/iptv-monitor/scripts/iptv-monitor-probe.service /etc/systemd/system/

# 修改服务文件中的路径和用户
sudo sed -i 's|/opt/iptv-monitor|/opt/iptv-monitor|g' /etc/systemd/system/iptv-monitor-probe.service

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable iptv-monitor-probe
sudo systemctl start iptv-monitor-probe

# 查看状态
sudo systemctl status iptv-monitor-probe

# 查看日志
sudo journalctl -u iptv-monitor-probe -f
```

### 4. 部署 API 服务

```bash
# 创建 API 目录
sudo mkdir -p /opt/iptv-monitor/api
sudo chown $USER:$USER /opt/iptv-monitor/api

# 复制 API 代码
cp -r /path/to/iptv-monitor/api/* /opt/iptv-monitor/api/

# 创建 Python 虚拟环境
cd /opt/iptv-monitor/api
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
cat > /opt/iptv-monitor/api/.env << 'EOF'
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=iptv-monitor-super-secret-token-2024
INFLUXDB_ORG=iptv
INFLUXDB_BUCKET=metrics
REDIS_URL=redis://localhost:6379
SQLITE_PATH=/data/db/iptv.db
THUMBNAIL_DIR=/data/thumbnails
EOF

# 手动启动测试（前台运行）
cd /opt/iptv-monitor/api
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**配置 systemd 服务（生产环境）:**

```bash
# 复制 systemd 服务文件
sudo cp /opt/iptv-monitor/scripts/iptv-monitor-api.service /etc/systemd/system/

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable iptv-monitor-api
sudo systemctl start iptv-monitor-api

# 查看状态
sudo systemctl status iptv-monitor-api

# 查看日志
sudo journalctl -u iptv-monitor-api -f
```

### 5. 部署前端服务

```bash
# 创建前端目录
sudo mkdir -p /opt/iptv-monitor/frontend
sudo chown $USER:$USER /opt/iptv-monitor/frontend

# 复制前端代码
cp -r /path/to/iptv-monitor/frontend/* /opt/iptv-monitor/frontend/

# 安装依赖
cd /opt/iptv-monitor/frontend
npm install

# 修改 API 地址（如果 API 部署在不同地址）
# 编辑 src/services/api.ts
# const API_BASE_URL = 'http://localhost:8000';

# 构建生产版本
npm run build

# 部署到 Nginx
sudo mkdir -p /var/www/iptv-monitor
sudo cp -r dist/* /var/www/iptv-monitor/
sudo chown -R www-data:www-data /var/www/iptv-monitor
```

**配置 Nginx:**

```bash
# 复制 Nginx 配置文件
sudo cp /opt/iptv-monitor/scripts/nginx-frontend.conf /etc/nginx/sites-available/iptv-monitor

# 启用站点
sudo ln -s /etc/nginx/sites-available/iptv-monitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. 配置组播网络

独立部署时，探针服务直接运行在宿主机上，组播网络配置与 Docker 部署相同：

```bash
# 确认宿主机组播路由
ip route show 224.0.0.0/4

# 若未配置，添加组播路由
ip route add 224.0.0.0/4 dev eth0

# 防火墙开放 UDP 1234 端口
iptables -I INPUT -p udp --dport 1234 -j ACCEPT

# 持久化组播路由（添加到 /etc/network/interfaces 或网络管理工具配置）
# 或添加到 /etc/rc.local
echo "ip route add 224.0.0.0/4 dev eth0" | sudo tee -a /etc/rc.local
chmod +x /etc/rc.local
```

### 7. 启动所有服务

```bash
# 按顺序启动
sudo systemctl start influxdb
sudo systemctl start redis-server
sudo systemctl start iptv-monitor-probe
sudo systemctl start iptv-monitor-api
sudo systemctl start nginx

# 验证服务状态
sudo systemctl status influxdb redis-server iptv-monitor-probe iptv-monitor-api nginx

# 测试 API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/channels
```

### 8. 访问系统

- **大屏前端**：http://localhost（或服务器 IP）
- **API 接口**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs
- **InfluxDB 管理界面**：http://localhost:8086

---

## 环境变量配置说明

### InfluxDB 相关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INFLUXDB_URL` | `http://localhost:8086` | InfluxDB 服务地址 |
| `INFLUXDB_TOKEN` | `iptv-monitor-super-secret-token-2024` | 访问令牌，生产环境务必修改 |
| `INFLUXDB_ORG` | `iptv` | 组织名 |
| `INFLUXDB_BUCKET` | `metrics` | 存储桶名 |

### Redis 相关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_URL` | `redis://localhost:6379` | Redis 服务地址 |

### 存储路径相关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLITE_PATH` | `/data/db/iptv.db` | SQLite 数据库文件路径 |
| `THUMBNAIL_DIR` | `/data/thumbnails` | 缩略图存储目录 |
| `SIM_VIDEO_DIR` | `/data/videos` | 仿真视频文件目录 |

### 探针服务相关

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WORKER_COUNT` | `10` | Worker 进程数，建议 4-16 |
| `CHANNELS_PER_WORKER` | `30` | 每个 Worker 处理的频道数，总频道数 = WORKER_COUNT × CHANNELS_PER_WORKER |

### 监测阈值（在 config.py 中）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `BLACK_LUMA_THRESHOLD` | `16` | 黑屏亮度阈值（0-255） |
| `FREEZE_MSE_THRESHOLD` | `0.5` | 冻屏 MSE 阈值 |
| `FREEZE_DURATION_SEC` | `10` | 冻屏持续时间阈值（秒） |
| `SILENCE_RMS_THRESHOLD` | `0.001` | 静音 RMS 阈值（0-1） |
| `SILENCE_DURATION_SEC` | `5` | 静音持续时间阈值（秒） |
| `CC_ERROR_THRESHOLD` | `5` | CC 错误率阈值（错误/秒） |
| `PCR_JITTER_THRESHOLD_MS` | `40.0` | PCR 抖动阈值（毫秒） |
| `BITRATE_DEVIATION_THRESHOLD` | `0.3` | 码率偏差阈值（30%） |

---

## 常见问题排查

### 1. 组播流接收不到

**症状：** 所有频道显示离线状态

**排查步骤：**

```bash
# 检查组播路由
ip route show 224.0.0.0/4

# 使用 tcpdump 捕获组播包验证
sudo tcpdump -i eth0 udp port 1234 -nn

# 检查防火墙
sudo iptables -L -n | grep 1234

# 检查网络接口
ip link show
```

**解决方案：**

- 确保添加了组播路由：`ip route add 224.0.0.0/4 dev eth0`
- 开放防火墙 UDP 1234 端口
- 确认组播源正常发送数据
- 检查网络交换机是否支持组播（IGMP Snooping）

### 2. InfluxDB 连接失败

**症状：** 探针或 API 启动失败，日志显示 InfluxDB 连接错误

**排查步骤：**

```bash
# 检查 InfluxDB 服务状态
sudo systemctl status influxdb
# Docker 部署
docker compose ps influxdb

# 测试 InfluxDB 连接
influx ping
curl http://localhost:8086/health

# 检查 InfluxDB 日志
sudo journalctl -u influxdb -f
# Docker 部署
docker compose logs influxdb -f
```

**解决方案：**

- 确认 InfluxDB 已正确初始化（运行过 `influx setup`）
- 检查环境变量中的 `INFLUXDB_TOKEN` 是否正确
- 检查 `INFLUXDB_URL` 地址是否可达
- Docker 部署时检查容器网络连接

### 3. Redis 连接失败

**症状：** 实时状态更新异常，WebSocket 推送失败

**排查步骤：**

```bash
# 检查 Redis 服务状态
sudo systemctl status redis-server
# Docker 部署
docker compose ps redis

# 测试 Redis 连接
redis-cli ping

# 检查 Redis 日志
sudo journalctl -u redis-server -f
```

**解决方案：**

- 确认 Redis 服务正常运行
- 检查 `REDIS_URL` 环境变量
- 检查 Redis 内存是否已满
- 检查 Redis 配置的最大连接数

### 4. 缩略图目录权限问题

**症状：** 探针日志显示无法写入缩略图

**排查步骤：**

```bash
# 检查目录权限
ls -la /data/thumbnails

# 检查运行用户
ps aux | grep probe
```

**解决方案：**

```bash
# 修改目录所有者
sudo chown -R iptv:iptv /data/thumbnails
# 或调整权限
sudo chmod -R 755 /data/thumbnails
```

### 5. 前端无法访问 API

**症状：** 前端页面空白或显示"连接失败"

**排查步骤：**

- 浏览器开发者工具 Network 面板查看 API 请求错误
- 检查 API 服务是否运行：`curl http://localhost:8000/health`
- 检查 Nginx 配置中的 API 代理设置
- 确认前端 API 地址配置是否正确（`src/services/api.ts`）

**解决方案：**

- 修改前端 API 地址为实际部署地址
- 检查 Nginx 配置文件中的 `proxy_pass` 设置
- 重启 Nginx：`sudo systemctl reload nginx`
- 重新构建前端：`npm run build`

### 6. 端口被占用

**症状：** 服务启动失败，提示端口已被使用

**排查步骤：**

```bash
# 检查端口占用
sudo lsof -i :80
sudo lsof -i :8000
sudo lsof -i :8086
sudo lsof -i :6379
```

**解决方案：**

- 停止占用端口的服务
- 或修改服务配置使用其他端口
- 或修改 docker-compose.yml 中的端口映射

### 7. 数据库初始化失败

**症状：** 运行 `init_db.py` 时报错

**排查步骤：**

```bash
# 检查 SQLite 目录权限
ls -la /data/db

# 手动运行初始化脚本并查看详细错误
python3 scripts/init_db.py
```

**解决方案：**

- 确保目录存在且可写：`mkdir -p /data/db && sudo chown $USER:$USER /data/db`
- 检查 Python 环境和依赖是否完整
- 确认数据库文件未被其他进程锁定

---

## 性能优化建议

### 1. 调整探针并发数

根据服务器 CPU 核心数调整 `WORKER_COUNT`：

- **4 核 CPU**：`WORKER_COUNT=4`
- **8 核 CPU**：`WORKER_COUNT=8`（默认）
- **16 核 CPU**：`WORKER_COUNT=16`

### 2. 优化 InfluxDB 存储

编辑 InfluxDB 配置（`/etc/influxdb/config.toml`）：

```toml
[data]
  cache-max-memory-size = "2g"

[coordinator]
  write-timeout = "10s"
```

### 3. 优化 Redis 内存

编辑 Redis 配置（`/etc/redis/redis.conf`）：

```
maxmemory 2gb
maxmemory-policy allkeys-lru
```

### 4. 调整视频采样频率

如果系统负载过高，可降低采样频率：

编辑 `probe/config.py`：

```python
FRAME_SAMPLE_INTERVAL_SEC = 10  # 默认 5 秒
```

### 5. 使用 SSD 存储

将 `data/` 目录迁移到 SSD 以提升 I/O 性能。

---

## 安全建议

1. **修改默认密码**：生产环境务必修改 `INFLUXDB_PASSWORD` 和 `INFLUXDB_TOKEN`
2. **启用 HTTPS**：使用 Nginx 配置 SSL/TLS 证书
3. **限制访问**：配置防火墙，仅允许必要的 IP 访问
4. **定期备份**：定期备份 `data/db/` 目录中的 SQLite 数据库
5. **日志审计**：启用系统日志审计，监控异常访问

---

## 下一步

部署完成后，请参考以下章节：

- **告警状态说明**：了解 4 种告警状态的含义
- **仿真故障注入**：使用仿真模式测试告警功能
- **API 接口**：了解可用的 REST API 和 WebSocket 接口

## 告警状态说明

| 状态 | 颜色 | 触发条件 |
|------|------|---------|
| 正常 (NORMAL) | 🟢 绿色 | 所有指标正常 |
| 注意 (WARNING) | 🟡 黄色 | CC错误>5/s、PCR抖动>40ms、码率偏差>30% |
| 告警 (ALARM) | 🔴 红色（闪烁） | 黑屏/冻屏/静音 |
| 离线 (OFFLINE) | ⚫ 灰色 | 2秒无UDP数据 |

## 仿真故障注入

通过 API 触发：

```bash
# 触发 ch001 黑屏 30秒
curl -X POST http://localhost:8000/api/v1/sim/trigger \
  -H 'Content-Type: application/json' \
  -d '{"channel_id": "ch001", "fault_type": "BLACK_SCREEN", "duration_sec": 30}'

# 清除故障
curl -X POST http://localhost:8000/api/v1/sim/clear \
  -d '{"channel_id": "ch001"}'
```

支持的故障类型：`BLACK_SCREEN` / `FROZEN` / `SILENT` / `PACKET_LOSS` / `BITRATE_DROP`

也可以通过大屏前端的"仿真测试"页面操作。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/channels` | 获取所有频道当前状态 |
| GET | `/api/v1/channels/{id}` | 获取单路频道状态 |
| GET | `/api/v1/channels/{id}/metrics?range=5m` | 获取历史指标（InfluxDB） |
| GET | `/api/v1/channels/stats/overview` | 统计汇总 |
| GET | `/api/v1/alerts` | 获取告警列表 |
| POST | `/api/v1/alerts/{id}/ack` | 告警确认 |
| GET | `/api/v1/thumbnails/{id}/latest` | 最新缩略图 |
| GET | `/api/v1/thumbnails/{id}/alarms` | 告警截图列表 |
| WS | `/ws/realtime` | 实时推送 WebSocket |

## 目录结构

```
iptv-monitor/
├── docker-compose.yml
├── .env.example          # 环境变量模板
├── .env                  # 环境变量配置（需创建）
├── probe/                # Python探针服务
│   ├── main.py           # 入口：10个Worker进程
│   ├── worker.py         # Worker：30路asyncio协程
│   ├── config.py         # 配置文件
│   ├── ts_parser.py      # TS包解析（PAT/PMT/SDT/EIT/CC/PCR）
│   ├── status_machine.py # 4级状态判定
│   ├── simulator.py      # 仿真模式
│   ├── analyzers/        # 视频/音频/码率/PCR分析器
│   └── storage/          # InfluxDB/Redis/SQLite写入器
├── api/                  # FastAPI后端
│   ├── main.py
│   ├── config.py         # 配置文件
│   ├── routers/          # REST API路由
│   ├── websocket/        # WebSocket管理器
│   ├── models/           # Pydantic模型
│   └── db/               # InfluxDB/Redis/SQLite客户端
├── frontend/             # Vue3大屏前端
│   └── src/
│       ├── components/   # ChannelGrid/Card/Chart/Alert组件
│       ├── stores/       # Pinia状态管理
│       └── composables/  # WebSocket/告警抑制
├── scripts/
│   ├── init_db.py        # 数据库初始化+300路配置
│   ├── iptv-monitor-probe.service  # systemd探针服务配置
│   ├── iptv-monitor-api.service    # systemd API服务配置
│   └── nginx-frontend.conf         # Nginx前端配置
└── data/
    ├── db/               # SQLite数据库
    ├── thumbnails/       # 缩略图文件
    └── videos/           # 仿真测试视频
```

## 性能说明

- **探针进程**：10个 multiprocessing.Process，每进程处理30路，每进程4个帧分析线程
- **视频分析**：每5秒采样1帧（可配置 `FRAME_SAMPLE_INTERVAL_SEC`）
- **指标写入**：每秒批量写入 InfluxDB（最多300 Points/批）
- **Redis状态**：每秒更新，TTL=30秒（超时自动标记为离线）
- **WebSocket**：Redis Pub/Sub 转发，支持多客户端同时连接
