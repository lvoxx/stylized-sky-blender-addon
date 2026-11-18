# SPDX-License-Identifier: GPL-3.0-or-later
"""Shader-node generators for the stylized cloud dome.

Design (see README):
  * The dome mesh is only a *screen* carrying the view ray direction `d`.
    Every cloud layer is a virtual slab [Altitude, Altitude+Thickness] above a
    (optionally curved) planet. The ray/slab intersection is computed
    analytically, then the slab is marched with a small, *unrolled* number of
    steps (nv view steps, nl light steps toward the Sun).
  * Lighting = Beer-Lambert transmittance toward the Sun (+ powder term,
    HG forward-scatter "silver lining", ambient gradient), then remapped by a
    toon band ramp. Everything is plain shader nodes -> works in EEVEE & Cycles.
"""
import bpy
from .nb import NB, srgb

GLOBALS = "LV_Sky_Globals"
SKYBASE = "LV_Sky_Base"
LAYER_PREFIX = "LV_Layer_"

F = "NodeSocketFloat"
FAC = "NodeSocketFloatFactor"
DIST = "NodeSocketFloatDistance"
ANG = "NodeSocketFloatAngle"
COL = "NodeSocketColor"
VEC = "NodeSocketVector"

# panel, name, socket type, default, min, max
LAYER_PREFIX_DOC = None
CLOUD_INPUTS = [
    ("Shape", "Coverage", FAC, 0.45, 0.0, 1.0),
    ("Shape", "Softness", F, 0.08, 0.005, 0.8),
    ("Shape", "Scale", DIST, 1800.0, 50.0, 200000.0),
    ("Shape", "Detail", F, 4.0, 0.0, 8.0),
    ("Shape", "Roughness", FAC, 0.55, 0.0, 1.0),
    ("Shape", "Billow", FAC, 0.0, 0.0, 1.0),
    ("Shape", "Warp", F, 0.4, 0.0, 3.0),
    ("Shape", "Puff Detail", FAC, 0.4, 0.0, 1.0),
    ("Shape", "Puff Scale", F, 3.5, 1.0, 30.0),
    ("Shape", "Stretch", F, 1.0, 1.0, 30.0),
    ("Shape", "Seed", F, 0.0, 0.0, 1000.0),
    ("Shape", "Altitude", DIST, 1800.0, 100.0, 30000.0),
    ("Structure", "Height", DIST, 900.0, 0.0, 20000.0),
    ("Structure", "Taper", FAC, 0.6, 0.0, 1.0),
    ("Structure", "Anvil", FAC, 0.0, 0.0, 1.0),
    ("Structure", "Base Dark", FAC, 0.25, 0.0, 1.0),
    ("Structure", "Top Light", FAC, 0.4, 0.0, 1.0),
    ("Structure", "Cluster", FAC, 0.5, 0.0, 1.0),
    ("Structure", "Cluster Scale", DIST, 14000.0, 1000.0, 300000.0),
    ("Structure", "Variety", FAC, 0.6, 0.0, 1.0),
    ("Wind", "Wind Angle", ANG, 0.0, -6.2832, 6.2832),
    ("Wind", "Wind Speed", F, 5.0, 0.0, 300.0),
    ("Relief", "Relief", F, 1.0, 0.0, 8.0),
    ("Relief", "Relief Width", F, 0.5, 0.05, 1.0),
    ("Relief", "Shadow Offset", FAC, 0.75, 0.0, 1.0),
    ("Relief", "Core Shade", FAC, 0.2, 0.0, 1.0),
    ("Light", "Ambient", FAC, 0.34, 0.0, 1.0),
    ("Light", "Wrap", FAC, 0.6, 0.0, 1.0),
    ("Light", "Silver Lining", F, 0.8, 0.0, 3.0),
    ("Light", "Phase G", FAC, 0.7, 0.0, 0.95),
    ("Light", "Sun Tint", FAC, 0.75, 0.0, 1.0),
    ("Toon", "Lit Color", COL, (1.0, 1.0, 1.0, 1.0), None, None),
    ("Toon", "Shadow Tint", COL, (1.0, 1.0, 1.0, 1.0), None, None),
    ("Toon", "Mid Blend", FAC, 0.5, 0.0, 1.0),
    ("Toon", "Band 1", FAC, 0.28, 0.0, 1.0),
    ("Toon", "Band 2", FAC, 0.50, 0.0, 1.0),
    ("Toon", "Band Blend", F, 0.07, 0.0005, 0.5),
    ("Toon", "Toon Mix", FAC, 1.0, 0.0, 1.0),
    ("Toon", "Exposure", F, 1.0, 0.0, 4.0),
    ("Heavy", "Heaviness", FAC, 0.0, 0.0, 1.0),
    ("Heavy", "Storm Response", FAC, 0.6, 0.0, 1.0),
    ("Heavy", "Storm Lit", COL, (0.13, 0.15, 0.19, 1.0), None, None),
    ("Heavy", "Storm Shade", COL, (0.016, 0.022, 0.04, 1.0), None, None),
    ("Edge", "Alpha Hardness", FAC, 0.9, 0.0, 1.0),
    ("Edge", "Edge Ragged", FAC, 0.5, 0.0, 1.0),
    ("Edge", "Edge Cell", F, 0.12, 0.01, 1.0),
    ("Atmosphere", "Opacity", FAC, 1.0, 0.0, 1.0),
    ("Atmosphere", "Presence", FAC, 1.0, 0.0, 1.0),
    ("Atmosphere", "Horizon Fade", F, 0.25, 0.001, 1.0),
    ("Atmosphere", "Haze", F, 1.0, 0.0, 3.0),
    ("Atmosphere", "Halo", FAC, 0.0, 0.0, 1.0),
]
CLOUD_PANELS = ["Shape", "Structure", "Wind", "Relief", "Light", "Toon", "Heavy", "Edge", "Atmosphere"]
LAYER_DEFAULTS = {n: d for (_p, n, _t, d, _a, _b) in CLOUD_INPUTS}

SKY_INPUTS = [
    ("Sun Size", F, 0.035, 0.002, 0.3),
    ("Sun Glow", F, 0.6, 0.0, 4.0),
    ("Glow Falloff", F, 24.0, 1.0, 200.0),
    ("Gradient Height", F, 0.55, 0.05, 1.0),
    ("Sun Disc", F, 1.0, 0.0, 1.0),
    ("Star Density", F, 1.6, 0.0, 3.0),
    ("Star Brightness", F, 1.0, 0.0, 6.0),
    ("Galaxy", F, 1.0, 0.0, 4.0),
    ("Moon Glow", F, 1.0, 0.0, 4.0),
    ("Haze Height", F, 0.22, 0.02, 1.0),
    ("Haze Strength", F, 1.0, 0.0, 2.0),
]

# ---------------------------------------------------------------- utilities
def _ensure_tree(name):
    t = bpy.data.node_groups.get(name)
    if t is None or t.bl_idname != 'ShaderNodeTree':
        t = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    return t


def _socket_names(tree, in_out):
    return {i.name for i in tree.interface.items_tree
            if i.item_type == 'SOCKET' and i.in_out == in_out}


def _new_socket(tree, name, in_out, stype, default=None, mn=None, mx=None):
    try:
        s = tree.interface.new_socket(name=name, in_out=in_out, socket_type=stype)
    except (TypeError, RuntimeError):
        base = COL if stype == COL else (VEC if stype == VEC else F)
        s = tree.interface.new_socket(name=name, in_out=in_out, socket_type=base)
    if default is not None:
        try:
            s.default_value = default
        except (TypeError, ValueError):
            pass
    for attr, v in (("min_value", mn), ("max_value", mx)):
        if v is not None and hasattr(s, attr) and stype not in (FAC,):
            try:
                setattr(s, attr, v)
            except (TypeError, ValueError):
                pass
    return s


def _clear(tree):
    tree.nodes.clear()


def _io(tree):
    gin = tree.nodes.new('NodeGroupInput')
    gout = tree.nodes.new('NodeGroupOutput')
    gin.location = (-1400, 0)
    gout.location = (2600, 0)
    return gin, gout


def _group_node(tree, subtree, loc=(-1000, 400)):
    g = tree.nodes.new('ShaderNodeGroup')
    g.node_tree = subtree
    g.location = loc
    return g


# ---------------------------------------------------------------- globals
def build_globals():
    """Build once; later calls reuse it (keeps drivers and user-edited ramps)."""
    tree = _ensure_tree(GLOBALS)
    if tree.nodes.get("LV_Time") and tree.nodes.get("RampSun") and tree.nodes.get("GStorm"):
        return tree
    existing = _socket_names(tree, 'OUTPUT')
    outs = [("Sun Dir", VEC), ("Sun Elev", F), ("Time", F), ("Sun Color", COL),
            ("Zenith Color", COL), ("Horizon Color", COL), ("Ambient Color", COL),
            ("Planet Radius", F), ("Pixel Angle", F), ("Haze", F), ("Visibility", F), ("Storm", F)]
    for n, t in outs:
        if n not in existing:
            _new_socket(tree, n, 'OUTPUT', t)
    _clear(tree)
    nb = NB(tree, x0=-900, y0=400)
    _gin, gout = _io(tree)
    sx = nb.val(0.4, label="Sun X (driven)", name="SunX")
    sy = nb.val(-0.5, label="Sun Y (driven)", name="SunY")
    sz = nb.val(0.77, label="Sun Z (driven)", name="SunZ")
    time = nb.val(0.0, label="Time s (driven)", name="LV_Time")
    planet = nb.val(6371.0, label="Planet radius km", name="PlanetKm")
    pix = nb.val(0.0008, label="Pixel angle rad", name="PixelAngle")
    ghaze = nb.val(0.35, label="Atmospheric haze (driven)", name="GHaze")
    gvis = nb.val(40000.0, label="Visibility m (driven)", name="GVis")
    gstorm = nb.val(0.0, label="Precipitation / storm (driven)", name="GStorm")
    sdir = nb.normalize(nb.xyz(sx, sy, sz))
    elev = nb.sep(sdir)[2]
    fac = nb.remap(elev, -0.3, 0.7, 0.0, 1.0)

    def stops(rows):
        return [(e + 0.3, srgb(c)) for e, c in rows]

    sun = nb.ramp(fac, stops([(-0.3, "#a8c4ff"), (-0.12, "#a89ad8"), (-0.03, "#ff7a45"),
                              (0.05, "#ffa863"), (0.18, "#ffd9a8"), (0.5, "#fff1dc"),
                              (0.7, "#fff6e8")]))
    sun.label, sun.name = "Sun color by elevation", "RampSun"
    zen = nb.ramp(fac, stops([(-0.3, "#0a1347"), (-0.12, "#1b2a78"), (-0.03, "#3a3a82"),
                              (0.05, "#4f6fb8"), (0.18, "#3f86d6"), (0.5, "#2f7fe0"),
                              (0.7, "#2a78dc")]))
    zen.label, zen.name = "Zenith by elevation", "RampZenith"
    hor = nb.ramp(fac, stops([(-0.3, "#1f62ad"), (-0.12, "#4b4fa0"), (-0.03, "#d86a5a"),
                              (0.05, "#ffb27a"), (0.18, "#cfe3f5"), (0.5, "#bfe0ff"),
                              (0.7, "#b5dcff")]))
    hor.label, hor.name = "Horizon by elevation", "RampHorizon"
    amb = nb.ramp(fac, stops([(-0.3, "#2d4aa0"), (-0.12, "#4a4f9a"), (-0.03, "#6b5a9a"),
                              (0.05, "#8f86c0"), (0.18, "#8ba5dc"), (0.5, "#86a8e0"),
                              (0.7, "#8cb0e4")]))
    amb.label, amb.name = "Cloud shadow tint by elevation", "RampAmbient"
    L = tree.links.new
    L(sdir, gout.inputs["Sun Dir"])
    L(elev, gout.inputs["Sun Elev"])
    L(time, gout.inputs["Time"])
    L(sun.outputs[0], gout.inputs["Sun Color"])
    L(zen.outputs[0], gout.inputs["Zenith Color"])
    L(hor.outputs[0], gout.inputs["Horizon Color"])
    L(amb.outputs[0], gout.inputs["Ambient Color"])
    L(nb.mul(planet, 1000.0), gout.inputs["Planet Radius"])
    L(pix, gout.inputs["Pixel Angle"])
    L(ghaze, gout.inputs["Haze"])
    L(gvis, gout.inputs["Visibility"])
    L(gstorm, gout.inputs["Storm"])
    return tree


# ---------------------------------------------------------------- sky base
def build_skybase():
    tree = _ensure_tree(SKYBASE)
    if "View Dir" not in _socket_names(tree, 'INPUT'):
        _new_socket(tree, "View Dir", 'INPUT', VEC, (0.0, 0.0, 1.0))
    have = _socket_names(tree, 'INPUT')
    for n, t, d, a, b in SKY_INPUTS:
        if n not in have:
            _new_socket(tree, n, 'INPUT', t, d, a, b)
    if "Color" not in _socket_names(tree, 'OUTPUT'):
        _new_socket(tree, "Color", 'OUTPUT', COL)
    _clear(tree)
    nb = NB(tree, x0=-900, y0=400)
    gin, gout = _io(tree)
    G = _group_node(tree, build_globals())
    d = gin.outputs["View Dir"]
    dz = nb.sep(d)[2]
    g = nb.smooth(dz, 0.0, gin.outputs["Gradient Height"])
    sky = nb.cmix(g, G.outputs["Horizon Color"], G.outputs["Zenith Color"])
    dayf = nb.smooth(G.outputs["Sun Elev"], -0.1, 0.25)
    storm = G.outputs["Storm"]
    stormcol = nb.cmix(g, nb.vscale((0.10, 0.115, 0.14), nb.madd(dayf, 0.85, 0.15)),
                       nb.vscale((0.03, 0.04, 0.06), nb.madd(dayf, 0.85, 0.15)))
    sky = nb.cmix(nb.mul(storm, 0.8), sky, stormcol)
    # atmospheric haze band toward the horizon (visibility)
    hz_col = nb.cmix(nb.mul(dayf, 0.3), G.outputs["Horizon Color"], (1.0, 1.0, 1.0, 1.0))
    hz_col = nb.cmix(nb.mul(storm, 0.7), hz_col, nb.vscale((0.09, 0.10, 0.125), nb.madd(dayf, 0.8, 0.2)))
    hband = nb.pw(nb.sub(1.0, nb.sat(nb.div(dz, gin.outputs["Haze Height"]))), 1.7)
    hamt = nb.sat(nb.mul(nb.mul(hband, gin.outputs["Haze Strength"]),
                         nb.madd(G.outputs["Haze"], 0.9, 0.35)))
    sky = nb.cmix(hamt, sky, hz_col)
    cosa = nb.dot(d, G.outputs["Sun Dir"])
    theta = nb.math('ARCCOSINE', nb.math('MAXIMUM', nb.math('MINIMUM', cosa, 1.0), -1.0))
    r0 = gin.outputs["Sun Size"]
    disc = nb.smooth(theta, nb.mul(r0, 1.12), r0)
    c = nb.sat(cosa)
    fall = gin.outputs["Glow Falloff"]
    glow = nb.mul(gin.outputs["Sun Glow"],
                  nb.add(nb.pw(c, fall), nb.mul(nb.pw(c, nb.div(fall, 6.0)), 0.25)))
    sun_amt = nb.add(nb.mul(nb.mul(disc, gin.outputs["Sun Disc"]), 6.0), glow)
    out = nb.vmath('ADD', sky, nb.vscale(G.outputs["Sun Color"], sun_amt))

    # night: soft Milky Way band, dense stars concentrated in it, moon glow
    night = nb.smooth(G.outputs["Sun Elev"], 0.02, -0.18)
    hor_m = nb.smooth(dz, 0.0, 0.12)
    axn = (0.35, 0.6, 0.55)
    ln = (axn[0] ** 2 + axn[1] ** 2 + axn[2] ** 2) ** 0.5
    ax = (axn[0] / ln, axn[1] / ln, axn[2] / ln)
    a = nb.dot(d, ax)
    a_n = nb.div(a, 0.30)
    band = nb.exp(nb.mul(nb.mul(a_n, a_n), -1.0))
    wide = nb.exp(nb.mul(nb.mul(nb.div(a, 0.75), nb.div(a, 0.75)), -1.0))
    n1 = nb.node('ShaderNodeTexNoise', noise_dimensions='3D', noise_type='FBM', normalize=True)
    nb.set(n1.inputs['Vector'], nb.vmath('ADD', nb.vscale(d, 1.5), (3.0, 1.0, 2.0)))
    nb.set(n1.inputs['Detail'], 6.0)
    nb.set(n1.inputs['Roughness'], 0.62)
    n2 = nb.node('ShaderNodeTexNoise', noise_dimensions='3D', noise_type='FBM', normalize=True)
    nb.set(n2.inputs['Vector'], nb.vmath('ADD', nb.vscale(d, 3.2), (9.0, 4.0, 1.0)))
    nb.set(n2.inputs['Detail'], 5.0)
    cloud = nb.smooth(n1.outputs[0], 0.25, 0.85)
    clear = nb.smooth(n2.outputs[0], 0.30, 0.70)
    lanes = nb.mix(clear, 0.55, 1.0)
    core = nb.mul(band, nb.mix(0.35, 1.0, cloud))
    colA = (0.03, 0.07, 0.34, 1.0)
    colB = (0.22, 0.12, 0.50, 1.0)
    colC = (0.12, 0.30, 0.85, 1.0)
    gcol = nb.cmix(nb.mul(nb.smooth(n2.outputs[0], 0.3, 0.9), 0.55), colA, colB)
    gcol = nb.cmix(nb.smooth(core, 0.4, 1.0), gcol, colC)
    glow = nb.vscale(colA[:3], nb.mul(nb.mul(wide, 0.5), gin.outputs["Galaxy"]))
    gal = nb.vscale(gcol, nb.mul(nb.mul(core, lanes), nb.mul(gin.outputs["Galaxy"], 1.5)))
    vor = nb.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
    nb.set(vor.inputs['Vector'], nb.vscale(d, 320.0))
    cr, cg, _cb = nb.sep(vor.outputs[1])
    dens = nb.mul(gin.outputs["Star Density"], nb.madd(nb.mul(band, cloud), 0.9, 0.10))
    keep = nb.math('GREATER_THAN', cg, nb.sub(1.0, dens))
    star1 = nb.mul(nb.mul(nb.smooth(vor.outputs[0], 0.11, 0.0), keep), nb.madd(nb.mul(cr, cr), 1.2, 0.35))
    vor2 = nb.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
    nb.set(vor2.inputs['Vector'], nb.vscale(d, 75.0))
    cr2, cg2, _cb2 = nb.sep(vor2.outputs[1])
    keep2 = nb.math('GREATER_THAN', cg2, nb.sub(1.0, nb.mul(gin.outputs["Star Density"], 0.06)))
    star2 = nb.mul(nb.mul(nb.smooth(vor2.outputs[0], 0.16, 0.0), keep2), nb.madd(cr2, 2.0, 1.5))
    stars = nb.vscale((0.85, 0.92, 1.0), nb.mul(nb.add(star1, star2), gin.outputs["Star Brightness"]))
    cosm = nb.dot(d, nb.vscale(G.outputs["Sun Dir"], -1.0))
    cm = nb.sat(cosm)
    mglow = nb.mul(nb.add(nb.mul(nb.pw(cm, 70.0), 0.55), nb.mul(nb.pw(cm, 9.0), 0.09)), gin.outputs["Moon Glow"])
    moon_add = nb.vscale((0.55, 0.72, 1.0), mglow)
    night_add = nb.vscale(nb.vmath('ADD', nb.vmath('ADD', stars, gal), nb.vmath('ADD', glow, moon_add)),
                          nb.mul(night, hor_m))
    out = nb.vmath('ADD', out, night_add)
    tree.links.new(out, gout.inputs["Color"])
    return tree


# ---------------------------------------------------------------- 2D cloud layer
def layer_tree_name(uid):
    return LAYER_PREFIX + uid


def ensure_layer_interface(tree):
    if "View Dir" not in _socket_names(tree, 'INPUT'):
        _new_socket(tree, "View Dir", 'INPUT', VEC, (0.0, 0.0, 1.0))
    have = _socket_names(tree, 'INPUT')
    for _p, n, t, d, a, b in CLOUD_INPUTS:
        if n not in have:
            _new_socket(tree, n, 'INPUT', t, d, a, b)
    outs = _socket_names(tree, 'OUTPUT')
    if "Color" not in outs:
        _new_socket(tree, "Color", 'OUTPUT', COL)
    if "Alpha" not in outs:
        _new_socket(tree, "Alpha", 'OUTPUT', F)


def _noise(nb, vec, scale, detail, rough=0.55):
    n = nb.node('ShaderNodeTexNoise', noise_dimensions='3D', noise_type='FBM', normalize=True)
    nb.set(n.inputs['Vector'], vec)
    nb.set(n.inputs['Scale'], scale)
    nb.set(n.inputs['Detail'], detail)
    nb.set(n.inputs['Roughness'], rough)
    return n.outputs[0], n.outputs[1]



def build_layer_group(uid, use_vor=True, tiers=3):
    """2D cloud on a hemisphere shell.

    Gravity / tiers: the layer is sampled on `tiers` horizontal planes between Altitude and
    Altitude+Height. Higher planes need denser noise (Taper) so footprints shrink with height ->
    wide heavy base, narrower top; perspective parallax stacks them upward on screen (a tower).
    The top plane can re-widen (Anvil). Shading: dark flat base, lit crown, Sun-direction slope.
    """
    tree = _ensure_tree(layer_tree_name(uid))
    ensure_layer_interface(tree)
    _clear(tree)
    nb = NB(tree, x0=-1200, y0=900, rows=20, dx=240, dy=180)
    gin, gout = _io(tree)
    I = lambda n: gin.outputs[n]
    G = _group_node(tree, build_globals())
    Go = lambda n: G.outputs[n]
    K = max(1, int(tiers))

    d = I("View Dir")
    dx, dy, dz = nb.sep(d)
    mu = nb.mx(dz, 0.02)
    R = Go("Planet Radius")
    Rmu = nb.mul(R, mu)
    Rmu2 = nb.mul(Rmu, Rmu)
    twoR = nb.mul(R, 2.0)

    def tpath(h):
        k = nb.add(nb.mul(twoR, h), nb.mul(h, h))
        return nb.div(k, nb.add(nb.sqrt(nb.add(Rmu2, k)), Rmu))

    h0 = I("Altitude")
    t0 = tpath(h0)
    foot = nb.div(nb.mul(t0, Go("Pixel Angle")), mu)
    lodv = nb.math('LOGARITHM', nb.div(I("Scale"), nb.mul(foot, 2.0)), 2.0)
    dlod = nb.mn(I("Detail"), nb.mx(lodv, 0.0))
    bill = nb.mul(I("Billow"), nb.smooth(lodv, 0.5, 2.5))

    wa = I("Wind Angle")
    travel = nb.mul(I("Wind Speed"), Go("Time"))
    sd = I("Seed")
    loc = nb.xyz(nb.add(nb.mul(nb.math('COSINE', wa), travel), nb.mul(sd, 1731.0)),
                 nb.add(nb.mul(nb.math('SINE', wa), travel), nb.mul(sd, 937.0)),
                 nb.mul(sd, 211.0))
    rot = nb.xyz(0.0, 0.0, wa)
    scl = nb.xyz(nb.mul(I("Scale"), I("Stretch")), I("Scale"), I("Scale"))
    eps = nb.mul(I("Scale"), 0.09)

    # light: sun by day, moon (opposite) by night
    L = Go("Sun Dir")
    elev = Go("Sun Elev")
    kk = nb.smooth(elev, -0.03, 0.03)
    Lm = nb.normalize(nb.mix(kk, nb.vscale(L, -1.0), L, kind='VECTOR'))
    sun_i = nb.smooth(elev, -0.04, 0.12)
    moon_i = nb.mul(nb.smooth(elev, 0.0, -0.2), 0.6)
    inten = nb.mx(sun_i, moon_i)
    Lx, Ly, Lz = nb.sep(Lm)
    Lh = nb.normalize(nb.xyz(Lx, Ly, nb.mx(Lz, 0.3)))
    Lhx, Lhy, _lz = nb.sep(Lh)

    # --- distribution: low-frequency coverage mask (clusters + gaps) and size/height variety
    Px0, Py0 = nb.mul(dx, t0), nb.mul(dy, t0)
    cpos = nb.vmath('ADD', nb.vscale(nb.xyz(Px0, Py0, 0.0), nb.div(1.0, I("Cluster Scale"))),
                    nb.xyz(nb.mul(sd, 0.37), nb.mul(sd, 0.53), 3.1))
    cn, _cc = _noise(nb, cpos, 1.0, 3.0, 0.5)
    vn_, _vc = _noise(nb, nb.vmath('ADD', nb.vscale(cpos, 2.3), (5.0, 7.0, 1.0)), 1.0, 2.0, 0.5)
    cmask = nb.remap(cn, 0.3, 0.7, 0.0, 1.0)
    vmask = nb.remap(vn_, 0.3, 0.7, 0.0, 1.0)
    shift = nb.mul(nb.mul(nb.sub(cmask, 0.5), I("Cluster")), 0.7)
    comp = 0.03 * (K - 1)   # several tiers see through more columns: compensate coverage
    thr = nb.add(nb.sub(nb.sub(0.78, nb.mul(nb.mul(I("Coverage"), I("Presence")), 0.56)), shift), comp)
    hvar = nb.mix(I("Variety"), 1.0, nb.madd(vmask, 1.1, 0.45))
    Hgt = nb.mul(I("Height"), hvar)
    tap = nb.mul(I("Taper"), nb.mix(I("Variety"), 1.0, nb.madd(vmask, 0.8, 0.6)))
    rw = I("Relief Width")

    def soft(x, th, w):
        return nb.sat(nb.div(nb.sub(x, th), w))

    def noise_at(c):
        n = nb.node('ShaderNodeTexNoise', noise_dimensions='3D', noise_type='FBM', normalize=True)
        nb.set(n.inputs['Vector'], c)
        nb.set(n.inputs['Scale'], 1.0)
        nb.set(n.inputs['Detail'], dlod)
        nb.set(n.inputs['Roughness'], I("Roughness"))
        nb.set(n.inputs['Distortion'], nb.mul(I("Warp"), 0.7))
        wv = nb.vscale(nb.vmath('SUBTRACT', n.outputs[1], (0.5, 0.5, 0.5)), I("Warp"))
        return n.outputs[0], wv

    pd = nb.mul(I("Puff Detail"), nb.smooth(lodv, 1.5, 3.5))

    # --- tiers
    A = None            # union alpha (hard masks)
    wsum = None         # visible-height accumulation
    F0 = F1 = F2 = FS = None
    bump = None
    c_first = None
    for k in range(K):
        tk = (k / (K - 1)) if K > 1 else 0.0
        hk = nb.madd(Hgt, tk, h0) if K > 1 else h0
        tkd = tpath(hk) if K > 1 else t0
        Px, Py = nb.mul(dx, tkd), nb.mul(dy, tkd)
        th = nb.add(thr, nb.mul(tap, 0.38 * (tk ** 0.8)))
        if K > 1 and k == K - 1:
            th = nb.sub(th, nb.mul(I("Anvil"), 0.4))

        def cc(px, py):
            return nb.mapping(nb.xyz(px, py, hk), loc, rot, scl)

        c0 = cc(Px, Py)
        xn0, w0 = noise_at(c0)
        xv0 = xn0
        pk = 0.0
        if use_vor:
            vo = nb.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
            nb.set(vo.inputs['Vector'], nb.vmath('ADD', c0, w0))
            nb.set(vo.inputs['Scale'], 1.3)
            xv0 = nb.mix(bill, xn0, nb.sub(1.0, nb.mn(vo.outputs[0], 1.0)))
            pv = nb.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
            nb.set(pv.inputs['Vector'], nb.vscale(nb.vmath('ADD', c0, nb.vscale(w0, 1.2)), I("Puff Scale")))
            edge = nb.sub(1.0, nb.smooth(nb.sub(xn0, th), 0.0, 0.12))
            pk = nb.mul(nb.mul(nb.sub(0.55, nb.mn(pv.outputs[0], 1.0)), pd), edge)
        mk = nb.sat(nb.div(nb.sub(nb.add(xv0, nb.mul(pk, 0.55)), th), I("Softness")))
        xn1, _ = noise_at(cc(nb.add(Px, eps), Py))
        xn2, _ = noise_at(cc(Px, nb.add(Py, eps)))
        xns, _ = noise_at(cc(nb.add(Px, nb.mul(nb.mul(Lhx, eps), 3.0)), nb.add(Py, nb.mul(nb.mul(Lhy, eps), 3.0))))
        s0, s1, s2, ss = soft(xn0, th, rw), soft(xn1, th, rw), soft(xn2, th, rw), soft(xns, th, rw)
        F0 = s0 if F0 is None else nb.add(F0, s0)
        F1 = s1 if F1 is None else nb.add(F1, s1)
        F2 = s2 if F2 is None else nb.add(F2, s2)
        FS = ss if FS is None else nb.add(FS, ss)
        bmp = nb.sub(xv0, xn0)
        bump = bmp if bump is None else nb.add(bump, bmp)
        # front-to-back (bottom plane first): visible-height bookkeeping
        if A is None:
            A = mk
            wsum = nb.mul(mk, tk)
        else:
            w = nb.mul(nb.sub(1.0, A), mk)
            wsum = nb.add(wsum, nb.mul(w, tk))
            A = nb.add(A, w)
        if c_first is None:
            c_first = c0
    invK = 1.0 / K
    F0, F1, F2, FS = (nb.mul(f, invK) for f in (F0, F1, F2, FS))
    hv = nb.div(wsum, nb.mx(A, 1e-3))          # 0 = looking at the base, 1 = crown

    kr = nb.mul(I("Relief"), 12.0)
    gdir = nb.add(nb.mul(nb.sub(F1, F0), Lhx), nb.mul(nb.sub(F2, F0), Lhy))
    lam = nb.sat(nb.add(nb.sub(0.55, nb.mul(gdir, kr)), nb.mul(nb.mul(bump, invK), nb.mul(I("Relief"), 2.0))))
    shad = nb.sat(nb.mul(nb.sub(FS, F0), 8.0))
    lam = nb.mul(lam, nb.sub(1.0, nb.mul(I("Shadow Offset"), shad)))

    # --- heaviness (rain / storm clouds go dark slate instead of staying neutral blue)
    heavy = nb.sat(nb.add(I("Heaviness"), nb.mul(Go("Storm"), I("Storm Response"))))
    amb = nb.mul(I("Ambient"), nb.sub(1.0, nb.mul(heavy, 0.45)))
    base_dark = nb.mul(I("Base Dark"), nb.madd(heavy, 0.8, 1.0))
    core = nb.mul(nb.mul(F0, F0), nb.mul(I("Core Shade"), nb.madd(heavy, 1.2, 1.0)))
    s = nb.add(amb, nb.mul(nb.sub(1.0, amb), nb.mul(lam, inten)))
    s = nb.add(s, nb.mul(hv, nb.mul(I("Top Light"), nb.sub(1.0, nb.mul(heavy, 0.5)))))
    s = nb.mul(s, nb.sub(nb.sub(1.0, core), nb.mul(base_dark, nb.sub(1.0, hv))))

    cosa = nb.dot(d, Lm)
    g = I("Phase G")
    den = nb.sub(nb.add(1.0, nb.mul(g, g)), nb.mul(nb.mul(g, 2.0), cosa))
    omg = nb.sub(1.0, g)
    hg = nb.pw(nb.div(nb.mul(omg, omg), nb.mx(den, 1e-4)), 1.5)

    white = (1.0, 1.0, 1.0, 1.0)
    sun_c = Go("Sun Color")
    tint = nb.mul(I("Sun Tint"), nb.sub(1.0, nb.mul(heavy, 0.6)))
    lit_n = nb.vmath('MULTIPLY', I("Lit Color"), nb.cmix(tint, white, sun_c))
    shade_n = nb.vmath('MULTIPLY', Go("Ambient Color"), I("Shadow Tint"))
    dayk = nb.madd(inten, 0.7, 0.3)
    lit = nb.cmix(heavy, lit_n, nb.vscale(I("Storm Lit"), dayk))
    shade = nb.cmix(heavy, shade_n, nb.vscale(I("Storm Shade"), dayk))
    mid = nb.cmix(I("Mid Blend"), shade, lit)
    bw = I("Band Blend")
    b1 = nb.smooth(s, nb.sub(I("Band 1"), bw), nb.add(I("Band 1"), bw))
    b2 = nb.smooth(s, nb.sub(I("Band 2"), bw), nb.add(I("Band 2"), bw))
    toon = nb.cmix(b2, nb.cmix(b1, shade, mid), lit)
    smooth_c = nb.cmix(nb.sat(s), shade, lit)
    col = nb.cmix(I("Toon Mix"), smooth_c, toon)

    thin = nb.pw(nb.sub(1.0, F0), 2.0)
    rim = nb.mul(nb.mul(nb.mul(I("Silver Lining"), hg), thin), nb.mul(inten, nb.sub(1.0, heavy)))
    col = nb.vmath('ADD', col, nb.vscale(sun_c, nb.mul(rim, 0.5)))
    cos_s = nb.dot(d, L)
    theta = nb.math('ARCCOSINE', nb.math('MAXIMUM', nb.math('MINIMUM', cos_s, 1.0), -1.0))
    rx = nb.div(nb.sub(theta, 0.384), 0.045)
    ring = nb.exp(nb.mul(nb.mul(rx, rx), -1.0))
    halo = nb.mul(nb.mul(nb.mul(I("Halo"), ring), F0), sun_i)
    col = nb.vmath('ADD', col, nb.vscale(sun_c, nb.mul(halo, 0.8)))

    # --- visibility: distance haze (global Visibility) + low-elevation haze band
    vis = nb.mx(nb.mul(Go("Visibility"), nb.sub(1.0, nb.mul(Go("Storm"), 0.6))), 500.0)
    tmid = nb.mul(t0, 1.0)
    fog = nb.mul(nb.sub(1.0, nb.exp(nb.mul(nb.div(tmid, nb.mul(vis, 3.0)), -3.9))), 0.85)
    band = nb.pw(nb.sub(1.0, nb.sat(nb.mul(dz, 3.5))), 2.0)
    hz = nb.mn(nb.add(nb.mul(I("Haze"), fog), nb.mul(nb.mul(Go("Haze"), 0.7), band)), 0.7)
    dayf = nb.smooth(elev, -0.1, 0.25)
    hz_col = nb.cmix(nb.mul(dayf, 0.3), Go("Horizon Color"), white)
    hz_col = nb.cmix(nb.mul(Go("Storm"), 0.7), hz_col, nb.vscale((0.09, 0.10, 0.125), nb.madd(dayf, 0.8, 0.2)))
    col = nb.cmix(hz, col, hz_col)
    col = nb.vscale(col, I("Exposure"))

    # --- alpha: union of tier masks + Voronoi ragged edge
    ev = nb.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
    nb.set(ev.inputs['Vector'], c_first)
    nb.set(ev.inputs['Scale'], nb.div(1.0, I("Edge Cell")))
    cellr = nb.sep(ev.outputs[1])[0]
    rag = nb.mul(I("Edge Ragged"), nb.smooth(lodv, 3.0, 5.0))
    jag = nb.add(A, nb.mul(nb.sub(cellr, 0.5), nb.mul(rag, 0.7)))
    a_bin = nb.math('GREATER_THAN', jag, 0.5)
    hard = nb.mul(I("Alpha Hardness"), nb.smooth(lodv, 1.0, 3.0))
    a = nb.mix(hard, A, a_bin)
    a = nb.mul(nb.mul(a, I("Opacity")), nb.smooth(dz, 0.0, I("Horizon Fade")))

    tree.links.new(col, gout.inputs["Color"])
    tree.links.new(a, gout.inputs["Alpha"])
    return tree


def build_sun_body_material(name="LV_Sky_SunBody_Mat"):
    mat = _new_material(name)
    nb = NB(mat.node_tree, x0=-600, y0=200, rows=4, dx=260, dy=220)
    G = nb.node('ShaderNodeGroup')
    G.node_tree = build_globals()
    col = nb.vscale(G.outputs["Sun Color"], 4.0)
    _emission_out(nb, col)
    return mat


def build_moon_material(name="LV_Sky_MoonBody_Mat"):
    mat = _new_material(name)
    nb = NB(mat.node_tree, x0=-800, y0=200, rows=4, dx=260, dy=220)
    tc = nb.node('ShaderNodeTexCoord')
    f, _c = _noise(nb, tc.outputs['Object'], 2.4, 5.0, 0.6)
    maria = nb.mix(nb.smooth(f, 0.42, 0.58), 1.0, 0.62)
    col = nb.vscale((0.80, 0.88, 1.0), nb.mul(maria, 1.4))
    _emission_out(nb, col)
    return mat


# ------------------------------------------------------------- materials
def _new_material(name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes"):
        try:
            mat.use_nodes = True
        except Exception:
            pass
    mat.node_tree.nodes.clear()
    for attr, val in (("surface_render_method", 'DITHERED'), ("use_backface_culling", False)):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    return mat


def _view_dir(nb):
    geo = nb.node('ShaderNodeNewGeometry')
    oi = nb.node('ShaderNodeObjectInfo')
    return nb.normalize(nb.vmath('SUBTRACT', geo.outputs['Position'], oi.outputs['Location']))


def _emission_out(nb, color):
    em = nb.node('ShaderNodeEmission')
    nb.set(em.inputs['Color'], color)
    nb.set(em.inputs['Strength'], 1.0)
    out = nb.node('ShaderNodeOutputMaterial')
    nb.t.links.new(em.outputs[0], out.inputs['Surface'])
    return out


def build_sky_only_material(name):
    mat = _new_material(name)
    nb = NB(mat.node_tree, x0=-1000, y0=400, rows=6, dx=260, dy=240)
    d = _view_dir(nb)
    sky = nb.node('ShaderNodeGroup', label="Sky Base", name="SKY")
    sky.node_tree = build_skybase()
    nb.set(sky.inputs['View Dir'], d)
    _emission_out(nb, sky.outputs['Color'])
    return mat


def build_shell_material(name, spec):
    """Hemisphere shell carrying one 2D cloud layer: opaque cut-out (binary-ish alpha),
    so nested shells sort by real depth with no dither noise."""
    mat = _new_material(name)
    nb = NB(mat.node_tree, x0=-1000, y0=400, rows=6, dx=260, dy=240)
    d = _view_dir(nb)
    n = nb.node('ShaderNodeGroup', label=spec.get('label', spec['uid']), name=spec['uid'])
    n.node_tree = spec['tree']
    nb.set(n.inputs['View Dir'], d)
    em = nb.node('ShaderNodeEmission')
    nb.set(em.inputs['Color'], n.outputs['Color'])
    tr = nb.node('ShaderNodeBsdfTransparent')
    mixs = nb.node('ShaderNodeMixShader')
    nb.set(mixs.inputs[0], n.outputs['Alpha'])
    nb.set(mixs.inputs[1], tr.outputs[0])
    nb.set(mixs.inputs[2], em.outputs[0])
    out = nb.node('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(mixs.outputs[0], out.inputs['Surface'])
    return mat


def capture_values(node):
    """Read all socket values of a layer group node (to survive a rebuild)."""
    vals = {}
    for s in node.inputs:
        if s.name == "View Dir" or s.is_linked:
            continue
        v = getattr(s, "default_value", None)
        if v is None:
            continue
        try:
            vals[s.name] = tuple(v)
        except TypeError:
            vals[s.name] = v
    return vals


def apply_values(node, values):
    for k, v in values.items():
        s = node.inputs.get(k)
        if s is None or s.is_linked:
            continue
        try:
            s.default_value = v
        except (TypeError, ValueError):
            pass
