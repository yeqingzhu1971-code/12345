import asyncio
import json
import os
from pathlib import Path

import edge_tts
from pydub import AudioSegment

OUT = Path("audio_output")
OUT.mkdir(exist_ok=True)

LINES = [
    {"id":"m01","start_ms":500,"text":"希思罗机场的落地玻璃上，蒙着细密的雨痕。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m02","start_ms":5500,"text":"铅灰色的云压得很低。上午十点，天光却像傍晚。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m03","start_ms":12500,"text":"这是我来英国读博的第二年。秋季学期刚过一个月，我又要回北京。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m04","start_ms":22500,"text":"家里的事情、公司的会议，还有那些永远说不完的话，挤在同一块屏幕里。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m05","start_ms":33500,"text":"我只想随便看点什么，让脑子安静一会儿。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m06","start_ms":40500,"text":"下一秒，一束北京的阳光，先撞进了眼里。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"f_friend","start_ms":48000,"text":"主席，等一下——","voice":"zh-CN-XiaoxiaoNeural","rate":"+7%","pitch":"+4Hz"},
    {"id":"f_hero","start_ms":50300,"text":"来了！","voice":"zh-CN-XiaoyiNeural","rate":"+10%","pitch":"+8Hz"},
    {"id":"m07","start_ms":55000,"text":"她穿着洗得发白的练功服，额前的碎发被汗打湿。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m08","start_ms":63500,"text":"她回头笑了一下。那一刻，我第一次觉得，伦敦的雨也没有那么冷。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m09","start_ms":74500,"text":"你知道吗？你笑起来的时候，好像一个明星。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
    {"id":"m10","start_ms":82500,"text":"她真正看到那条消息，是三百六十五天以后。","voice":"zh-CN-YunzeNeural","rate":"-12%","pitch":"-8Hz"},
]

async def synth(item):
    path = OUT / f"{item['id']}.mp3"
    comm = edge_tts.Communicate(item["text"], item["voice"], rate=item["rate"], pitch=item["pitch"])
    await comm.save(str(path))
    return path

async def main():
    for item in LINES:
        try:
            await synth(item)
        except Exception:
            # Fallback voices available on older Edge endpoints.
            if item["id"].startswith("m"):
                item["voice"] = "zh-CN-YunxiNeural"
            elif item["id"] == "f_friend":
                item["voice"] = "zh-CN-XiaoxiaoNeural"
            else:
                item["voice"] = "zh-CN-XiaoyiNeural"
            await synth(item)

    track = AudioSegment.silent(duration=90000, frame_rate=48000).set_channels(2)
    manifest = []
    for item in LINES:
        seg = AudioSegment.from_file(OUT / f"{item['id']}.mp3").set_frame_rate(48000).set_channels(2)
        # Heroine and friend are a touch more present; male remains restrained.
        seg = seg.apply_gain(2.0 if item["id"].startswith("f") else -1.0)
        track = track.overlay(seg, position=item["start_ms"])
        manifest.append({**item, "duration_ms": len(seg)})
    track.export(OUT / "dialogue_track.wav", format="wav")
    (OUT / "dialogue_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

asyncio.run(main())
