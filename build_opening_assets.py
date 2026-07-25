import bpy, math, os, sys, json, traceback, importlib
from mathutils import Vector

OUTPUT = os.environ.get('OUTPUT_DIR', os.path.join(os.getcwd(), 'output'))
os.makedirs(OUTPUT, exist_ok=True)

# ---------- basic helpers ----------
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        pass

def mat(name, base, metallic=0.0, rough=0.5, transmission=0.0, alpha=1.0, emission=None, emission_strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*base, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = rough
    if 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    elif 'Transmission' in bsdf.inputs:
        bsdf.inputs['Transmission'].default_value = transmission
    bsdf.inputs['Alpha'].default_value = alpha
    if emission:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (*emission,1)
            bsdf.inputs['Emission Strength'].default_value = emission_strength
        elif 'Emission' in bsdf.inputs:
            bsdf.inputs['Emission'].default_value = (*emission,1)
    if alpha < 1.0:
        m.surface_render_method = 'DITHERED'
    return m

def assign(obj, material):
    if hasattr(obj.data, 'materials'):
        obj.data.materials.clear(); obj.data.materials.append(material)

def box(name, loc, scale, material, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new('Bevel','BEVEL'); mod.width=bevel; mod.segments=3
    assign(o, material)
    return o

def uv(name, loc, scale, material, seg=48, rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(o, material)
    bpy.ops.object.shade_smooth()
    return o

def cyl(name, loc, radius, depth, material, rot=(0,0,0), vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; assign(o, material); bpy.ops.object.shade_smooth(); return o

def torus(name, loc, major, minor, material, rot=(0,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=64, minor_segments=12, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; assign(o, material); return o

def plane(name, loc, size, material, rot=(0,0,0)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; assign(o, material); return o

def text_obj(body, loc, size=0.4, extrude=0.01, material=None, rot=(math.pi/2,0,0), align='CENTER'):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    o=bpy.context.object; o.data.body=body; o.data.align_x=align; o.data.size=size; o.data.extrude=extrude
    if material: assign(o, material)
    return o

def look_at(obj, target):
    direction = Vector(target)-obj.location
    obj.rotation_euler = direction.to_track_quat('-Z','Y').to_euler()

def camera(name, loc, target, lens=50):
    bpy.ops.object.camera_add(location=loc)
    c=bpy.context.object; c.name=name; c.data.lens=lens; look_at(c,target); return c

def area_light(name, loc, energy, size, color=(1,1,1), target=None):
    bpy.ops.object.light_add(type='AREA', location=loc)
    l=bpy.context.object; l.name=name; l.data.energy=energy; l.data.shape='RECTANGLE'; l.data.size=size; l.data.color=color
    if target: look_at(l,target)
    return l

def point_light(name, loc, energy, color=(1,1,1), radius=0.25):
    bpy.ops.object.light_add(type='POINT', location=loc)
    l=bpy.context.object; l.name=name; l.data.energy=energy; l.data.color=color; l.data.shadow_soft_size=radius; return l

def setup_world(world_color=(0.03,0.04,0.06,1)):
    sc=bpy.context.scene
    sc.render.engine='BLENDER_EEVEE_NEXT'
    sc.render.resolution_x=960; sc.render.resolution_y=540; sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'
    sc.render.film_transparent=False
    sc.render.fps=24
    sc.world.color=world_color[:3]
    sc.view_settings.look='AgX - Medium High Contrast'

def render(path, cam):
    sc=bpy.context.scene; sc.camera=cam; sc.render.filepath=path; bpy.ops.render.render(write_still=True)

def export_glb(path):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_visible=True, export_apply=True)

def save_blend(path):
    bpy.ops.wm.save_as_mainfile(filepath=path)

def add_metadata(obj, **kwargs):
    for k,v in kwargs.items(): obj[k]=v

def parent_keep(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world
    return obj

# ---------- characters ----------
_MPFB_READY=False
def register_mpfb():
    global _MPFB_READY
    if _MPFB_READY:
        return True
    mpfb_src=os.environ.get('MPFB_SRC')
    if not mpfb_src or not os.path.isdir(mpfb_src): return False
    if mpfb_src not in sys.path: sys.path.insert(0, mpfb_src)
    try:
        import mpfb
        mpfb.register()
        _MPFB_READY=True
        return True
    except Exception:
        traceback.print_exc(); return False

def dyn(pkg,key):
    for amod in list(sys.modules):
        if amod.endswith(pkg):
            mod=importlib.import_module(amod)
            return getattr(mod,key)
    raise RuntimeError(pkg)

def primitive_human(name, female=True, height=1.75, loc=(0,0,0)):
    skin=mat(name+'_skin',(0.78,0.55,0.43) if not female else (0.92,0.72,0.62),rough=0.42)
    dark=mat(name+'_hair',(0.008,0.01,0.012),rough=0.28)
    root=bpy.data.objects.new(name,None); bpy.context.collection.objects.link(root); root.location=loc
    # proportions in meters
    pelvis_z=0.92*height/1.75; torso_z=1.25*height/1.75; head_z=1.61*height/1.75
    torso=uv(name+'_Torso',(loc[0],loc[1],torso_z),(0.20 if female else 0.23,0.13,0.32),skin); parent_keep(torso,root)
    pelvis=uv(name+'_Pelvis',(loc[0],loc[1],pelvis_z),(0.18 if female else 0.19,0.14,0.20),skin); parent_keep(pelvis,root)
    neck=cyl(name+'_Neck',(loc[0],loc[1],1.45*height/1.75),0.055,0.15,skin); parent_keep(neck,root)
    head=uv(name+'_Head',(loc[0],loc[1]-0.005,head_z),(0.105,0.09,0.14),skin); parent_keep(head,root)
    # limbs
    for side,sgn in [('L',-1),('R',1)]:
        x=loc[0]+sgn*(0.16 if female else 0.19)
        upper=cyl(f'{name}_{side}_UpperArm',(x,loc[1],1.27*height/1.75),0.052,0.38,skin,rot=(0.06,0,0)); parent_keep(upper,root)
        lower=cyl(f'{name}_{side}_LowerArm',(x,loc[1],0.91*height/1.75),0.044,0.36,skin); parent_keep(lower,root)
        hand=uv(f'{name}_{side}_Hand',(x,loc[1],0.69*height/1.75),(0.052,0.035,0.095),skin); parent_keep(hand,root)
        lx=loc[0]+sgn*(0.085 if female else 0.095)
        thigh=cyl(f'{name}_{side}_Thigh',(lx,loc[1],0.66*height/1.75),0.075,0.58,skin); parent_keep(thigh,root)
        shin=cyl(f'{name}_{side}_Shin',(lx,loc[1],0.28*height/1.75),0.057,0.58,skin); parent_keep(shin,root)
        foot=uv(f'{name}_{side}_Foot',(lx,loc[1]-0.05,0.07),(0.075,0.16,0.055),skin); parent_keep(foot,root)
    # hair cap and face guides
    uv(name+'_HairCap',(loc[0],loc[1],head_z+0.03),(0.115,0.095,0.011),dark)
    if female: uv(name+'_Bun',(loc[0],loc[1]+0.05,head_z+0.14),(0.075,0.06,0.075),dark)
    root['height_cm']=height*100; root['identity_version']='revised_v01'; root['use_original_uploaded_model']=False
    return root

def create_human(name,female,height,loc,mpfb_ok):
    if mpfb_ok:
        try:
          HS = dyn("mpfb.services.humanservice","HumanService")
          TS = dyn("mpfb.services.targetservice","TargetService")
          HOP = dyn("mpfb.entities.objectproperties","HumanObjectProperties")
          h=HS.create_human();  h.name=name; h.location=loc
          # apply long/slender young Asian base proportions with macro controls
          HOP.set_value('gender', 1.0 if female else 0.0, entity_reference=h)
          HOP.set_value('asian', 1.0, entity_reference=h)
          HOP.set_value('african', 0.0, entity_reference=h)
          HOP.set_value('caucasian', 0.0, entity_reference=h)
          HOP.set_value('age', 0.17 if female else 0.26, entity_reference=h)
          HOP.set_value('muscle', 0.43 if female else 0.57, entity_reference=h)
          HOP.set_value('weight', 0.38 if female else 0.48, entity_reference=h)
          HOP.set_value('height', 0.68 if female else 0.75, entity_reference=h)
          HOP.set_value('proportions', 0.69 if female else 0.62, entity_reference=h)
          TS.reapply_macro_details(h)
          HS.add_builtin_rig(h, 'game_engine')
          h['height_cm']=height*100; h['identity_version']='revised_v01'; h['use_original_uploaded_model']=False
          return h
        except Exception: traceback.print_exc()
    return primitive_human(name,female,height,loc)

def add_female_outfit(root,loc):
    black=mat('Female_Practice_Black',(0.008,0.008,0.012),rough=0.58)
    grey=mat('Female_Washed_Grey',(0.26,0.28,0.31),rough=0.65)
    # simple leotard / trousers overlay that works for both MPFB and fallback bodies
    box('FEM_Trousers_Waist',(loc[0],loc[1],0.88),(0.18,0.12,0.18),black,0.06)
    for sgn in (-1,1):
        cyl('FEM_Trousers_Leg',(loc[0]+sgn*0.085,loc[1],0.48),0.085,0.76,black)
    box('FEM_Practice_Top',(loc[0],loc[1],1.22),(0.21,0.12,0.25),grey,0.08)

def add_glasses(loc,gold=True):
    frame=mat('Gold_Wire_Glasses' if gold else 'Black_Frame_Glasses',(0.67,0.41,0.15) if gold else (0.01,0.01,0.01),metallic=1.0,rough=0.18)
    for sgm in (-1,1):
        torus('Glasses_Lens_Fit',(loc[0]+sgm*0.058,loc[1]-0.08,loc[2]+1.62), 0.048,0.0055,frame,rot=(math.pi/2,0,0))
    cyl('Glasses_Bridge',(loc[0],loc[1]-0.08,loc[2]+1.62),0.007,0.04,frame,rot=(0,math.pi/2,0))

def add_male_outfit(root,loc):
    black=mat('Male_All_Black_Outfit',(0.005,0.005,0.007),rough=0.49)
    coat=mat('Male_Deep_Coat',(0.015,0.018,0.025),rough=0.62)
    box('MAL_Trousers_Waist',(loc[0],loc[1],0.90),(0.19,0.13,0.18),black,0.06)
    for sgn in (-1,1):
        cyl('MAL_Trousers_Leg',(loc[0]+sgn*0.09,loc[1],0.48),0.09,0.78,black)
    box('MAL_Black_Shirt',(loc[0],loc[1],1.25),(0.24,0.14,0.28),black,0.08)
    box('MAL_Long_Coat',(loc[0],loc[1]+0.04KŒJK
ŒÌŒNŒ
KÛØ]ŒL
BˆYÙÛ\ÜÙ\ÊØËYJB‚ˆÈKKKKKKKKKHÝ[™ÙHKKKKKKKKKB™YˆZ[ÛÝ[™ÙJ[˜ÛYWØÚ\˜XÝ\UYJN‚ˆÛX\—ÜØÙ[™J
NÈÙ]\ÝÛÜ›

Œ‹ŒKŒÍKJJBˆÝÛ™O[X]
	ÕØ\›WÔÝÛ™IË
MKLKŠK›ÝYÚLŒÎ
BˆØ[][X]
	ÑY\ÕØ[]	Ë
ŒL‹ŒMKŒJK›ÝYÚLŒÍJBˆœ›Ûž™O[X]
	Ðœ\ÚYÐœ›Ûž™IË
ŒÍ‹ŒNKŒŠKY][XÏLŽK›ÝYÚLŒŠBˆX]\[X]
	ÐØ[Y[ÓX]\‰Ë
ËŒŒKŒJK›ÝYÚLŠBˆ›YO[X]
	ÓZYšYÚÐ›YWÐØ\œ]	Ë
ŒMŒÌ‹ŒÍJK›ÝYÚLŽM
BˆÛ\ÜÏ[X]
	ÔÛ[ÚÙYÑÛ\ÜÉË
Œ‹ŒKŒLŠKY][XÏLŒK›ÝYÚLŒN˜[œÛZ\ÜÚ[ÛLMK[OLMJBˆ˜Z[[X]
	Ô˜Z[™›ÜÑÛ\ÜÉË
KMKJK›ÝYÚLŒ˜[œÛZ\ÜÚ[ÛLŽ[OLŒJBˆØ\›O[X]
	ÕØ\›WÑ[Z\ÜÚ[Û‰Ë
KM‹ŒJK›ÝYÚL[Z\ÜÚ[ÛJKKŒMJK[Z\ÜÚ[Û—ÜÝ™[™ÝL‹JBˆÈÚ[Œ›HL›HË›Bˆ›Þ
	ÓÝ[™ÙWÑ›ÛÜ‰Ë
LŒMJK
LK‹ŒMJK›YK
Bˆ›Þ
	ÐÙZ[[™ÉË
ËJK
LK‹ŒMJKØ[]
Bˆ›Þ
	Ð˜XÚÕØ[	Ë
‹KÍJK
LKŒMKKÍJKØ[]ŒŠBˆ›Þ
	ÓYØ[	Ë
LLKKÍJK
ŒMK‹KÍJKÝÛ™KŒŠBˆÈÚ[™ÝÈØ[[™][[ÛœÂˆ›Þ
	ÕÚ[™ÝÑÛ\ÜÉË
LKKÍJK
Œ‹KÍJKÛ\ÜË
Bˆ›ÜˆH[ˆ˜[™ÙJMKŠNˆ›Þ
	ÕÚ[™ÝÓ][[Û‰Ë
LŽMKKËŒJK
ŒŒKËŒJKœ›Ûž™KŒJBˆÈ˜Z[˜›ÜÂˆ›ÜˆH[ˆ˜[™ÙJL
N‚ˆOKMKÊÌLK
Š
JŒÍÊINJKÎŒ
NÈLŒŠÌËŒÊŠ
JŒŒÊINMÊKÎM‹ŒˆÞ[
‰Ô˜Z[—Ñ›ÜÞÚNŒÙIË
LŽKŠKŒL‹ŒL
ÌŒŒ
Š]Ð¤°É…¥¸¤(€€€€Œ‰É½¹é”É¥Á…ÉÑ¥Ñ¥½¹Ì€¼ÅÕ¥•Ðé½¹”(€€€™½Èà¥¸€ ´Ð¸Ô°À¸Ð°Ð¸à¤è(€€€€€€€™½Èä¥¸€ ´Ì¸È°È¸ä¤è(€€€€€€€€€€€™½Èè¥¸€ À¸à°Ä¸Ø°È¸Ð¤è(€€€€€€€€€€€€€€€‰½à EÕ¥•ÑÉ¥œ°¡à±ä±è¤° À¸ÀÌ°Ä¸Ä°À¸ÀÌ¤±‰É½¹é”°À¸ÀÄ¤(€€€€Œ¡…¥ÉÌ(€€€™½È¤°¡à±ä±Éè¤¥¸•¹Õµ•É…Ñ”¡l ´Ø°´Ì°À¤° ´Ø°À°À¤° ´Ø°Ì°À¤° ´È°´Ì¸Ô°À¸È¤° ´È°À°À¸È¤° ´È°Ì¸Ô°À¸È¤° Ì¸È°´Ä¸Ð°´À¸Ð¤° Ì¸È°Ä¸Ð°À¸Ð¥t¤è(€€€€€€€Í•…Ðõ‰½à¡˜¡…¥É}í¤èÀÉ‘õ}M•…Ðœ°¡à±ä°À¸ÐÔ¤° À¸ÔÔ°À¸ØÔ°À¸ÄÔ¤±±•…Ñ¡•È°À¸ÄÈ¤(€€€€€€€‰½à¡˜¡…¥É}í¤èÀÉ‘õ}	…¬œ°£‚Ç’³ãSR¢†ÖF‚æ6÷2‡'¢’–b'£ÓÓVÇ6R’ÃãR’ÂƒãSRÃãRÃãr’ÆÆVF†W"Ãã"¢f÷"7‚–â‚ÓÃ“¢7–Â†bt6†—%÷¶“£&GÕôÆVu÷·7‡ÒrÂ‡‚·7‚£ãCRÇ’Ãã#"’ÃãRÃãCBÆ'&öç¦R¢&÷‚†buF&ÆU÷¶“£&GÒrÂ‡‚³ãÇ’ÃãCR’Âƒã3RÃãRÃã‚’Ç7FöæRÃãR¢2v÷&²öG2÷&—fFP¢f÷"’Ç’–âVçVÖW&FR‚‚Ó"ã‚ÃãÃ"ã‚’“ ¢&÷‚†buv÷&µöE÷¶—ÕõvÆÂrÂ‚Ó‚ã2Ç’ÃãR’Âƒã"ÃãÃãR’ÇvÆçWBÃãB¢&÷‚†buv÷&µöE÷¶—ÕôvÆ72rÂ‚ÓrãRÇ’ÃãR’Âƒã"ÃãÃãB’ÆvÆ72Ã¢2&V6WF–öâæBvFP¢&÷‚‚u&V6WF–öäFW6²rÂ‚ÓRãRÃRãÃãcR’Âƒã‚ÃãSRÃãcR’Ç7FöæRÃã¢&÷‚‚u&V6WF–öä&6¶G&÷rÂ‚ÓRãRÃRã‚Ãã‚’Âƒ"ãRÃãÃã‚’ÇvÆçWBÃã"¢FW‡Eöö&¢‚tTÔ•$DU24”täEU$RÄõTätRrÂ‚ÓRãRÃRãcrÃ"ãB’Ãã#2ÃãÆ'&öç¦RÇ&÷CÒ†ÖF‚ç’ó"ÃÃ’¢&÷‚‚t–çFW&æÄ&ö&F–ætvFRrÂƒ‚ã‚ÃBã"ÃãB’Âƒ"ãÃã3RÃãB’ÇvÆçWBÃãR¢FW‡Eöö&¢‚tD•$T5B$ô$D”är(i"CSrÂƒ‚ã‚Ã2ãƒ"Ã"ã"’Ãã#"ÃãÇv&ÒÇ&÷CÒ†ÖF‚ç’ó"ÃÃ’¢23ƒ7G–Æ—¦VB&6¶w&÷VæB÷WG6–FRv–æF÷rÂ&VÆ—7F–2æ6†÷"æ÷B'&æBW†7B&WÆ–6¢v†—FSÖÖB‚t—&7&gEõv†—FRrÂƒãs"ÃãsbÃãƒ"’ÆÖWFÆÆ–3ÓãRÇ&÷VvƒÓã3"¢&VCÖÖB‚uF–Åõ&VBrÂƒãS"ÃãÃã’Ç&÷VvƒÓã3b¢gW3Ö7–Â‚t3ƒôgW6VÆvRrÂƒBÃBã"Ãã’ÃãRÃrãRÇv†—FRÇ&÷CÒƒÆÖF‚ç’ó"Ã’ÇfW'F–6W3ÓcB¢7–Â‚t3ƒõF–ÂrÂƒrãBÃBã"Ã2ã’ÃãBÃã#RÇ&VBÇ&÷CÒƒÃÃ’¢f÷"‚–âƒã‚Ã"ã"Ã"ãbÃ2ã“ ¢f÷‚‚t3ƒõv–æF÷rrÂŒËŒKKŒÍJK
Œ‹ŒËŒŠKÛ\ÜËŒJBˆÈÙ[ÛY]šXÈÚ[™È[™[™Ú[™\Âˆ›Þ
	ÐLÎÕÚ[™ÉË
MŒ‹ŒËŽJK
ËŽŒMKŒMJKÚ]KŒŠBˆ›Üˆ[ˆ
L‹ŒËMKŒŠNˆÞ[
	ÐLÎÑ[™Ú[™IË

\
K†