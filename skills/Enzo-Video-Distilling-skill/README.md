# Enzo Video Distilling Skill

将网页视频内容转化为高质量的结构化 Markdown 知识文档。

## 支持平台

- 小红书 / RedNote / XiaoHongShu
- YouTube
- Bilibili
- 其他直接视频链接
- 本地 MP4 文件

## 触发场景

用户提供视频链接要求"总结""蒸馏""提炼知识点""分析内容"时使用。

## 核心流程

```
输入(URL/文件) → 获取视频 → 压缩(如需) → AI分析 → 生成文档 → 清理
```

## 安装

将 `SKILL.md` 放入 Claude Code 的 skills 目录：

```
.claude/skills/Enzo-Video-Distilling-skill/SKILL.md
```

## 依赖

- **XHS-Downloader**：小红书视频下载（可选，有则更稳定）
- **ffmpeg**：视频压缩
- **Python** + `requests`, `playwright`（小红书场景）
- **MCP 工具**：`zai-vision`（视频分析）、`yt-dlp`（YouTube/B站下载）、`webscraper`

## License

MIT
