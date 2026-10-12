# -*- coding: utf-8 -*-
"""抖音视频下载：验证 API -> 聚合所有直链 -> 逐个尝试下载。
用法: python download_douyin.py <video_id>   (需 cookie_raw.txt 在同目录)
"""
import urllib.request, json, sys, os, time

if len(sys.argv) < 2:
    print("用法: download_douyin.py <video_id>  (需 cookie_raw.txt 在同目录)")
    sys.exit(1)
vid = sys.argv[1]
with open("cookie_raw.txt", "r", encoding="utf-8") as f:
    cookie = f.read().strip()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def fetch_json(url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Cookie", cookie)
    req.add_header("Referer", "https://www.douyin.com/")
    req.add_header("Accept", "application/json, */*")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# 1) 验证 + 拿详情
url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={vid}"
data = fetch_json(url)
assert data.get("status_code") == 0 and "aweme_detail" in data, "Cookie 失效/被拦，请重抓 Cookie"
d = data["aweme_detail"]
print("标题:", d.get("desc"))
print("作者:", d.get("author", {}).get("nickname"), "/", d.get("author", {}).get("unique_id"))
print("发布:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d.get("create_time", 0))))
st = d.get("statistics", {})
print("点赞/评论/分享:", st.get("digg_count"), st.get("comment_count"), st.get("share_count"))

with open("aweme_detail.json", "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print("已保存 aweme_detail.json")

# 2) 聚合 play_addr + download_addr + bit_rate[].play_addr 所有直链
video = d.get("video", {})
cands = []
for key in ("play_addr", "download_addr"):
    va = video.get(key)
    if va and va.get("url_list"):
        cands += va["url_list"]
for br in video.get("bit_rate", []) or []:
    if br.get("play_addr", {}).get("url_list"):
        cands += br["play_addr"]["url_list"]
print(f"\n候选直链数: {len(cands)}")

out = "video.mp4"
ok = False
for i, vurl in enumerate(cands):
    try:
        print(f"尝试直链 {i+1}/{len(cands)}: {vurl[:90]}...")
        req = urllib.request.Request(vurl)
        req.add_header("User-Agent", UA)
        req.add_header("Referer", "https://www.douyin.com/")
        req.add_header("Cookie", cookie)
        req.add_header("Range", "bytes=0-")
        with urllib.request.urlopen(req, timeout=60) as r, open(out, "wb") as fo:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                fo.write(chunk)
        ok = True
        print(f"下载完成: {out} ({os.path.getsize(out)} 字节)")
        break
    except Exception as e:
        print("  失败:", repr(e)[:200])
        continue
if not ok:
    print("所有直链下载失败")
    sys.exit(1)
