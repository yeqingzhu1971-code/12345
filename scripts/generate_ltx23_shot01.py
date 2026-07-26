from __future__ import annotations

import base64
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

OUT = Path("ltx23_output")
WORK = OUT / "work"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

parts = sorted(Path("assets").glob("shot01_ref_q45.part*.b64"))
if len(parts) != 5:
    raise RuntimeError(f"Expected 5 reference chunks, found {len(parts)}: {parts}")
encoded = "".join(p.read_text(encoding="utf-8").strip() for p in parts)
raw = base64.b64decode(encoded, validate=True)
actual_sha = hashlib.sha256(raw).hexdigest()
if len(raw) < 25000:
    raise RuntimeError(f"Reference payload unexpectedly small: {len(raw)} bytes")
source_path = WORK / "shot01_source_reconstructed.jpg"
source_path.write_bytes(raw)

with Image.open(source_path) as source_image:
    source_image.load()
    source = source_image.convert("RGB")
if source.width < 700 or source.height < 400:
    raise RuntimeError(f"Reference dimensions unexpectedly small: {source.size}")

# Mobile/cloud generation pattern: coherent lower-resolution temporal generation first,
# followed by learned spatial upscaling in a separate cloud pass.
frame = source.crop((190, 55, 750, 370)).resize((768, 432), Image.Resampling.LANCZOS)
frame = ImageEnhance.Color(frame).enhance(0.43)
frame = ImageEnhance.Brightness(frame).enhance(0.72)
frame = ImageEnhance.Contrast(frame).enhance(1.13)
cool = Image.new("RGB", frame.size, (54, 66, 76))
frame = Image.blend(frame, cool, 0.14)

overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)
draw.rectangle((0, 0, 59, 432), fill=(12, 16, 19, 185))
draw.rectangle((709, 0, 768, 432), fill=(12, 16, 19, 185))
draw.rectangle((54, 0, 66, 432), fill=(41, 32, 27, 190))
draw.rectangle((702, 0, 714, 432), fill=(41, 32, 27, 190))
overlay = overlay.filter(ImageFilter.GaussianBlur(radius=3))
frame = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")

vignette = Image.new("L", frame.size, 0)
vd = ImageDraw.Draw(vignette)
vd.ellipse((-130, -80, 898, 560), fill=255)
vignette = vignette.filter(ImageFilter.GaussianBlur(radius=78))
dark = Image.new("RGB", frame.size, (8, 11, 14))
frame = Image.composite(frame, dark, vignette)
reference_path = WORK / "shot01_private_suite_reference.jpg"
frame.save(reference_path, quality=97, subsampling=0)

PROMPT = """
Single uninterrupted live-action cinematic shot. Preserve the exact East Asian male identity, facial proportions, black side-parted hair, thin gold wire-frame glasses, matte black shirt, dark trousers, seated pose, phone, armchair, rain-streaked glazing and A380 placement from the reference image. He is Jiang Yan, 28, restrained and steady on the outside, privately anxious and tired. The lounge reads as a private semi-enclosed first-class quiet suite with only four seats, tall smoked-glass and walnut partitions, dark stone and muted bronze details, never a public hall. He remains seated. Animate only subtle natural breathing, one blink, a tiny shift of focus down to the phone, one controlled thumb movement, and a slight tightening of the jaw. Rainwater continuously trails down the glass; a distant service vehicle moves slowly while the A380 remains stable. The camera performs a very slow, perfectly stable dolly-in, no cuts. Dense lead-grey Heathrow sky, low saturation, cool overcast illumination, almost no warm light. Realistic skin, coherent hands, stable glasses, natural cloth movement, physically plausible temporal motion, premium restrained Chinese romantic drama, 35 mm lens, shallow depth of field. No speech, no narration, no subtitles, no screen text, no logo.
""".strip()


def find_media(value: Any) -> tuple[str, str] | None:
    if isinstance(value, Path):
        return ("path", str(value))
    if isinstance(value, str):
        if value.startswith(("https://", "http://")):
            return ("url", value)
        if value and value.lower() != "none":
            return ("path", value)
        return None
    if isinstance(value, dict):
        for key in ("path", "url", "video", "file", "value"):
            if key in value and value[key] is not None:
                found = find_media(value[key])
                if found:
                    return found
        for nested in value.values():
            found = find_media(nested)
            if found:
                return found
    if isinstance(value, (tuple, list)):
        for nested in value:
            found = find_media(nested)
            if found:
                return found
    return None


client = Client("Lightricks/LTX-2-3", verbose=True)
raw_result = client.predict(
    input_image=handle_file(str(reference_path)),
    prompt=PROMPT,
    duration=3.0,
    enhance_prompt=False,
    seed=728310,
    randomize_seed=False,
    height=432,
    width=768,
    api_name="/generate_video",
)
print("RAW_RESULT:", repr(raw_result), flush=True)

used_seed = raw_result[1] if isinstance(raw_result, (tuple, list)) and len(raw_result) > 1 else 728310
media_value = raw_result[0] if isinstance(raw_result, (tuple, list)) and raw_result else raw_result
found = find_media(media_value)
if not found:
    raise RuntimeError(f"No downloadable video returned: {raw_result!r}")
kind, source_video = found

destination = OUT / "shot01_heathrow_private_suite_ltx23.mp4"
if kind == "url":
    urllib.request.urlretrieve(source_video, destination)
else:
    local_path = Path(source_video)
    if not local_path.exists():
        raise RuntimeError(f"Returned local video path does not exist: {local_path}; result={raw_result!r}")
    shutil.copy2(local_path, destination)

manifest = {
    "generator": "Lightricks/LTX-2-3",
    "endpoint": "/generate_video",
    "pipeline_stage": "temporal_generation_before_spatial_upscale",
    "input_size_bytes": len(raw),
    "input_sha256": actual_sha,
    "seed": used_seed,
    "duration_seconds": 3.0,
    "resolution": [768, 432],
    "reference": reference_path.name,
    "video": destination.name,
    "prompt": PROMPT,
    "raw_result_type": type(raw_result).__name__,
}
(OUT / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(manifest, ensure_ascii=False, indent=2))
