# SPDX-License-Identifier: GPL-3.0-or-later
"""Scene-side logic: dome/shell meshes, controller, sun drivers, rebuild."""
import math
import uuid
import bpy
from . import shaders, presets

COLL = "LV_Sky"
CTRL = "LV_Sky_Controller"
DOME = "LV_Sky_Dome"
SUN = "LV_Sun"
SHELL = "LV_Sky_Shell_"
CEL = "LV_Sky_Celestial"
SUNB = "LV_Sky_SunBody"
MOONB = "LV_Sky_MoonBody"
SUSPEND = [0]  # >0 while we edit properties from code (skip update-callback rebuilds)


class suspend:
    def __enter__(self):
        SUSPEND[0] += 1

    def __exit__(self, *a):
        SUSPEND[0] -= 1


# ------------------------------------------------------------------ meshes
def hemisphere_data(name, radius, ns=72, nr=28, below_deg=4.0):
    """Half sphere (a little below the horizon), faces pointing inward."""
    verts, faces = [], []
    e0 = -math.radians(below_deg)
    for i in range(nr):
        e = e0 + (math.pi / 2 - e0) * i / nr
        ce, se = math.cos(e), math.sin(e)
        for j in range(ns):
            a = 2 * math.pi * j / ns
            verts.append((radius * ce * math.cos(a), radius * ce * math.sin(a), radius * se))
    top = len(verts)
    verts.append((0.0, 0.0, radius))
    for i in range(nr - 1):
        for j in range(ns):
            j2 = (j + 1) % ns
            a, b = i * ns + j, i * ns + j2
            c, d = (i + 1) * ns + j2, (i + 1) * ns + j
            faces.append((d, c, b, a))
    last = (nr - 1) * ns
    for j in range(ns):
        j2 = (j + 1) % ns
        faces.append((top, last + j2, last + j))
    old = bpy.data.meshes.get(name)
    me = bpy.data.meshes.new(name + ".new")
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    if old is not None:
        me.name = name + ".tmp"
    return me, old


def _set_mesh(obj, name, radius):
    me, old = hemisphere_data(name, radius)
    obj.data = me
    me.name = name
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)


def _ensure_collection(scene):
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
    if c.name not in scene.collection.children:
        scene.collection.children.link(c)
    return c


def _link(coll, obj):
    if obj.name not in coll.objects:
        coll.objects.link(obj)


def _apply_visibility(obj, light_scene):
    flags = dict(visible_camera=True, visible_diffuse=light_scene, visible_glossy=light_scene,
                 visible_transmission=light_scene, visible_volume_scatter=light_scene,
                 visible_shadow=False)
    for k, v in flags.items():
        if hasattr(obj, k):
            setattr(obj, k, v)


def ensure_controller(scene):
    s = scene.lv_sky
    coll = _ensure_collection(scene)
    ctrl = s.controller or bpy.data.objects.get(CTRL)
    if ctrl is None:
        ctrl = bpy.data.objects.new(CTRL, None)
        ctrl.empty_display_type = 'SPHERE'
        ctrl.empty_display_size = 2.0
    _link(coll, ctrl)
    for key, val, lo, hi in (("lv_time_scale", 1.0, -50.0, 50.0), ("lv_time_offset", 0.0, -1e5, 1e5),
                             ("lv_front", 0.0, 0.0, 1.0), ("lv_haze", 0.35, 0.0, 1.0),
                             ("lv_visibility", 40.0, 1.0, 300.0), ("lv_storm", 0.0, 0.0, 1.0)):
        if key not in ctrl:
            ctrl[key] = val
            try:
                ctrl.id_properties_ui(key).update(min=lo, max=hi, soft_min=lo, soft_max=hi)
            except Exception:
                pass
    s.controller = ctrl
    return ctrl


def ensure_sun(scene):
    s = scene.lv_sky
    if s.sun and s.sun.type == 'LIGHT' and s.sun.data.type == 'SUN':
        return s.sun
    for o in scene.objects:
        if o.type == 'LIGHT' and o.data.type == 'SUN':
            s.sun = o
            return o
    light = bpy.data.lights.new(SUN, 'SUN')
    light.energy = 3.0
    o = bpy.data.objects.new(SUN, light)
    _link(_ensure_collection(scene), o)
    set_sun_angles(o, 40.0, 140.0)
    s.sun = o
    return o


def set_sun_angles(sun, elev_deg, az_deg):
    """Light points along local -Z, so direction-to-sun = R*(0,0,1)."""
    sun.rotation_mode = 'XYZ'
    sun.rotation_euler = (0.0, math.radians(90.0 - elev_deg), math.radians(az_deg))


# ------------------------------------------------------------------ drivers
def _clear_drivers(idb):
    ad = idb.animation_data
    if not ad:
        return
    for fc in list(ad.drivers):
        try:
            idb.driver_remove(fc.data_path, fc.array_index)
        except Exception:
            pass


def _driver(idb, path, expr, variables, index=-1):
    fc = idb.driver_add(path, index) if index >= 0 else idb.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    d.expression = expr
    for name, spec in variables:
        v = d.variables.new()
        v.name = name
        t = v.targets[0]
        if spec[0] == 'XFORM':
            v.type = 'TRANSFORMS'
            t.id = spec[1]
            t.transform_type = spec[2]
            t.transform_space = 'WORLD_SPACE'
            t.rotation_mode = 'XYZ'
        else:
            v.type = 'SINGLE_PROP'
            t.id_type = spec[1]
            t.id = spec[2]
            t.data_path = spec[3]
    return fc


SUN_EXPR = {
    "SunX": "cos(rx)*sin(ry)*cos(rz)+sin(rx)*sin(rz)",
    "SunY": "cos(rx)*sin(ry)*sin(rz)-sin(rx)*cos(rz)",
    "SunZ": "cos(rx)*cos(ry)",
}


def bind_globals(scene):
    s = scene.lv_sky
    tree = shaders.build_globals()
    _clear_drivers(tree)
    sun, ctrl = s.sun, s.controller
    if sun:
        for node, expr in SUN_EXPR.items():
            _driver(tree, f'nodes["{node}"].outputs[0].default_value', expr,
                    [("rx", ('XFORM', sun, 'ROT_X')), ("ry", ('XFORM', sun, 'ROT_Y')),
                     ("rz", ('XFORM', sun, 'ROT_Z'))])
    if ctrl:
        _driver(tree, 'nodes["LV_Time"].outputs[0].default_value',
                "frame/(fps/max(base,0.001))*ts+to",
                [("fps", ('PROP', 'SCENE', scene, 'render.fps')),
                 ("base", ('PROP', 'SCENE', scene, 'render.fps_base')),
                 ("ts", ('PROP', 'OBJECT', ctrl, '["lv_time_scale"]')),
                 ("to", ('PROP', 'OBJECT', ctrl, '["lv_time_offset"]'))])
        for node, expr, key in (("GHaze", "v", "lv_haze"), ("GVis", "v*1000", "lv_visibility"),
                                ("GStorm", "v", "lv_storm")):
            _driver(tree, f'nodes["{node}"].outputs[0].default_value', expr,
                    [("v", ('PROP', 'OBJECT', ctrl, f'["{key}"]'))])


def bind_transitions(scene):
    s = scene.lv_sky
    ctrl = s.controller
    for L in s.layers:
        mat = layer_material(s, L)
        if mat is None or mat.node_tree.nodes.get(L.uid) is None:
            continue
        nt = mat.node_tree
        node = nt.nodes[L.uid]
        idx = [i for i, sk in enumerate(node.inputs) if sk.name == "Presence"][0]
        path = f'nodes["{L.uid}"].inputs[{idx}].default_value'
        try:
            nt.driver_remove(path)
        except Exception:
            pass
        if L.use_transition and ctrl and L.t_end > L.t_start:
            _driver(nt, path, f"max(0,min(1,(p-{L.t_start:.4f})/{(L.t_end - L.t_start):.4f}))",
                    [("p", ('PROP', 'OBJECT', ctrl, '["lv_front"]'))])


# ------------------------------------------------------------------ layers
def new_uid():
    return "L" + uuid.uuid4().hex[:6]


def layer_material(s, L):
    o = bpy.data.objects.get(f"{SHELL}{L.uid}")
    return o.active_material if o else None


def _rng(s):
    import random
    return random.Random(s.sky_seed * 7919 + len(s.layers) * 104729) if s.sky_seed else random.Random()


def add_layer(scene, genus, overrides=None, transition=None, label=None, variation=None):
    s = scene.lv_sky
    with suspend():
        L = s.layers.add()
        L.uid = new_uid()
        L.name = label or presets.GENUS[genus]["label"].split(" (")[0]
        L.genus = genus
        L.use_voronoi = presets.genus_values(genus).get("Billow", 0.0) > 0.0
        L.tiers = presets.genus_tiers(genus)
        if transition:
            L.use_transition, L.t_start, L.t_end = True, transition[0], transition[1]
        s.layer_index = len(s.layers) - 1
    vals = presets.genus_values(genus)
    vals.update(overrides or {})
    vals = presets.jitter(vals, variation if variation is not None else s.variation, _rng(s))
    return L, vals


def capture(s):
    """uid -> values, read from the current materials."""
    out = {}
    mats = []
    if s.dome and s.dome.active_material:
        mats.append(s.dome.active_material)
    for L in s.layers:
        o = bpy.data.objects.get(f"{SHELL}{L.uid}")
        if o and o.active_material:
            mats.append(o.active_material)
    for m in mats:
        if not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeGroup' and (n.name.startswith("L") or n.name == "SKY"):
                out.setdefault(n.name, shaders.capture_values(n))
    return out


def remove_layer_data(L):
    o = bpy.data.objects.get(f"{SHELL}{L.uid}")
    if o:
        m, me = o.active_material, o.data
        bpy.data.objects.remove(o)
        if m and m.users == 0:
            bpy.data.materials.remove(m)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)
    t = bpy.data.node_groups.get(shaders.layer_tree_name(L.uid))
    if t:
        bpy.data.node_groups.remove(t)


def _sphere_mesh(name):
    import bmesh
    me = bpy.data.meshes.get(name)
    if me is None:
        bm = bmesh.new()
        try:
            bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
        except TypeError:
            bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, diameter=1.0)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
    return me


def sync_celestial(scene):
    s = scene.lv_sky
    ctrl, sun = s.controller, s.sun
    if not (s.celestial and ctrl and sun):
        for nm in (SUNB, MOONB, CEL):
            o = bpy.data.objects.get(nm)
            if o:
                bpy.data.objects.remove(o)
        return
    coll = _ensure_collection(scene)
    cel = bpy.data.objects.get(CEL)
    if cel is None:
        cel = bpy.data.objects.new(CEL, None)
        cel.empty_display_type = 'PLAIN_AXES'
        cel.empty_display_size = 5.0
    _link(coll, cel)
    cel.parent = ctrl
    cel.matrix_parent_inverse.identity()
    con = cel.constraints.get("LV_CopySun") or cel.constraints.new('COPY_ROTATION')
    con.name = "LV_CopySun"
    con.target = sun
    D = 0.97 * s.dome_radius
    for nm, sign, ang, mat in ((SUNB, 1.0, s.sun_size, shaders.build_sun_body_material()),
                               (MOONB, -1.0, s.moon_size, shaders.build_moon_material())):
        o = bpy.data.objects.get(nm)
        if o is None:
            o = bpy.data.objects.new(nm, _sphere_mesh(nm + "Mesh"))
        _link(coll, o)
        o.parent = cel
        o.matrix_parent_inverse.identity()
        o.location = (0.0, 0.0, sign * D)
        r = D * math.tan(ang)
        o.scale = (r, r, r)
        _apply_visibility(o, False)
        _assign(o, mat)


def rebuild(context, initial=None):
    """Create/refresh dome, nested cloud shells, node groups, materials, drivers."""
    scene = context.scene
    s = scene.lv_sky
    initial = initial or {}
    coll = _ensure_collection(scene)
    ctrl = ensure_controller(scene)
    ensure_sun(scene)
    saved = capture(s)

    dome = s.dome or bpy.data.objects.get(DOME)
    if dome is None:
        me, _ = hemisphere_data(DOME, s.dome_radius)
        me.name = DOME
        dome = bpy.data.objects.new(DOME, me)
    else:
        _set_mesh(dome, DOME, s.dome_radius)
    _link(coll, dome)
    dome.parent = ctrl
    dome.matrix_parent_inverse.identity()
    dome.location = (0, 0, 0)
    _apply_visibility(dome, s.light_scene)
    s.dome = dome
    _assign(dome, shaders.build_sky_only_material("LV_Sky_Dome_Mat"))

    def alt_of(uid):
        return (initial.get(uid) or saved.get(uid) or {}).get("Altitude", 1800.0)

    live = {f"{SHELL}{L.uid}" for L in s.layers}
    for o in list(bpy.data.objects):
        if o.name.startswith(SHELL) and o.name not in live:
            m, me = o.active_material, o.data
            bpy.data.objects.remove(o)
            if m and m.users == 0:
                bpy.data.materials.remove(m)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)

    order = sorted(range(len(s.layers)), key=lambda i: alt_of(s.layers[i].uid))
    n = len(order)
    for rank, i in enumerate(order):
        L = s.layers[i]
        tree = shaders.build_layer_group(L.uid, L.use_voronoi, L.tiers)
        name = f"{SHELL}{L.uid}"
        r = s.dome_radius * (0.8 if n == 1 else 0.5 + 0.42 * rank / (n - 1))
        o = bpy.data.objects.get(name)
        if o is None:
            me, _ = hemisphere_data(name, r)
            me.name = name
            o = bpy.data.objects.new(name, me)
        else:
            _set_mesh(o, name, r)
        _link(coll, o)
        o.parent = ctrl
        o.matrix_parent_inverse.identity()
        o.location = (0, 0, 0)
        o.hide_viewport = o.hide_render = not L.enabled
        _apply_visibility(o, s.light_scene)
        _assign(o, shaders.build_shell_material(f"LV_Sky_Shell_Mat_{L.uid}",
                                                dict(uid=L.uid, tree=tree, label=L.name)))

    for L in s.layers:
        mat = layer_material(s, L)
        node = mat.node_tree.nodes.get(L.uid) if mat else None
        if node is None:
            continue
        vals = dict(saved.get(L.uid, {}))
        vals.update(initial.get(L.uid, {}))
        shaders.apply_values(node, vals)
    sky = dome.active_material.node_tree.nodes.get("SKY")
    if sky:
        sv = dict(saved.get("SKY", {}))
        sv.pop("Sun Disc", None)
        shaders.apply_values(sky, sv)
        sky.inputs["Sun Disc"].default_value = 0.0 if s.celestial else 1.0

    bind_globals(scene)
    bind_transitions(scene)
    sync_follow_camera(scene)
    sync_celestial(scene)


def _assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def sync_follow_camera(scene):
    s = scene.lv_sky
    ctrl = s.controller
    if not ctrl:
        return
    con = ctrl.constraints.get("LV_FollowCamera")
    if s.follow_camera and scene.camera:
        if con is None:
            con = ctrl.constraints.new('COPY_LOCATION')
            con.name = "LV_FollowCamera"
        con.target = scene.camera
    elif con is not None:
        ctrl.constraints.remove(con)


def apply_weather(context, key):
    s = context.scene.lv_sky
    for L in list(s.layers):
        remove_layer_data(L)
    with suspend():
        s.layers.clear()
    initial = {}
    W = presets.WEATHER[key]
    for genus, ov, trans in W["layers"]:
        L, vals = add_layer(context.scene, genus, ov, trans)
        initial[L.uid] = vals
    with suspend():
        s.layer_index = 0
    ctrl = ensure_controller(context.scene)
    ctrl["lv_storm"] = W.get("storm", 0.0)
    ctrl["lv_haze"] = W.get("haze", 0.35)
    ctrl["lv_visibility"] = W.get("vis", 40.0)
    rebuild(context, initial)


def reroll(context, amount=None):
    """Re-roll seeds and jitter every layer's look (no more repeated clouds)."""
    import random
    s = context.scene.lv_sky
    rng = random.Random()
    amt = s.variation if amount is None else amount
    for L in s.layers:
        node = layer_node(s, L)
        if node is None:
            continue
        vals = shaders.capture_values(node)
        vals["Seed"] = rng.uniform(0.0, 900.0)
        base = {k: vals[k] for k in vals}
        shaders.apply_values(node, presets.jitter(base, max(amt, 0.6), rng))


def layer_node(s, L):
    mat = layer_material(s, L)
    if mat and mat.node_tree:
        return mat.node_tree.nodes.get(L.uid)
    return None


def delete_rig(context):
    s = context.scene.lv_sky
    for o in list(bpy.data.objects):
        if o.name.startswith("LV_Sky_"):
            bpy.data.objects.remove(o)
    for m in list(bpy.data.materials):
        if m.name.startswith("LV_Sky_"):
            bpy.data.materials.remove(m)
    for t in list(bpy.data.node_groups):
        if t.name.startswith("LV_"):
            bpy.data.node_groups.remove(t)
    for me in list(bpy.data.meshes):
        if me.name.startswith("LV_Sky_") and me.users == 0:
            bpy.data.meshes.remove(me)
    c = bpy.data.collections.get(COLL)
    if c and not c.objects:
        bpy.data.collections.remove(c)
    s.layers.clear()
    s.controller = None
    s.dome = None


def fit_camera_clip(context):
    s = context.scene.lv_sky
    need = s.dome_radius * 1.25
    cam = context.scene.camera
    if cam and cam.type == 'CAMERA' and cam.data.clip_end < need:
        cam.data.clip_end = need
    sp = getattr(context, "space_data", None)
    if sp and sp.type == 'VIEW_3D' and sp.clip_end < need:
        sp.clip_end = need
