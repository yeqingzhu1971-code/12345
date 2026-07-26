from __future__ import annotations

import json
import shutil
from pathlib import Path

from gradio_client import Client

OUT = Path("video_output")
OUT.mkdir(parents=True, exist_ok=True)

PROMPT = """
A single continuous six-second live-action cinematic shot, 16:9. A handsome East Asian man, age 28, about 180 cm tall, refined but not flashy, short side-parted black hair, clean-shaven, wearing a matte black casual shirt, straight black trousers, a dark charcoal wool overcoat draped over one arm, and thin gold wire-frame glasses. He sits alone inside a very private semi-enclosed first-class quiet suite within an Emirates-inspired lounge at London Heathrow Terminal 3. The suite has only four seats, high walnut and smoked-glass partitions, dark stone, muted bronze trim, no open lobby feeling, no crowd. Through rain-streaked floor-to-ceiling glass, a large A380 is parked on a wet apron beneath a dense lead-grey sky. Almost no warm ambient lighting; only one dim table lamp far behind him. Low saturation, cool grey-blue palette, soft natural overcast light, realistic skin texture, subtle breathing and blinking, small hand movement as he looks down at his phone, rain moving down the glass, distant ground-service vehicles moving slowly. Camera makes a very slow controlled dolly-in from a medium-wide composition to a medium close-up. Natural physics, coherent anatomy, stable identity, 35mm cinema lens, shallow depth of field, premium restrained romantic drama, photorealistic, no narration, no subtitles, no on-screen text.
""".strip()

NEGATIVE = """
static photograph, slideshow, frozen person, excessive camera shake, bright blue sky, sunny weather, high saturation, orange lighting, golden luxury lobby, crowded airport hall, giant open lounge, palace, gaudy gold, warped face, identity change, extra fingers, fused hands, deformed glasses, floating objects, duplicated people, jitter, flicker, frame interpolation artifacts, low resolution, blurry image, illustration, anime, subtitles, captions, watermark, logo, text
""".strip()

client = Client("Lightricks/ltx-video-distilled", verbose=True)
result = client.predict(
    prompt=PROMPT,
    negative_prompt=NEGATIVE,
    input_image_filepath=None,
    input_video_filepath=None,
    height_ui=576,
    width_ui=1024,
    mode="text-to-video",
    duration_ui=6.0,
    ui_frames_to_use=9,
    seed_ui=728310,
    randomize_seed=False,
    ui_guidance_scale=1.0,
    improve_texture_flag=True,
    api_name="/text_to_video",
)

video_result, seed = result
if isinstance(video_result, dict):
    source = video_result.get("video") or video_result.get("path")
else:
    source = str(video_result)
if not source:
    raise RuntimeError(f"No video path returned: {result!r}")

source_path = Path(source)
destination = OUT / "shot_01_heathrow_private_lounge_test.mp4"
shutil.copy2(source_path, destination)

manifest = {
    "space": "Lightricks/ltx-video-distilled",
    "endpoint": "/text_to_video",
    "seed": seed,
    "duration_seconds": 6.0,
    "resolution": [1024, 576],
    "prompt": PROMPT,
    "negative_prompt": NEGATIVE,
    "output": destination.name,
}
(OUT / "generation_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
