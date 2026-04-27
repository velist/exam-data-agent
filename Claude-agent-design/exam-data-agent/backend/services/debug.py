"""
开发者调试服务：查询日志记录（按IP隔离）、取消令牌、日志导出（服务器保存+7天清理）。
"""
import os
import time
import json
import threading
import logging
from collections import deque
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("debug")

CST = timezone(timedelta(hours=8))
MAX_LOG_ENTRIES = 200
LOG_RETENTION_DAYS = 7

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, "data", "debug_logs")

# 按 IP 隔离的内存缓冲区 {ip: deque}
_log_buffers: dict[str, deque] = {}
_buffers_lock = threading.Lock()

# 活跃查询的取消令牌 {query_id: threading.Event}
_cancel_tokens: dict[str, threading.Event] = {}
_cancel_lock = threading.Lock()


def _get_buffer(ip: str) -> deque:
    with _buffers_lock:
        if ip not in _log_buffers:
            _log_buffers[ip] = deque(maxlen=MAX_LOG_ENTRIES)
        return _log_buffers[ip]


# --- 取消令牌 ---

def create_cancel_token(query_id: str) -> threading.Event:
    event = threading.Event()
    with _cancel_lock:
        _cancel_tokens[query_id] = event
    return event


def remove_cancel_token(query_id: str):
    with _cancel_lock:
        _cancel_tokens.pop(query_id, None)


def cancel_query(query_id: str) -> bool:
    with _cancel_lock:
        event = _cancel_tokens.get(query_id)
    if event:
        event.set()
        return True
    return False


# --- 日志操作 ---

def add_log(entry: dict, client_ip: str = "unknown"):
    """添加一条查询日志到对应 IP 的内存缓冲区"""
    entry["timestamp"] = datetime.now(CST).isoformat()
    buf = _get_buffer(client_ip)
    buf.append(entry)


def get_logs(client_ip: str, limit: int = 50) -> list[dict]:
    """获取指定 IP 最近 N 条日志"""
    buf = _get_buffer(client_ip)
    logs = list(buf)
    return logs[-limit:]


def export_logs(client_ip: str) -> tuple[str, str]:
    """导出指定 IP 的全部日志为 JSON，同时保存到磁盘。
    返回 (json_string, saved_file_path_or_empty)
    """
    buf = _get_buffer(client_ip)
    data = list(buf)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    saved_path = ""
    if data:
        saved_path = _save_to_disk(client_ip, json_str)

    return json_str, saved_path


def clear_logs(client_ip: str):
    """清空指定 IP 的日志缓冲区"""
    with _buffers_lock:
        _log_buffers.pop(client_ip, None)


def _save_to_disk(client_ip: str, json_str: str) -> str:
    """保存日志到磁盘，返回文件路径"""
    safe_ip = client_ip.replace(":", "_").replace(".", "_")
    ip_dir = os.path.join(LOG_DIR, safe_ip)
    os.makedirs(ip_dir, exist_ok=True)

    ts = datetime.now(CST).strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}.json"
    filepath = os.path.join(ip_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info(f"日志已保存: {filepath}")
    except Exception as e:
        logger.warning(f"日志保存失败: {e}")

    _cleanup_ip_dir(ip_dir)
    return filepath


def _cleanup_ip_dir(ip_dir: str):
    """清理指定 IP 目录下超过保留期的文件"""
    if not os.path.isdir(ip_dir):
        return
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    try:
        for fname in os.listdir(ip_dir):
            fpath = os.path.join(ip_dir, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                logger.info(f"清理过期日志: {fpath}")
    except Exception as e:
        logger.warning(f"日志清理失败: {e}")


def cleanup_old_logs():
    """清理所有 IP 目录下超过 7 天的日志文件。启动时调用一次。"""
    if not os.path.isdir(LOG_DIR):
        return
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    cleaned = 0
    try:
        for ip_dir_name in os.listdir(LOG_DIR):
            ip_dir = os.path.join(LOG_DIR, ip_dir_name)
            if not os.path.isdir(ip_dir):
                continue
            for fname in os.listdir(ip_dir):
                fpath = os.path.join(ip_dir, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    cleaned += 1
            # 删除空目录
            if not os.listdir(ip_dir):
                os.rmdir(ip_dir)
        if cleaned:
            logger.info(f"启动清理完成，移除 {cleaned} 个过期日志文件")
    except Exception as e:
        logger.warning(f"启动清理异常: {e}")
