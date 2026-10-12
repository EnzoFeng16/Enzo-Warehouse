# -*- coding: utf-8 -*-
"""用本地 model_small 转写 audio.wav (wave+numpy 绕开 PyAV 不兼容)。
输出 transcript.txt (带 [mm:ss->mm:ss] 时间戳) + transcript_full.txt (纯文本)。
"""
import os, sys

# 国内拉模型用镜像，避免 HF 直连慢/超时（加载本地目录时其实不需要联网）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from faster_whisper import WhisperModel

# 从本地目录加载（已下载到 model_small），避免再次联网
MODEL = "model_small"
print(f"加载模型 {MODEL} (CPU, int8) ...", flush=True)
model = WhisperModel(MODEL, device="cpu", compute_type="int8")

print("读取 audio.wav (绕过 PyAV) ...", flush=True)
import wave, numpy as np
wf = wave.open("audio.wav", "rb")
fr = wf.getframerate()
n = wf.getnframes()
raw = wf.readframes(n)
wf.close()
audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
print(f"采样率 {fr}, 样本数 {len(audio_np)}", flush=True)

# 人名/品牌密集的视频建议改用 "medium" 模型以提升准确率
segments, info = model.transcribe(
    audio_np,
    beam_size=5,
    language="zh",
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
)

def fmt(t):
    s = int(t)
    m = s // 60
    return f"{m:02d}:{s % 60:02d}"

lines = []
full = []
for seg in segments:
    line = f"[{fmt(seg.start)}->{fmt(seg.end)}] {seg.text.strip()}"
    lines.append(line)
    full.append(seg.text.strip())
    print(line, flush=True)

with open("transcript.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
with open("transcript_full.txt", "w", encoding="utf-8") as f:
    f.write("".join(full))

print(f"\n完成: 共 {len(lines)} 段, 全文字数 {len(''.join(full))}", flush=True)
