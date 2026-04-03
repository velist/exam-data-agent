"""
部署脚本：将最新代码上传到 Linux 服务器并重启服务
使用 paramiko SSH/SFTP 执行远程操作
"""
import os
import sys
import tarfile
import tempfile
import paramiko

# 服务器配置
SERVER_HOST = "172.10.10.26"
SERVER_PORT = 2143
SERVER_USER = "yingteng"
SERVER_PASS = "ytjy1234"
REMOTE_DIR = "/home/yingteng/exam-data-agent"

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 需要上传的目录/文件（相对于项目根目录）
INCLUDE_PATHS = [
    "backend/",
    "frontend/src/",
    "frontend/public/",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.node.json",
    "frontend/index.html",
    "scripts/export_cache.py",
]

# 排除的模式
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "node_modules",
    "dist",
    ".wrangler",
    ".playwright-mcp",
    "dataset_cache.json",  # 运行时产物，服务器启动后自动生成
    "report_cache.json",   # 运行时产物
    "query_cache",         # 运行时产物目录
    "*.png",
    "*.log",
]


def should_exclude(path: str) -> bool:
    """检查路径是否应被排除"""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.endswith(pattern[1:]):
                return True
        elif pattern in path.split(os.sep) or path.endswith(pattern):
            return True
    return False


def create_tarball() -> str:
    """创建项目代码 tar.gz 包"""
    tar_path = os.path.join(tempfile.gettempdir(), "exam-data-agent-deploy.tar.gz")
    print(f"📦 正在打包项目代码 → {tar_path}")

    with tarfile.open(tar_path, "w:gz") as tar:
        for include_path in INCLUDE_PATHS:
            full_path = os.path.join(PROJECT_ROOT, include_path)
            if not os.path.exists(full_path):
                print(f"  ⚠️  路径不存在，跳过: {include_path}")
                continue

            if os.path.isdir(full_path):
                for root, dirs, files in os.walk(full_path):
                    # 过滤排除目录
                    dirs[:] = [d for d in dirs if not should_exclude(d)]
                    for f in files:
                        file_path = os.path.join(root, f)
                        arcname = os.path.relpath(file_path, PROJECT_ROOT)
                        if not should_exclude(arcname):
                            tar.add(file_path, arcname=arcname)
            else:
                arcname = os.path.relpath(full_path, PROJECT_ROOT)
                if not should_exclude(arcname):
                    tar.add(full_path, arcname=arcname)

    size_mb = os.path.getsize(tar_path) / 1024 / 1024
    print(f"  ✅ 打包完成 ({size_mb:.1f} MB)")
    return tar_path


def run_remote(ssh: paramiko.SSHClient, cmd: str, check: bool = True) -> str:
    """执行远程命令并返回输出"""
    # 如果命令包含 sudo，自动注入密码
    actual_cmd = cmd
    if "sudo " in cmd:
        actual_cmd = cmd.replace("sudo ", f"echo {SERVER_PASS} | sudo -S ")
    print(f"  🖥️  {cmd[:80]}{'...' if len(cmd) > 80 else ''}")
    stdin, stdout, stderr = ssh.exec_command(actual_cmd, timeout=300)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()

    if out:
        # 只显示前10行
        lines = out.split("\n")
        for line in lines[:10]:
            print(f"     {line}")
        if len(lines) > 10:
            print(f"     ... ({len(lines) - 10} more lines)")

    if exit_code != 0 and check:
        print(f"  ❌ 命令失败 (exit={exit_code})")
        if err:
            print(f"     STDERR: {err[:500]}")
        raise RuntimeError(f"Remote command failed: {cmd}")

    return out


def deploy():
    """主部署流程"""
    print("=" * 60)
    print("  考试宝典数据助手 — 服务器部署")
    print("=" * 60)
    print()

    # Step 1: 打包
    tar_path = create_tarball()

    # Step 2: 连接服务器
    print(f"\n🔗 连接服务器 {SERVER_HOST}:{SERVER_PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_HOST, port=SERVER_PORT, username=SERVER_USER,
                password=SERVER_PASS, timeout=15)
    print("  ✅ SSH 连接成功")

    try:
        # Step 3: 上传 tar.gz
        print(f"\n📤 上传代码包到服务器...")
        sftp = ssh.open_sftp()
        remote_tar = f"/tmp/exam-data-agent-deploy.tar.gz"
        sftp.put(tar_path, remote_tar)
        print("  ✅ 上传完成")

        # Step 4: 停止服务
        print(f"\n⏹️  停止当前服务...")
        run_remote(ssh, "sudo systemctl stop exam-data-agent", check=False)

        # Step 5: 备份旧代码
        print(f"\n💾 备份旧代码...")
        run_remote(ssh, f"cp -r {REMOTE_DIR}/backend {REMOTE_DIR}/backend.bak 2>/dev/null || true",
                   check=False)

        # Step 6: 清理旧代码（保留 .env、venv、data 目录）
        print(f"\n🧹 清理旧代码（保留 .env / venv / data）...")
        run_remote(ssh,
            f"cd {REMOTE_DIR} && "
            f"rm -rf backend/services backend/prompts backend/tests backend/main.py backend/config.py backend/db.py backend/sql_validator.py && "
            f"rm -rf frontend/src frontend/public/cache"
        )

        # Step 7: 解压新代码
        print(f"\n📥 解压新代码...")
        run_remote(ssh, f"cd {REMOTE_DIR} && tar xzf {remote_tar}")

        # Step 8: 确保 data 目录存在
        print(f"\n📁 确保 data 目录...")
        run_remote(ssh, f"mkdir -p {REMOTE_DIR}/backend/data")

        # Step 9: 安装/更新 Python 依赖
        print(f"\n🐍 安装 Python 依赖...")
        run_remote(ssh, f"cd {REMOTE_DIR} && ./venv/bin/pip install -r backend/requirements.txt -q")

        # Step 10: 安装/更新前端依赖并构建
        print(f"\n🏗️  构建前端...")
        run_remote(ssh, f"cd {REMOTE_DIR}/frontend && npm install --silent 2>/dev/null")
        run_remote(ssh, f"cd {REMOTE_DIR}/frontend && npm run build 2>&1 | tail -5")

        # Step 11: 验证关键文件
        print(f"\n🔍 验证关键文件...")
        run_remote(ssh, f"ls {REMOTE_DIR}/backend/main.py {REMOTE_DIR}/backend/services/dataset_cache.py {REMOTE_DIR}/backend/services/dataset_router.py {REMOTE_DIR}/frontend/dist/index.html")

        # Step 12: 重启服务
        print(f"\n🚀 重启服务...")
        run_remote(ssh, "sudo systemctl start exam-data-agent")
        import time
        time.sleep(3)
        run_remote(ssh, "systemctl is-active exam-data-agent")

        # Step 13: 健康检查
        print(f"\n❤️  健康检查...")
        import time
        time.sleep(2)
        health = run_remote(ssh, "curl -s http://localhost:8230/api/health")
        if '"ok"' in health:
            print("  ✅ 服务健康！")
        else:
            print("  ⚠️  健康检查返回异常，请手动确认")

        # Step 14: 清理备份和临时文件
        print(f"\n🧹 清理临时文件...")
        run_remote(ssh, f"rm -f {remote_tar} && rm -rf {REMOTE_DIR}/backend.bak", check=False)

        print()
        print("=" * 60)
        print("  ✅ 部署完成！")
        print(f"  🌐 内网访问: http://{SERVER_HOST}:8230/")
        print(f"  📊 报表页面: http://{SERVER_HOST}:8230/report")
        print(f"  ❤️  健康检查: http://{SERVER_HOST}:8230/api/health")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        print("  尝试回滚并重启旧版本...")
        run_remote(ssh, f"if [ -d {REMOTE_DIR}/backend.bak ]; then rm -rf {REMOTE_DIR}/backend && mv {REMOTE_DIR}/backend.bak {REMOTE_DIR}/backend; fi", check=False)
        run_remote(ssh, "sudo systemctl start exam-data-agent", check=False)
        raise
    finally:
        ssh.close()
        # 清理本地临时文件
        if os.path.exists(tar_path):
            os.remove(tar_path)


if __name__ == "__main__":
    deploy()
