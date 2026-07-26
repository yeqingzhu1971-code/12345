from __future__ import annotations

import json
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

from gradio_client import Client

OUT = Path("chunk01_output")
OUT.mkdir(parents=True, exist_ok=True)

PROMPT = """
Single uninterrupted photorealistic live-action establishing shot of London Heathrow Terminal 3 airport apron during a cold autumn rainstorm. An Emirates Airbus A380 is parked stably at the gate beside the glass terminal. Dense lead-grey low clouds, a dim overcast morning that feels almost like evening, muted cool colours but still fully colour footage, no blue sky and no warm sunlight. Fine rain falls continuously; rainwater streams down foreground glass and creates ripples across the wet tarmac. Two realistic ground-service vehicles move slowly and coherently, their small amber beacons reflecting in puddles. Subtle mist drifts near the runway. The camera makes one extremely slow, smooth cinematic push-in with no cut and no shake. Premium restrained Chinese romantic drama, physically plausible airport operations, high temporal consistency, detailed wet reflections, natural motion, 35 mm cinema lens. No foreground people, no subtitles, no captions, no narration, no logos added by the model, no black-and-white filter, no time-lapse, no sudden aircraft movement.
""".strip()

client = Client("Wan-AI/Wan2.1", verbose=True)
try:
    client.predict(api_name="/switch_t2v_tab")
except Exception:
    pass

submit = client.predict(
    prompt=PROMPT,
    size="1280*720",
    watermark_wan=False,
    seed=20260726,
    api_name="/t2v_generation_async",
)
print("SUBMIT", repr(submit), flush=True)


def find_video(value: Any) -> tuple[str, str] | None:
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return ("url", value)
        if value and Path(value).exists():
            return ("path", value)
    if isinstance(value, dict):
        for key in ("video", "path", "url", "file", "value"):
            if key in value and value[key] is not None:
                found = find_video(value[key])
                if found:
                    return found
        for nested in value.values():
            found = find_video(nested)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for nested in value:
            found = find_video(nested)
            if found:
                return found
    return None


result = None
history = []
# The official free cloud queue can take roughly 18–25 minutes at 720p.
for attempt in range(120):
    time.sleep(15 if attempt else 5)
    try:
        status = client.predict(api_name="/status_refresh")
    except Exception as exc:
        history.append({"attempt": attempt + 1, "error": repr(exc)})
        print("POLL_ERROR", attempt + 1, repr(exc), flush=True)
        continue
    history.append({"attempt": attempt + 1, "status": repr(status)[:3000]})
    print("POLL", attempt + 1, repr(status), flush=True)
    found = find_video(status)
    if found:
        result = found
        break

(OUT / "poll_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
if not result:
    raise RuntimeError("Wan2.1 did not return a downloadable video within the 30-minute polling window")

kind, source = result
destination = OUT / "opening_chunk01_heathrow_establishing_wan21.mp4"
if kind == "url":
    urllib.request.urlretrieve(source, destination)
else:
    shutil.copy2(Path(source), destination)

manifest = {
    "segment": "01",
    "generator": "Wan-AI/Wan2.1 official Space",
    "endpoint": "/t2v_generation_async + /status_refresh",
    "resolution_requested": "1280x720",
    "seed": 20260726,
    "prompt": PROMPT,
    "output": destination.name,
    "submit_result": repr(submit),
    "poll_attempts": len(history),
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
