# 考试宝典数据助手 — 开机启动指南

## 架构说明

```
ksdata.aipush.fun        →  CF Pages (静态前端，自动部署)
ksapi.aipush.fun         →  Cloudflare Tunnel  →  本机 localhost:8230 (FastAPI后端)
```

前端部署在 Cloudflare Pages，后端运行在本机，通过 Cloudflare Tunnel 对外暴露。

---

## 每次开机后需要手动启动两个服务

### 第一步：启动后端服务

双击项目根目录下的 **`start.bat`**

或在命令行：
```bat
cd /d D:\文档\文档\公司\NLP\Claude-agent-design\exam-data-agent
start.bat
```

等待看到以下输出说明后端就绪：
```
URL: http://localhost:8230
INFO:     Application startup complete.
```

### 第二步：启动 Cloudflare Tunnel

双击项目根目录下的 **`start-tunnel.bat`**

或在命令行：
```bat
cd /d D:\文档\文档\公司\NLP\Claude-agent-design\exam-data-agent
start-tunnel.bat
```

等待看到以下输出说明隧道连接成功：
```
INF Connection ... registered connIndex=0 ip=...
```

---

## 验证是否正常

浏览器访问 `https://ksdata.aipush.fun`，发送一条查询消息，能正常返回数据即为成功。

或直接测试后端接口是否可达：
```
curl https://api.ksdata.aipush.fun/api/report/weekly
```

---

## Tunnel 配置信息（无需修改）

| 项目 | 值 |
|------|----|
| Tunnel 名称 | exam-data-agent |
| Tunnel ID | 6e5a7122-c725-4791-976d-49a7c5128196 |
| 配置文件 | `C:\Users\a\.cloudflared\config.yml` |
| 凭证文件 | `C:\Users\a\.cloudflared\6e5a7122-c725-4791-976d-49a7c5128196.json` |
| 后端端口 | 8230 |
| 对外域名 | ksapi.aipush.fun |

---

## 设置开机自动启动（可选）

如果不想每次手动启动，可以将两个服务注册为 Windows 开机自启：

### 方法：任务计划程序

1. 打开「任务计划程序」（Win+S 搜索）
2. 「创建基本任务」→ 触发器选「计算机启动时」
3. 操作选「启动程序」，分别添加：
   - `start.bat` 的完整路径（先延迟30秒，等系统启动完毕）
   - `start-tunnel.bat` 的完整路径（再延迟60秒，等后端启动完毕）
4. 勾选「不管用户是否登录都要运行」

---

## 常见问题

**Q: Tunnel 显示连接失败**
A: 检查本机网络是否正常，确认后端已在 8230 端口启动

**Q: 后端启动报数据库连接失败**
A: 检查 `backend/.env` 中的数据库配置，确认阿里云 AnalyticDB 可访问

**Q: 前端显示「静态模式，不支持实时查询」**
A: Tunnel 未启动，或 CF Pages 的 VITE_API_URL 未生效（需重新部署前端）

**Q: Clash Verge 代理模式注意**
A: 必须使用「系统代理」模式，不要使用 TUN 模式，否则 cloudflared 连接会被拦截

**Q: 需要重新部署前端**
```bash
git commit --allow-empty -m "chore: redeploy" && git push
```
