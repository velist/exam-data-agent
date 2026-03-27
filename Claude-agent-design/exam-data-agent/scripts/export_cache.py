"""
将后端查询缓存导出到前端 public 目录，供 CF Pages 静态部署使用。

用法：python scripts/export_cache.py

流程：
1. 读取 backend/data/query_cache/ 下所有 JSON 缓存
2. 复制到 frontend/public/cache/
3. 生成 frontend/public/cache/index.json 索引文件
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_SRC = os.path.join(ROOT, "backend", "data", "query_cache")
CACHE_DST = os.path.join(ROOT, "frontend", "public", "cache")


def export():
    if not os.path.exists(CACHE_SRC):
        print(f"缓存目录不存在: {CACHE_SRC}")
        sys.exit(1)

    # 清理目标目录
    if os.path.exists(CACHE_DST):
        shutil.rmtree(CACHE_DST)
    os.makedirs(CACHE_DST, exist_ok=True)

    index = []
    count = 0

    for fname in os.listdir(CACHE_SRC):
        if not fname.endswith(".json"):
            continue
        src_path = os.path.join(CACHE_SRC, fname)
        dst_path = os.path.join(CACHE_DST, fname)

        # 复制缓存文件
        shutil.copy2(src_path, dst_path)

        # 读取元信息，写入索引
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            index.append({
                "key": fname.replace(".json", ""),
                "sql": data.get("sql", ""),
                "ts": data.get("ts", 0),
            })
            count += 1
        except Exception as e:
            print(f"  跳过 {fname}: {e}")

    # 写入索引文件
    index_path = os.path.join(CACHE_DST, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"已导出 {count} 个缓存文件到 {CACHE_DST}")
    print(f"索引文件: {index_path}")


if __name__ == "__main__":
    export()
