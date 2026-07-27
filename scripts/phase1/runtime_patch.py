from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"{label}: already applied")
        return text
    if old not in text:
        raise SystemExit(f"{label}: insertion point not found")
    print(f"{label}: applied")
    return text.replace(old, new, 1)


if len(sys.argv) != 2:
    raise SystemExit("usage: runtime_patch.py <builder.py>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''    import mpfb  # type: ignore\n\n    defaults = {\n''',
    '''    import mpfb  # type: ignore\n\n    # MPFB is a Blender extension. A source checkout has no registered extension\n    # repository, so provide its writable user path before LocationService starts.\n    mpfb_user_home = OUT / "mpfb_user"\n    mpfb_user_home.mkdir(parents=True, exist_ok=True)\n    bpy.utils.extension_path_user = lambda package, *args, **kwargs: str(mpfb_user_home)\n\n    defaults = {\n''',
    "mpfb_headless_extension_path",
)

text = replace_once(
    text,
    '''def set_world(scene: bpy.types.Scene, color: tuple[float, float, float], strength: float) -> None:\n    scene.world.use_nodes = True\n    bg = scene.world.node_tree.nodes.get("Background")\n''',
    '''def set_world(scene: bpy.types.Scene, color: tuple[float, float, float], strength: float) -> None:\n    if scene.world is None:\n        scene.world = bpy.data.worlds.new(f"{scene.name}_World")\n    scene.world.use_nodes = True\n    bg = scene.world.node_tree.nodes.get("Background")\n''',
    "scene_world_initialization",
)

text = replace_once(
    text,
    '''    mat.surface_render_method = "DITHERED" if alpha < 0.999 else "DITHERED"\n''',
    '''    if hasattr(mat, "surface_render_method"):\n        try:\n            mat.surface_render_method = "DITHERED"\n        except Exception:\n            pass\n''',
    "material_surface_mode_guard",
)

text = replace_once(
    text,
    '''    scene.view_settings.look = "AgX - Medium High Contrast"\n''',
    '''    try:\n        scene.view_settings.look = "AgX - Medium High Contrast"\n    except Exception:\n        pass\n''',
    "agx_look_guard",
)

path.write_text(text, encoding="utf-8")
print(f"patched {path} ({len(text)} characters)")
