"""
将后端缓存导出到前端 public 目录，供 CF Pages 静态部署使用。

用法：python scripts/export_cache.py

导出内容：
1. backend/data/query_cache/ 下的 SQL 查询缓存（过滤 bigdata 残留）
2. backend/data/dataset_cache.json 中的预聚合业务数据集
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_SRC = os.path.join(ROOT, "backend", "data", "query_cache")
DATASET_SRC = os.path.join(ROOT, "backend", "data", "dataset_cache.json")
CACHE_DST = os.path.join(ROOT, "frontend", "public", "cache")


def _is_dws_only(data: dict) -> bool:
    """检查缓存的 SQL 是否仅涉及 dws 库。"""
    sql = data.get("sql", "").upper()
    if not sql:
        return False
    if "BIGDATA." in sql or "BIGDATA " in sql:
        return False
    return True


def export():
    # 清理目标目录
    if os.path.exists(CACHE_DST):
        shutil.rmtree(CACHE_DST)
    os.makedirs(CACHE_DST, exist_ok=True)

    index = []
    count = 0

    # --- 1. 导出 SQL 查询缓存（过滤 bigdata）---
    if os.path.exists(CACHE_SRC):
        for fname in os.listdir(CACHE_SRC):
            if not fname.endswith(".json"):
                continue
            src_path = os.path.join(CACHE_SRC, fname)
            try:
                with open(src_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not _is_dws_only(data):
                    print(f"  跳过 (非 dws): {fname}")
                    continue
                dst_path = os.path.join(CACHE_DST, fname)
                shutil.copy2(src_path, dst_path)
                index.append({
                    "key": fname.replace(".json", ""),
                    "sql": data.get("sql", ""),
                    "ts": data.get("ts", 0),
                    "type": "query",
                })
                count += 1
            except Exception as e:
                print(f"  跳过 {fname}: {e}")
    else:
        print(f"查询缓存目录不存在: {CACHE_SRC}")

    # --- 2. 导出预聚合数据集 ---
    dataset_count = 0
    if os.path.exists(DATASET_SRC):
        try:
            with open(DATASET_SRC, "r", encoding="utf-8") as f:
                datasets = json.load(f)
            for name, data in datasets.items():
                if name.startswith("_"):
                    continue  # 跳过元数据（如 _ts）
                dst_path = os.path.join(CACHE_DST, f"ds_{name}.json")
                with open(dst_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                index.append({
                    "key": f"ds_{name}",
                    "dataset": name,
                    "type": "dataset",
                })
                dataset_count += 1
        except Exception as e:
            print(f"  数据集导出失败: {e}")
    else:
        print(f"数据集缓存不存在: {DATASET_SRC}（启动后端后会自动生成）")

    # --- 3. 写入索引文件 ---
    index_path = os.path.join(CACHE_DST, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"已导出 {count} 个查询缓存 + {dataset_count} 个数据集到 {CACHE_DST}")
    print(f"索引文件: {index_path}")


if __name__ == "__main__":
    export()
