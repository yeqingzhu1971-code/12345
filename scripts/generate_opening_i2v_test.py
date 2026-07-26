from __future__ import annotations

import base64
import json
import re
import shutil
from pathlib import Path

from gradio_client import Client, file
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

OUT = Path("video_i2v_output")
OUT.mkdir(parents=True, exist_ok=True)
WORK = OUT / "work"
WORK.mkdir(parents=True, exist_ok=True)

# Decode the compact approved visual reference stored in the repository.
encoded = Path("assets/shot01_ref_q20.b64").read_text(encoding="utf-8")
encoded = re.sub(r"[^A-Za-z0-9+/=]", "", encoded)
if "==" in encoded:
    encoded = encoded.split("==", 1)[0] + "=="
elif "=" in encoded:
    encoded = encoded.split("=", 1)[0] + "="
raw_path = WORK / "shot01_raw.jpg"
raw_path.write_bytes(base64.b64decode(encoded, validate=False))

# Reframe the lounge as a quiet four-seat suite instead of an open hall.
with Image.open(raw_path) as source_image:
    source_image.load()
    image = source_image.convert("RGB")
image = image.crop((62, 0, 578, 360)).resize((1024, 576), Image.Resampling.LANCZOS)
image = ImageEnhance.Color(image).enhance(0.55)
image = ImageEnhance.Brightness(image).enhance(0.78)
image = ImageEnhance.Contrast(image).enhance(1.12)

# Add understated smoked-glass/walnut side partitions to reinforce privacy.
overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)
draw.rectangle((0, 0, 122, 576), fill=(19, 22, 25, 150))
draw.rectangle((902, 0, 1024, 576), fill=(19, 22, 25, 150))
draw.rectangle((112, 0, 132, 576), fill=(52, 39, 30, 205))
draw.rectangle((892, 0, 912, 576), fill=(52, 39, 30, 205))
overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.2))
image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
ref_path = WORK / "shot01_private_reframed.jpg"
image.save(ref_path, quality=94, subsampling=0)

PROMPT = """
Preserve the exact same East Asian male identity, hairstyle, facial proportions, thin gold wire-frame glasses, all-black clothing, chair, window geometry and rainy airport composition from the input image. Create a single continuous six-second photorealistic live-action shot. The man remains seated alone in a private semi-enclosed first-class quiet suite; only subtle natural breathing, one blink, a slight downward eye movement toward the phone, and a small controlled thumb movement. Rain droplets slowly travel down the glass; an A380 and two distant service vehicles move subtly outside. The camera performs an extremely slow, stable dolly-in of only a few centimetres. Dense lead-grey sky, low saturation, cool overcast light, almost no warm lighting. Restrained premium romantic drama, realistic skin, coherent hands, stable glasses, natural motion, temporal consistency. No dialogue, no narration, no text.
""".strip()

NEGATIVE = """
identity change, different face, different haircut, black frame glasses, missing glasses, open crowded lobby, large public hall, orange light, bright warm lighting, blue sky, sunshine, high saturation, standing up, talking, exaggerated gestures, moving chair, warped hands, extra fingers, face morph, camera shake, flicker, jitter, static image, slideshow, subtitles, text, watermark, logo
""".strip()

client = Client("Lightricks/ltx-video-distilled", verbose=True)
video_result, seed = client.predict(
    prompt=PROMPT,
    negative_prompt=NEGATIVE,
    input_image_filepath=file(str(ref_path)),
    input_video_filepath=None,
    height_ui=576,
    width_ui=1024,
    mode="image-to-video",
    duration_ui=6.0,
    ui_frames_to_use=9,
    seed_ui=728310,
    randomize_seed=False,
    ui_guidance_scale=1.0,
    improve_texture_flag=True,
    api_name="/image_to_video",
)

source = video_result.get("video") if isinstance(video_result, dict) else str(video_result)
if not source:
    raise RuntimeError(f"No video returned: {video_result!r}")
destination = OUT / "shot_01_heathrow_private_lounge_i2v.mp4"
shutil.copy2(Path(source), destination)

manifest = {
    "space": "Lightricks/ltx-video-distilled",
    "endpoint": "/image_to_video",
    "seed": seed,
    "duration_seconds": 6.0,
    "resolution": [1024, 576],
    "reference": str(ref_path),
    "output": destination.name,
    "prompt": PROMPT,
    "negative_prompt": NEGATIVE,
}
(OUT / "generation_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
