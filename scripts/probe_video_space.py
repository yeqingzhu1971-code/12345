from __future__ import annotations

import json
import traceback
from pathlib import Path

from gradio_client import Client

OUT = Path("probe_output")
OUT.mkdir(parents=True, exist_ok=True)

SPACES = [
    "Lightricks/ltx-video-distilled",
    "Lightricks/ltx-2-3-spatial-upscaler",
    "Wan-AI/Wan2.2-S2V",
]

results: dict[str, object] = {}
for space in SPACES:
    try:
        client = Client(space, verbose=True)
        api = client.view_api(all_endpoints=True, print_info=False, return_format="dict")
        results[space] = {"status": "ok", "api": api}
    except Exception as exc:  # noqa: BLE001
        results[space] = {
            "status": "error",
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }

(OUT / "video_space_api.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
