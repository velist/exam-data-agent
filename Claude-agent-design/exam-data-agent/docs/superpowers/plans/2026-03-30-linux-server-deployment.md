# 考试宝典数据助手 — Linux 服务器部署计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 exam-data-agent 后端服务部署到内网 Linux 服务器 (172.10.10.26)，提供完整的 API + 前端 SPA 服务。

**Architecture:** 通过 SSH/SCP 将代码上传至 Linux 服务器，使用 Python venv 隔离依赖，uvicorn 直接运行 FastAPI 服务，systemd 守护进程实现开机自启。前端构建产物由 FastAPI 直接 serve。

**Tech Stack:** Python 3.12 / FastAPI / uvicorn / systemd / SCP

---

## 服务器环境

| 项目 | 值 |
|------|-----|
| OS | Ubuntu 24.04.3 LTS |
| CPU | Intel Core Ultra 9 285K (24c) |
| RAM | 188GB |
| Disk | 1.8TB (9% used) |
| Python | 3.12.3 (无 pip) |
| Node.js | v22.22.0 |
| SSH | `ssh -p 2143 yingteng@172.10.10.26` / `ytjy1234` |
| systemd | 可用 |
| 目标端口 | 8230 (空闲) |

## 远程命令执行方式

所有远程操作通过 Python paramiko 库执行（Windows 本机无 sshpass）：

```python
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('172.10.10.26', port=2143, username='yingteng', password='ytjy1234')
stdin, stdout, stderr = ssh.exec_command('command')
```

文件传输使用 paramiko SFTP。

---

### Task 1: 安装 pip 并验证 Python 环境

**目标:** 服务器上 python3 可用 pip，能创建 venv。

- [ ] **Step 1: 安装 pip**

```bash
# 远程执行
curl -sS https://bootstrap.pypa.io/get-pip.py | python3
```

- [ ] **Step 2: 验证 pip 和 venv**

```bash
python3 -m pip --version
python3 -m venv --help | head -1
```

Expected: pip 版本号 + venv 帮助信息

---

### Task 2: 创建项目目录并上传代码

**目标:** 将 backend/ 和 frontend/ 代码上传到 `/home/yingteng/exam-data-agent/`

- [ ] **Step 1: 创建远程目录**

```bash
mkdir -p ~/exam-data-agent
```

- [ ] **Step 2: 本地打包项目代码（排除 node_modules/dist/__pycache__）**

```bash
# 本地 Windows 执行
cd exam-data-agent
tar czf /tmp/exam-data-agent.tar.gz --exclude='node_modules' --exclude='dist' --exclude='__pycache__' --exclude='.wrangler' --exclude='query_cache' backend/ frontend/package.json frontend/package-lock.json frontend/src/ frontend/public/ frontend/vite.config.ts frontend/tsconfig*.json frontend/index.html
```

- [ ] **Step 3: SCP 上传并解压**

```python
# paramiko SFTP 上传 tar.gz
# 远程解压
cd ~/exam-data-agent && tar xzf exam-data-agent.tar.gz
```

- [ ] **Step 4: 验证文件结构**

```bash
ls ~/exam-data-agent/backend/main.py
ls ~/exam-data-agent/frontend/package.json
```

---

### Task 3: 创建 venv 并安装 Python 依赖

**目标:** 隔离的 Python 环境 + 所有 backend 依赖就绪

- [ ] **Step 1: 创建 venv**

```bash
cd ~/exam-data-agent && python3 -m venv venv
```

- [ ] **Step 2: 安装依赖**

```bash
cd ~/exam-data-agent && ./venv/bin/pip install -r backend/requirements.txt
```

- [ ] **Step 3: 验证关键包**

```bash
./venv/bin/python -c "import fastapi, uvicorn, sqlalchemy, pymysql; print('OK')"
```

Expected: `OK`

---

### Task 4: 构建前端

**目标:** 生成 frontend/dist 静态文件

- [ ] **Step 1: 安装 npm 依赖**

```bash
cd ~/exam-data-agent/frontend && npm install
```

- [ ] **Step 2: 设置 VITE_API_URL 并构建**

```bash
cd ~/exam-data-agent/frontend && npm run build
```

- [ ] **Step 3: 验证构建产物**

```bash
ls ~/exam-data-agent/frontend/dist/index.html
ls ~/exam-data-agent/frontend/dist/assets/
```

---

### Task 5: 配置环境变量

**目标:** 创建 .env 文件，包含数据库和 API 密钥

- [ ] **Step 1: 询问用户获取 .env 内容或从本地读取**

需要的变量：
- `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- `QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL`

- [ ] **Step 2: 写入远程 .env**

```bash
cat > ~/exam-data-agent/.env << 'EOF'
DB_HOST=<host>
DB_PORT=3306
DB_USER=<user>
DB_PASSWORD=<password>
DB_NAME=dws
QWEN_API_KEY=<key>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
EOF
chmod 600 ~/exam-data-agent/.env
```

---

### Task 6: 测试运行服务

**目标:** 手动启动服务，验证 API 可达

- [ ] **Step 1: 启动 uvicorn**

```bash
cd ~/exam-data-agent/backend && ../venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8230
```

- [ ] **Step 2: 测试健康检查**

```bash
curl http://172.10.10.26:8230/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: 测试前端页面**

```bash
curl -s http://172.10.10.26:8230/ | head -5
```

Expected: HTML 包含 `考试宝典数据助手`

---

### Task 7: 配置 systemd 服务守护

**目标:** 服务开机自启 + 崩溃自动重启

- [ ] **Step 1: 创建 systemd service 文件**

```ini
# /etc/systemd/system/exam-data-agent.service
[Unit]
Description=Exam Data Agent API Server
After=network.target

[Service]
Type=simple
User=yingteng
WorkingDirectory=/home/yingteng/exam-data-agent/backend
EnvironmentFile=/home/yingteng/exam-data-agent/.env
ExecStart=/home/yingteng/exam-data-agent/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8230
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: 启用并启动服务**

```bash
sudo systemctl daemon-reload
sudo systemctl enable exam-data-agent
sudo systemctl start exam-data-agent
```

- [ ] **Step 3: 验证服务状态**

```bash
systemctl status exam-data-agent
curl http://172.10.10.26:8230/api/health
```

---

### Task 8 (可选): Nginx 反向代理

**目标:** 如果需要 80/443 端口访问或 SSL，配置 nginx

暂跳过 — 内网直接用 8230 端口即可。后续需要时再添加。

---

## 部署后访问地址

- 内网 API: `http://172.10.10.26:8230/api/`
- 内网前端: `http://172.10.10.26:8230/`
- 健康检查: `http://172.10.10.26:8230/api/health`
