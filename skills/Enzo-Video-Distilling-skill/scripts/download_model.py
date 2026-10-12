# -*- coding: utf-8 -*-
"""下载 faster-whisper-small 模型到 model_small/ (hf-mirror)。
只下这 4 个文件；断点续传 + 大小校验。
"""
import urllib.request, os, time

BASE = "https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/"
local = "model_small"
os.makedirs(local, exist_ok=True)
# 只这 4 个文件（仓库没有 preprocessor_config.json / vocab.json，加会 404）
files = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
UA = "Mozilla/5.0"

def total_len(url):
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0))

def download(name):
    url = BASE + name
    path = os.path.join(local, name)
    total = total_len(url)
    if os.path.exists(path) and os.path.getsize(path) == total and total > 0:
        print(f"[skip] {name} 已完整 {total}")
        return True
    for attempt in range(6):
        try:
            start = os.path.getsize(path) if os.path.exists(path) else 0
            req = urllib.request.Request(url)
            req.add_header("User-Agent", UA)
            if 0 < start < total:
                req.add_header("Range", f"bytes={start}-")
            mode = "ab" if (0 < start < total) else "wb"
            with urllib.request.urlopen(req, timeout=600) as r, open(path, mode) as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(path) == total:
                print(f"[ok] {name} 完成 {total}")
                return True
            print(f"[warn] {name} 大小不符 {os.path.getsize(path)}/{total}, 重试")
        except Exception as e:
            print(f"[err] {name} attempt {attempt+1}: {e}")
            time.sleep(3)
    print(f"[FAIL] {name}")
    return False

ok = all(download(f) for f in files)
print("ALL_DONE" if ok else "HAS_FAILURE")
