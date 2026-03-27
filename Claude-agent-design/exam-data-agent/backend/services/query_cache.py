"""
SQL 查询结果缓存层
- 以 SQL 的 SHA256 哈希作为缓存键
- JSON 文件存储，有效期 1 年
- 含时间关键词（本周/今天/昨天等）的查询不缓存
"""

import hashlib
import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "query_cache")
MAX_AGE = 365 * 24 * 3600  # 1 year

# 含这些关键词的 SQL 不缓存（结果会随时间变化）
_VOLATILE_PATTERNS = re.compile(
    r"CURDATE|NOW\(\)|CURRENT_DATE|今天|昨天|本周|本月|当天|当月",
    re.IGNORECASE,
)


def _cache_key(sql: str) -> str:
    normalized = " ".join(sql.split()).strip().upper()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _is_volatile(sql: str) -> bool:
    return bool(_VOLATILE_PATTERNS.search(sql))


def get_cached_result(sql: str) -> dict | None:
    if _is_volatile(sql):
        return None
    key = _cache_key(sql)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) > MAX_AGE:
            os.remove(path)
            return None
        logger.info(f"缓存命中: {key}")
        return data["result"]
    except Exception as e:
        logger.warning(f"读取缓存失败: {e}")
        return None


def set_cached_result(sql: str, result: dict) -> None:
    if _is_volatile(sql):
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = _cache_key(sql)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        payload = {
            "ts": time.time(),
            "sql": sql,
            "result": result,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"缓存写入: {key}")
    except Exception as e:
        logger.warning(f"写入缓存失败: {e}")
