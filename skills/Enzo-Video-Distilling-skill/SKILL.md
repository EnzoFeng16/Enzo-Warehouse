---
name: Enzo-Video-Distilling-skill
description: |
  网页视频知识蒸馏——将视频（小红书、B站、YouTube 等平台或本地文件）转化为结构化 Markdown 知识文档。
  触发场景：用户提供视频链接要求"总结""蒸馏""提炼知识点""分析内容"时使用。
  也适用于用户说"像之前一样帮我蒸馏这个视频"、发小红书链接要求总结等场景。
  支持平台：小红书/RedNote/XiaoHongShu、YouTube、Bilibili、其他直接视频链接、本地 MP4 文件。
---

# Enzo Video Distilling Skill

将网页视频内容转化为高质量的结构化知识文档。

## 核心流程

```
输入(URL/文件) → 获取视频 → 压缩(如需) → AI分析 → 生成文档 → 清理
```

## Step 1: 判断输入类型

| 输入特征 | 类型 | 处理方式 |
|----------|------|----------|
| `xiaohongshu.com/explore/` | 小红书笔记 | Step 2A |
| `xhslink.com/` | 小红书短链 | Step 2A |
| `youtube.com/` 或 `youtu.be/` | YouTube | Step 2B |
| `bilibili.com/` | B站 | Step 2B |
| `.mp4`/`.mov`/`.m4v` 本地路径 | 本地文件 | 直接跳到 Step 3 |
| 其他视频 URL | 通用 | Step 2B |

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

---

### 2A.0 确认 Cookie

检查用户是否提供了 Cookie。如果没有，**必须先向用户索要**：

> 需要小红书 Cookie 才能获取视频。请在浏览器中登录 xiaohongshu.com，F12 → 网络 → 复制任一请求的 Cookie 值发给我。

用户可能在对话上下文中已提供过 Cookie（如 `web_session=...`），注意复用。

---

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

---

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

## Step 2B: 其他平台视频获取

优先使用 yt-dlp MCP 工具：

1. `ytdlp_get_video_metadata` — 获取视频元数据（标题、作者、时长）
2. `ytdlp_download_video` — 下载视频（720p）
3. `ytdlp_download_transcript` — 获取字幕/转录文本（如有）

如果 yt-dlp 失败，尝试用 `mcp__webscraper__scrape_url` 获取页面内容作为补充。

## Step 3: 视频压缩

AI 视频分析有 **8MB 文件大小限制**。下载后必须先检查：

```bash
ls -lh <video_path>
```

### 如果 > 8MB

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

### 如果 ≤ 8MB

直接使用，无需压缩。

## Step 4: AI 视频分析

使用 `mcp__zai-vision__analyze_video` 工具。

### 分析 Prompt（中文，详细）

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

### 回退策略：文本分析

如果视频无法下载（CDN 被封、网络问题等），**不要死磕**。用已有的文本素材直接生成文档：

**素材来源**（按优先级）：
1. XHS-Downloader API 返回的 `data.作品描述` —— 通常包含视频核心内容要点
2. XHS-Downloader API 返回的 `data.作品标题`、`data.作者昵称`、`data.发布时间`
3. Playwright 从页面抓取的文本内容（标题、描述、评论文本）
4. 小红书上其他用户对该视频的评论和讨论

**方法**：将收集到的文本内容作为分析素材，用同样的分析 Prompt 要求 AI 提取知识点、框架和要点，直接生成文档。

**判断标准**：如果从 Step 2 开始已经超过 5 分钟还没有下载到可用的视频文件，立即切换到此回退策略。

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

## Step 6: 清理

- 删除临时下载/压缩的视频文件（`video.mp4`、`video_compressed.mp4` 等）
- 只保留最终的 `.md` 知识文档
- 如果是小红书视频，关闭 Playwright 浏览器实例

## 注意事项

- **Cookie 安全**：小红书 Cookie 只在当前会话使用，不要写入文档或日志
- **编码问题**：Windows 下 Python print 中文可能乱码，用 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` 解决
- **视频质量 vs 文件大小**：压缩是必要的折中，优先保证语音可辨识，画面清晰度可适度降低
- **下载超时防线**：从 Step 2 开始 5 分钟内没拿到可用的视频文件，立刻降级到文本分析，不要死磕

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
