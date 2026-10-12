# Enzo Video Distilling Skill（完整版）

将网页视频内容转化为高质量的结构化 Markdown 知识文档。**完整覆盖：小红书 / 抖音 / B站 / YouTube / 本地文件 / 其他直链。**

> 抖音为本次新增能力——因反爬机制 `yt-dlp` 直连必失败，本技能改用「Cookie 直连抖音 Web API + 本地 Whisper 转写」一条龙攻克，详见 `SKILL.md` 的 Step 2C。

## 支持平台

- 小红书 / RedNote / XiaoHongShu（XHS-Downloader / Playwright）
- **抖音 / Douyin（Cookie 直连 API + Whisper 转写，本次新增）**
- YouTube
- Bilibili
- 其他直接视频链接
- 本地 MP4 文件

## 触发场景

用户提供视频链接要求"总结""蒸馏""提炼知识点""分析内容"时使用；也适用于"像之前一样帮我蒸馏这个视频"、发小红书/抖音链接要求总结等。

## 核心流程

```
输入(URL/文件) → 判断平台 → 获取视频 → 压缩(如需) → AI分析/转写 → 生成文档 → 清理
```

## 安装

**WorkBuddy：**
```bash
cp -r Enzo-Video-Distilling-skill ~/.workbuddy/skills/
```

**Claude Code：**
```
.claude/skills/Enzo-Video-Distilling-skill/SKILL.md
```

## 依赖

- **ffmpeg**：视频压缩、抽音频
- **Python** + `requests`, `playwright`（小红书场景）
- **yt-dlp**（MCP 或命令行，用于 YouTube/B站；**抖音不可用**）
- **faster-whisper**（抖音口播转写，模型用 `scripts/download_model.py` 拉取）
- **MCP 工具（可选）**：`zai-vision`（视频视觉分析，有则用路径 A；无则用 Whisper 路径 B）、`webscraper`

## 抖音专属脚本（scripts/）

- `download_douyin.py <video_id>`：验证 + 聚合直链 + 下载
- `download_model.py`：`faster-whisper-small` 模型断点续传
- `transcribe.py`：`wave+numpy` 绕 PyAV 转写

## License

MIT
