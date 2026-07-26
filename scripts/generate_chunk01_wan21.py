from __future__ import annotations

import base64
import json
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

OUT = Path("chunk01_output")
OUT.mkdir(parents=True, exist_ok=True)
REF = OUT / "chunk01_heathrow_reference.jpg"
REF.write_bytes(base64.b64decode(Path("assets/chunk01_ref.b64").read_text().strip(), validate=True))

PROMPT = """
A single continuous live-action cinematic establishing shot of London Heathrow Terminal 3 apron in cold autumn rain, based exactly on the input image. Dense lead-grey low clouds, low saturation, no blue sky, no warm sunrise. Rain falls naturally and water ripples across the wet tarmac. Two ground-service vehicles move slowly and coherently, beacon lights reflecting in puddles. The Emirates A380 remains stable at the gate while subtle atmospheric mist drifts. The camera performs a very slow smooth push-in with no cut and no shake. Photorealistic, premium restrained Chinese romantic drama, realistic airport operations, temporal consistency, detailed wet reflections, natural motion. No people in foreground, no subtitles, no text, no logo, no narration, no black-and-white filter.
""".strip()

client = Client("Wan-AI/Wan2.1", verbose=True)
try:
    client.predict(api_name="/switch_i2v_tab")
except Exception:
    pass

submit = client.predict(
    prompt=PROMPT,
    image=handle_file(str(REF)),
    watermark_wan=False,
    seed=20260726,
    api_name="/i2v_generation_async",
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
for attempt in range(60):
    time.sleep(15 if attempt else 5)
    try:
        status = client.predict(api_name="/status_refresh_1")
    except Exception as exc:
        history.append({"attempt": attempt + 1, "error": repr(exc)})
        print("POLL_ERROR", attempt + 1, repr(exc), flush=True)
        continue
    history.append({"attempt": attempt + 1, "status": repr(status)[:2000]})
    print("POLL", attempt + 1, repr(status), flush=True)
    found = find_video(status)
    if found:
        result = found
        break

(OUT / "poll_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
if not result:
    raise RuntimeError("Wan2.1 did not return a downloadable video within the polling window")

kind, source = result
destination = OUT / "opening_chunk01_heathrow_establishing_wan21.mp4"
if kind == "url":
    urllib.request.urlretrieve(source, destination)
else:
    shutil.copy2(Path(source), destination)

manifest = {
    "segment": "01",
    "generator": "Wan-AI/Wan2.1 official Space",
    "endpoint": "/i2v_generation_async + /status_refresh_1",
    "seed": 20260726,
    "prompt": PROMPT,
    "reference": REF.name,
    "output": destination.name,
    "submit_result": repr(submit),
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
