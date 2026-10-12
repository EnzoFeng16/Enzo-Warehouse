---
name: Enzo-Video-Distilling-skill
description: |
  网页视频知识蒸馏——将视频（小红书、抖音、B站、YouTube 等平台或本地文件）转化为结构化 Markdown 知识文档。
  触发场景：用户提供视频链接要求"总结""蒸馏""提炼知识点""分析内容"时使用。
  也适用于用户说"像之前一样帮我蒸馏这个视频"、发小红书/抖音链接要求总结等场景。
  支持平台：小红书/RedNote/XiaoHongShu、抖音/Douyin、YouTube、Bilibili、其他直接视频链接、本地 MP4 文件。
---

# Enzo Video Distilling Skill（完整版）

将网页视频内容转化为高质量的结构化 Markdown 知识文档。本版已覆盖**小红书 / 抖音 / B站 / YouTube / 本地文件 / 其他直链**，抖音为本次新增能力。

## 核心流程

```
输入(URL/文件) → 判断平台 → 获取视频 → 压缩(如需) → AI分析/转写 → 生成文档 → 清理
```

## Step 1: 判断输入类型

| 输入特征 | 类型 | 处理方式 |
|----------|------|----------|
| `xiaohongshu.com/explore/` | 小红书笔记 | Step 2A |
| `xhslink.com/` | 小红书短链 | Step 2A |
| `v.douyin.com/` | 抖音短链 | Step 2C |
| `douyin.com/video/<id>` | 抖音视频 | Step 2C |
| `youtube.com/` 或 `youtu.be/` | YouTube | Step 2B |
| `bilibili.com/` | B站 | Step 2B |
| `.mp4`/`.mov`/`.m4v` 本地路径 | 本地文件 | 直接跳到 Step 3 |
| 其他视频 URL | 通用 | Step 2B |

---

## Step 2A: 小红书视频获取

小红书视频页面是 SPA，视频 URL 通过 API 动态加载。

### 决策流程

```
有 XHS-Downloader？
  ├── 是 → 2A.1 方法一：XHS-Downloader API（推荐，最快）
  └── 否 → 2A.2 方法二：Playwright 获取 CDN 地址
                │
                ├── CDN 可直链下载（sns-video-v6 / sns-bak-v6）
                │     └── Python requests 下载 → 成功
                │
                └── CDN 仅 MSE 播放（sns-video-qc）
                      └── 放弃下载 → 直接用 API 返回的文本做分析
```

**核心原则：不要在下载上耗费超过 5 分钟。** 小红书 CDN 有多个域名，部分拒绝直接 HTTP，纠缠过久直接降级到文本分析。

### 2A.0 确认 Cookie

检查用户是否提供了 Cookie。如果没有，**必须先向用户索要**：

> 需要小红书 Cookie 才能获取视频。请在浏览器中登录 xiaohongshu.com，F12 → 网络 → 复制任一请求的 Cookie 值发给我。

用户可能在对话上下文中已提供过 Cookie（如 `web_session=...`），注意复用。

### 2A.1 方法一：XHS-Downloader API（推荐，最快）

XHS-Downloader 内置反爬和 Cookie 管理，且能返回备用 CDN 地址，避免单域名下载失败。

#### 首次配置检查

使用前确保 `_internal/Volume/settings.json` 包含所有必要字段：

```json
{
    "cookie": "<用户的Cookie字符串>",
    "work_path": "<输出目录，如 D:\\CC\\小红书学习>",
    "folder_name": "videos",
    "browser_cookie": false
}
```

**常见坑：** `browser_cookie` 字段缺失会导致 `KeyError: 'browser_cookie'` 崩溃。如果遇到此错误，在 settings.json 末尾添加 `"browser_cookie": false`。

#### 启动 API 服务

先检查是否已有实例在运行：
```bash
curl -s "http://localhost:5556/health"
```

如果端口已被占用（返回数据或 connection refused 以外的错误），说明已有实例，直接复用，**不要试图重启**。如果返回 `connection refused` 或超时，则启动：
```bash
cd <XHS-Downloader目录> && nohup ./main.exe api > /dev/null 2>&1 &
```

#### 调用下载

```bash
curl -s -X POST "http://localhost:5556/xhs/detail" \
  -H "Content-Type: application/json" \
  -d '{"url": "<小红书完整URL，含 xsec_token>", "download": true}'
```

返回的 JSON 包含：
- `data.作品标题`、`data.作品描述`、`data.作者昵称`、`data.发布时间` → 文档元数据
- `data.下载地址` → CDN URL 数组，**即使目标 CDN 不可用，API 可能返回不同域名的备用地址**

#### 下载视频文件

```python
import requests
# 遍历 data.下载地址 中的 URL，找到第一个能用的
for cdn_url in download_urls:
    resp = requests.get(cdn_url, headers={'Referer': 'https://www.xiaohongshu.com/'}, stream=True, timeout=30)
    if resp.status_code == 200:
        break
# 写入 video.mp4
```

**如果所有 CDN URL 都下载失败**（全部 ECONNRESET / 403），**不要继续纠缠**，直接跳转到 Step 4 回退策略，用 API 已返回的标题+描述文本做分析。XHS-Downloader API 返回的 `data.作品描述` 通常已包含视频的核心内容要点。

### 2A.2 方法二：Playwright 浏览器（仅当 XHS-Downloader 不可用）

#### 获取视频 CDN 地址

```python
from playwright.sync_api import sync_playwright
# 1. 解析 Cookie 字符串为 Playwright 格式
# 2. 启动 headless Chromium，add_cookies
# 3. 访问完整 URL（必须带 xsec_token 参数）
# 4. 监听网络请求，匹配包含 .mp4 的 URL
# 5. 从 network requests 中提取视频 CDN 地址
```

关键点：
- URL 必须带 `?xsec_token=...&xsec_source=pc_user` 参数
- 用 `wait_until='load'`（**不要用 `networkidle`**，小红书页面持续有网络请求，会超时）
- 页面加载后 sleep 3-5 秒等待视频请求发出

#### CDN 域名差异

| CDN 域名 | 行为 | 下载方式 |
|----------|------|----------|
| `sns-video-v6.xhscdn.com` | 接受 HTTP 请求 | `requests.get(url, headers={'Referer': 'https://www.xiaohongshu.com/'})` |
| `sns-bak-v6.xhscdn.com` | 接受 HTTP 请求 | 同上 |
| `sns-video-qc.xhscdn.com` | **仅允许浏览器 MSE 流式播放** | 无法直接 HTTP 下载 |

如果 Playwright 捕获到的 CDN 是 `sns-video-qc` 域名：
- **不要尝试** `page.route()` 拦截响应体（视频流式传输，只能捕获初始 ~2MB 缓冲）
- **不要尝试** `page.goto(cdn_url)` 直接导航（会被风控拦截为"IP存在风险"）
- **不要尝试** `page.evaluate('fetch(cdn_url)')` （浏览器 JS fetch 同样被 CORS/安全策略阻止）
- **不要尝试** Playwright 录屏回放视频（headless 浏览器被风控 + 等待时间长 + 无画面）

**当 Playwright 遇到 `sns-video-qc` 时的正确做法：** 放弃下载，用页面已有的文本内容（标题、描述、评论）做分析。Python 端 `requests.get()` 返回 ECONNRESET 且 Playwright 的各种拦截手段均无效时，说明此 CDN 域名彻底无法下载，**立即降级，不纠缠**。

#### 下载视频

```python
import requests
resp = requests.get(cdn_url, headers={'Referer': 'https://www.xiaohongshu.com/'}, stream=True)
with open('video.mp4', 'wb') as f:
    for chunk in resp.iter_content(8192):
        f.write(chunk)
```

---

## Step 2B: 其他平台视频获取（YouTube / B站 / 通用直链）

优先使用 yt-dlp MCP 工具：

1. `ytdlp_get_video_metadata` — 获取视频元数据（标题、作者、时长）
2. `ytdlp_download_video` — 下载视频（720p）
3. `ytdlp_download_transcript` — 获取字幕/转录文本（如有）

如果 yt-dlp 失败，尝试用 `mcp__webscraper__scrape_url` 获取页面内容作为补充。

> ⚠️ **注意**：yt-dlp 对**抖音**无效（见 Step 2C），抖音必须走专属流程。

---

## Step 2C: 抖音视频获取（本次新增能力）

抖音反爬严格，`yt-dlp` 的 `DouyinIE` 会直接报 `Fresh cookies (not necessarily logged in) are needed`。本步用**原始 Cookie 头直连抖音 Web API** 绕过，已跑通一条龙。

### 关键结论（先记住，省得再踩）

1. **yt-dlp 直连抖音必失败**：根因是抖音 `aweme/v1/web/aweme/detail/` 接口要"新鲜 `__ac_signature` 签名 Cookie"，而 yt-dlp 既没实现签名生成、又读不好 Cookie → 它发的是无/错 Cookie 请求，被反爬挡下。**这不代表你给的 Cookie 无效**——实测游客态（无 `sid_tt`/`sessionid_ss`）Cookie 直接打 API 完全可用。结论：**彻底放弃 yt-dlp，用原始 `Cookie:` 头直连 API**。
2. **Cookie 必须用户提供**：抖音反爬，需从浏览器 DevTools 复制 `Cookie:` 请求头整串（含 `ttwid`/`__ac_signature`/`s_v_web_id` 等）。只在本会话使用，结束务必删除，绝不写进文档/日志。
3. **视觉分析 MCP 工具通常没有**：用本地 Whisper 转写音频代替"看视频"，对口播知识视频更对路。
4. **先验证再下载**：白拉 70MB 前先用 API 断言 `status_code==0` 且含 `aweme_detail`，失败立刻提示重抓 Cookie，省带宽。
5. **多源直链聚合**：抖音返回的 `play_addr`/`download_addr`/`bit_rate[].play_addr` 各带一组直链，逐个尝试直到某个 200/206 成功。

### 2C.1 解析短链拿 video id

```
curl -sI -L "https://v.douyin.com/xxxx/"    # 看 302 Location → www.douyin.com/video/<id>
```
记下 `<id>`。

### 2C.2 用 Cookie 打 Web API 拿详情 + 直链

把用户给的 `Cookie:` 整串存到 `cookie_raw.txt`（用 Write 工具写文件，别走 bash 变量，避免特殊字符被吞）。

**Cookie 新鲜度**：抖音签名 Cookie（`__ac_signature`/`ttwid`/`s_v_web_id`）有时效，拿到后尽快用；若 API 返回空 / `status_code!=0` / 403，先让用户**重抓一份新鲜 Cookie** 再试（不必登录，游客态即可）。

**先验证再下载**：
```python
import urllib.request, json
vid = "<id>"
cookie = open("cookie_raw.txt", encoding="utf-8").read().strip()
req = urllib.request.Request(f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={vid}")
req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36")
req.add_header("Referer", "https://www.douyin.com/")
req.add_header("Cookie", cookie)
d = json.loads(urllib.request.urlopen(req, timeout=30).read())
assert d.get("status_code") == 0 and "aweme_detail" in d, "Cookie 失效/被拦，重抓"
aweme = d["aweme_detail"]
# aweme["desc"], aweme["author"]["nickname"], aweme["create_time"], aweme["statistics"]
# 视频直链在 aweme["video"] 下（见 2C.3）
```
> 嫌手写麻烦可直接跑 `scripts/download_douyin.py <video_id>`（自动验证 + 聚合所有直链 + 落盘 `aweme_detail.json`）。

`desc` 通常只是预告（"视频里见"），真正内容在口播 → 必须转写音频（见 2C.4）。

### 2C.3 下载视频

抖音返回的 `video` 里**不止一个直链来源**：`play_addr`、`download_addr`、以及 `bit_rate[].play_addr` 各带一组 `url_list`。不同视频能用的来源不同，所以**全部聚合成候选列表、逐个尝试直到某个 200/206 成功**（`scripts/download_douyin.py` 已内置该逻辑）：
```python
import urllib.request
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
candidates = []
for key in ("play_addr", "download_addr"):
    va = aweme["video"].get(key)
    if va and va.get("url_list"): candidates += va["url_list"]
for br in aweme["video"].get("bit_rate", []) or []:
    if br.get("play_addr", {}).get("url_list"): candidates += br["play_addr"]["url_list"]
for url in candidates:
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA); req.add_header("Referer","https://www.douyin.com/"); req.add_header("Cookie", cookie)
        with urllib.request.urlopen(req, timeout=60) as r, open("video.mp4","wb") as f:
            while True:
                b = r.read(1<<20)
                if not b: break
                f.write(b)
        break
    except Exception as e:
        print("直链失败, 换下一个:", e)
```
> ⚠️ `play_addr` 下载的是**带抖音水印**版本；`download_addr` 理论无水印但常 403。知识蒸馏不关心水印，默认用 `play_addr` 即可。

### 2C.4 抽音频 + Whisper 转写（抖音没有视觉分析工具时）

```
ffmpeg -y -i video.mp4 -vn -ac 1 -ar 16000 -f wav audio.wav
```

下载 faster-whisper 模型（**关键坑见下方"模型下载"**）→ 转写。用 wave+numpy 读音频绕过 PyAV 兼容问题：
```python
import wave, numpy as np
wf = wave.open("audio.wav","rb"); raw = wf.readframes(wf.getnframes()); wf.close()
audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32)/32768.0
from faster_whisper import WhisperModel
model = WhisperModel("model_small", device="cpu", compute_type="int8")  # 本地目录
segs, info = model.transcribe(audio_np, beam_size=5, language="zh", vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
# 逐 seg 写 transcript.txt（带 [mm:ss->mm:ss] 时间戳）+ transcript_full.txt（纯文本）
```
> 📌 **转写质量提示**：`small` 模型对专有名词/人名识别易错（实测把"莱昂纳多"识别成"小李子"、"乒乓球"→"平房球"）。若视频人名/品牌密集，改用 `medium` 模型（更准但慢 2~3 倍、内存更大）；无论哪种，出炉后都要人工校对术语。可直接跑 `scripts/transcribe.py`（已内置 wave+numpy 绕 PyAV）。

### 2C.5 抖音模型下载的坑（已解决，照做即可）

- **别用 curl 拉 hf-mirror**：Windows 自带 curl 用 schannel，对 hf-mirror 大文件 TLS 握手失败。用 Python `urllib` 流式续传。
- **别用 hf_hub_download 的 local_dir**：会产出 0 字节文件（缓存锁机制干扰）。直接 urllib 拉下列 4 个文件到 `model_small/`：
  - `https://hf-mirror.com/Systran/faster-whisper-small/resolve/main/config.json`
  - `.../model.bin`（~483MB，float16；faster-whisper 能加载）
  - `.../tokenizer.json`
  - `.../vocabulary.txt`  ← **注意是 vocabulary.txt，不是 vocab.json**（faster-whisper 的 allow_patterns 是 `vocabulary.*`）
  - **只下这 4 个文件**；不要加 `preprocessor_config.json` 或 `vocab.json`——仓库里根本没有这两个，硬加会 404 崩脚本。
  - 先 HEAD 拿 Content-Length 做大小校验，断点续传 + 重试直到字节数吻合。可直接跑 `scripts/download_model.py`（已内置 4 文件清单 + 断点续传 + 大小校验）。
- 国内若 hf-mirror 不稳，HF_ENDPOINT 可回退 `https://huggingface.co`（可能慢/被墙，优先镜像）。

---

## Step 3: 视频压缩

AI 视频分析有 **8MB 文件大小限制**（仅当用 `zai-vision` 等视觉分析工具时需要；走 Whisper 转写路径则无需压缩，音频已足够）。下载后先检查：

```bash
ls -lh <video_path>
```

### 如果 > 8MB 且要用视觉分析

用 ffmpeg 压缩，**根据视频时长调整参数**：

**短视频（< 3 分钟）：**
```bash
ffmpeg -y -i input.mp4 -vf "scale=640:-2,fps=15" -b:v 280k -c:v libx264 -preset fast -c:a aac -b:a 64k output.mp4
```

**长视频（3-10 分钟）：**
```bash
ffmpeg -y -i input.mp4 -vf "scale=480:-2,fps=10" -b:v 90k -c:v libx264 -preset ultrafast -c:a aac -b:a 16k -ac 1 -ar 16000 output.mp4
```

**超长视频（> 10 分钟）：** 先用 ffprobe 确认时长，可能需要分段处理或更激进的压缩。

压缩后再次 `ls -lh` 确认 < 8MB，如果仍超限继续降低参数。

### 如果 ≤ 8MB 或走 Whisper 路径

直接使用，无需压缩。

---

## Step 4: AI 视频分析 / 内容提取

### 路径 A：有视觉分析工具（zai-vision）

使用 `mcp__zai-vision__analyze_video` 工具。

**分析 Prompt（中文，详细）：**
```
请完整、详细地分析这个视频的内容。我需要你：
1. 逐段描述视频中每一部分讲的内容（标注时间戳）
2. 提取所有展示的PPT文字、图表、框架图、白板板书等关键信息
3. 总结视频的核心知识点和要点
4. 用中文回答，尽可能详细，不要遗漏任何信息点
5. 如果视频中有演讲者的核心观点和论证逻辑，请完整转述
6. 如果有方法论或框架，请重点提取并结构化呈现
```
**重要：** 使用中文字幕/语音的分析结果，不需要额外翻译。

### 路径 B：无视觉分析工具（抖音等场景）→ Whisper 转写

抖音等没有 `zai-vision` 的环境，用 Step 2C.4 得到的 `transcript.txt` 作为分析素材，直接让模型做结构化蒸馏。

### 回退策略：纯文本分析

如果视频无法下载（CDN 被封、网络问题等），**不要死磕**。用已有的文本素材直接生成文档：

**素材来源**（按优先级）：
1. XHS-Downloader API 返回的 `data.作品描述` —— 通常包含视频核心内容要点
2. 抖音 `aweme_detail` 的 `desc` / 作者 / 发布时间（若仅是预告，需转写）
3. XHS-Downloader API 返回的 `data.作品标题`、`data.作者昵称`、`data.发布时间`
4. Playwright 从页面抓取的文本内容（标题、描述、评论文本）

**判断标准**：如果从 Step 2 开始已经超过 5 分钟还没有下载到可用的视频文件，立即切换到此回退策略。

---

## Step 5: 生成结构化知识文档

根据分析结果，生成 Markdown 文档，保存到用户指定的文件夹。

### 文档模板

```markdown
# [视频标题/主题]

> 来源：[平台] @[作者]
> 链接：[URL]
> 日期：[发布日期]

---

## 一、核心论点

[一句话总结视频的核心观点]

---

## 二、详细内容

[按视频逻辑分段展开，每段包含：]

### 2.1 [段落主题]
- 要点 1
- 要点 2

### 2.2 [段落主题]
...

---

## 三、核心框架/方法论

[如果有框架图，用 ASCII art 或 Mermaid 呈现]

---

## 四、关键概念

[重要的专业术语或概念解释，用表格呈现]

| 概念 | 解释 |
|------|------|
| ... | ... |

---

## 五、知识图谱

[用 ASCII art 画出核心知识结构]

---

## 六、一句话总结

> [精炼的一句话总结]

---

## 七、可落地的行动清单

1. [具体的行动项]
2. ...
```

### 写作原则

- **不要仅翻译或转述**，要"蒸馏"——提取核心逻辑，去除冗余
- 使用表格和图表增强可读性
- 保留原视频中的专业术语和关键数据
- 如果有多个解决方案/方法论并列，用对比表格呈现
- **校正 ASR 瑕疵**：Whisper 转写的视频里人名/专有名词常被误识别（如"小李子"=莱昂纳多、品牌名等），保留原术语

---

## Step 6: 清理

- 删除临时下载/压缩的视频文件（`video.mp4`、`video_compressed.mp4` 等）
- **抖音场景务必删除 `cookie_raw.txt` / `cookies.txt`（Cookie 必须删，不在磁盘留会话凭据）**
- 只保留最终的 `.md` 知识文档（及可选的 `transcript.txt`、模型与脚本，供复用）
- 如果是小红书视频，关闭 Playwright 浏览器实例

---

## 注意事项

- **Cookie 安全**：小红书 / 抖音 Cookie 只在当前会话使用，不要写入文档或日志
- **编码问题**：Windows 下 Python print 中文可能乱码，用 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` 解决
- **视频质量 vs 文件大小**：压缩是必要的折中，优先保证语音可辨识，画面清晰度可适度降低
- **下载超时防线**：从 Step 2 开始 5 分钟内没拿到可用的视频文件，立刻降级到文本分析，不要死磕
- **抖音必须 Cookie + Whisper**：别指望 yt-dlp 或 zai-vision，走 Step 2C 专属流程

---

## 附：可复用脚本（scripts/）

- `download_douyin.py <video_id>`：读 `cookie_raw.txt` → 验证 API → 聚合 `play_addr`/`download_addr`/`bit_rate` 全部直链 → 逐个尝试下载 → 落盘 `video.mp4` + `aweme_detail.json`。
- `download_model.py`：从 hf-mirror 拉 `faster-whisper-small` 4 个文件到 `model_small/`，断点续传 + 大小校验。
- `transcribe.py`：读 `audio.wav`，用 `model_small` 本地模型转写（wave+numpy 绕 PyAV），输出 `transcript.txt`（带时间戳）+ `transcript_full.txt`。

运行前确保 `cookie_raw.txt`、`audio.wav`、`model_small/` 在当前目录。

---

## 故障排查速查表

| 症状 | 原因 | 解决 |
|------|------|------|
| XHS-Downloader `KeyError: 'browser_cookie'` | settings.json 缺少字段 | 添加 `"browser_cookie": false` |
| API 启动报 `10048` 端口占用 | 上次的 API 进程未退出 | `curl localhost:5556/health` 验证是否可用，直接复用 |
| `requests.get(CDN)` 返回 ECONNRESET | CDN 是 `sns-video-qc` 域名，仅允许 MSE | 检查 `data.下载地址` 是否有其他域名（如 `sns-bak-v6`），否则降级文本分析 |
| Playwright `page.route()` 只捕获 ~2MB | 视频以 MSE 流式传输，响应体分块 | 放弃此方案，不纠缠 |
| Playwright `page.goto(CDN)` 显示"IP存在风险" | Headless 浏览器被小红书风控 | 放弃下载，降级到文本分析 |
| Playwright `wait_until='networkidle'` 超时 | 小红书页面持续有网络请求 | 用 `wait_until='load'` + `time.sleep(3)` |
| `mcp__zai-vision__analyze_video` 报文件过大 | 视频 > 8MB | 用 ffmpeg 按 Step 3 参数重新压缩，继续降低 bitrate/fps/分辨率 |
| 抖音 `yt-dlp` 报 Fresh cookies needed | yt-dlp 不支持抖音签名 | **彻底弃用 yt-dlp**，走 Step 2C 直连 API |
| 抖音 API 返回空 / status_code!=0 / 403 | Cookie 过期或被拦 | 重抓一份新鲜 Cookie（游客态即可）再试 |
| faster-whisper 加载报 `metadata_errors` | 与新版 PyAV 不兼容 | 用 wave+numpy 读音频传 ndarray（见 2C.4） |
| `model.bin` 下载成 0 字节 | hf_hub_download 缓存锁干扰 | 用 `scripts/download_model.py` 直连 urllib 拉取 |
| `hf-mirror` 拉模型 TLS 失败 | Windows curl 用 schannel | 用 Python `urllib` 流式续传（脚本已内置） |
| 模型缺 `vocab.json` 报 404 | 该文件仓库不存在 | 只用 `config.json`/`model.bin`/`tokenizer.json`/`vocabulary.txt` 4 文件 |
