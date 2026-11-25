# 用 edge-tts 為 8 鏡合成旁白，每鏡控制在 7 秒內，輸出 narration.wav 與 timings.json
# 用法：python3 tts.py   （需能連線 speech.platform.bing.com）
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import NARR, SHOT, DUR, OUT

VOICE = "zh-TW-HsiaoChenNeural"
SR = 48000
TMP = os.path.join(OUT, "_tts")
os.makedirs(TMP, exist_ok=True)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p]).decode().strip())


def synth(text, rate, path):
    cmd = ["edge-tts", "--voice", VOICE, f"--rate={rate:+d}%", "--text", text, "--write-media", path]
    if os.environ.get("HTTPS_PROXY"):
        cmd[1:1] = ["--proxy", os.environ["HTTPS_PROXY"]]
    subprocess.run(cmd, check=True, capture_output=True)


timings = []
parts_wav = []
for i, parts in enumerate(NARR):
    rate, total = -5, 99.0
    while total > 6.95 and rate < 40:
        rate += 5
        seg_info = []
        for j, text in enumerate(parts):
            p = os.path.join(TMP, f"s{i}_{j}.mp3")
            synth(text, rate, p)
            seg_info.append([p, dur(p), text])
        total = sum(d for _, d, _ in seg_info) + 0.15
    t = i * SHOT + 0.25
    for p, d, text in seg_info:
        timings.append({"start": round(t, 3), "end": round(t + d, 3), "text": text, "file": p})
        t += d + 0.15
    print(f"shot {i+1}: {total:.2f}s rate +{rate}%", flush=True)

# 組合成 60 秒單聲道旁白軌
inputs, filt = [], []
for k, tm in enumerate(timings):
    inputs += ["-i", tm["file"]]
    ms = int(tm["start"] * 1000)
    filt.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,adelay={ms}[a{k}]")
mix = "".join(f"[a{k}]" for k in range(len(timings)))
filt.append(f"{mix}amix=inputs={len(timings)}:normalize=0,apad,atrim=0:{DUR}[out]")
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
                "-map", "[out]", "-ar", str(SR), "-ac", "1", os.path.join(OUT, "narration.wav")], check=True)
with open(os.path.join(OUT, "timings.json"), "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in tm.items() if k != "file"} for tm in timings], f, ensure_ascii=False, indent=1)
print("done")
