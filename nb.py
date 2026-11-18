# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny helper to build shader node graphs from Python with auto-linking.

Every helper accepts either a python number/tuple (becomes a default value)
or a NodeSocket / Node (becomes a link), and returns an output socket so
calls can be chained like normal expressions.
"""
import bpy


class NB:
    def __init__(self, tree, x0=0, y0=0, rows=14, dx=230, dy=170):
        self.t = tree
        self.x0, self.y0, self.rows, self.dx, self.dy = x0, y0, rows, dx, dy
        self._i = 0

    # ------------------------------------------------------------------ core
    def node(self, idname, label=None, name=None, **props):
        n = self.t.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        if label:
            n.label = label
        if name:
            n.name = name
        n.location = (self.x0 + (self._i // self.rows) * self.dx,
                      self.y0 - (self._i % self.rows) * self.dy)
        self._i += 1
        return n

    def set(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        elif isinstance(v, bpy.types.Node):
            self.t.links.new(v.outputs[0], sock)
        else:
            try:
                sock.default_value = v
            except (TypeError, ValueError):
                sock.default_value = tuple(v)

    # ------------------------------------------------------------- scalars
    def val(self, v, label=None, name=None):
        n = self.node('ShaderNodeValue', label=label, name=name)
        n.outputs[0].default_value = v
        return n.outputs[0]

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        self.set(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b): return self.math('ADD', a, b)
    def sub(self, a, b): return self.math('SUBTRACT', a, b)
    def mul(self, a, b): return self.math('MULTIPLY', a, b)
    def div(self, a, b): return self.math('DIVIDE', a, b)
    def pw(self, a, b): return self.math('POWER', a, b)
    def mn(self, a, b): return self.math('MINIMUM', a, b)
    def mx(self, a, b): return self.math('MAXIMUM', a, b)
    def sat(self, a): return self.math('ADD', a, 0.0, clamp=True)
    def sqrt(self, a): return self.math('SQRT', a)
    def exp(self, a): return self.math('EXPONENT', a)
    def madd(self, a, b, c): return self.math('MULTIPLY_ADD', a, b, c)

    def smooth(self, x, e0, e1, lo=0.0, hi=1.0, interp='SMOOTHSTEP'):
        """smoothstep(e0, e1, x) remapped to [lo, hi]. e0 > e1 gives a falling edge."""
        n = self.node('ShaderNodeMapRange', data_type='FLOAT',
                      interpolation_type=interp, clamp=True)
        for i, v in enumerate((x, e0, e1, lo, hi)):
            self.set(n.inputs[i], v)
        return n.outputs[0]

    def remap(self, x, a0, a1, b0, b1, clamp=True):
        n = self.node('ShaderNodeMapRange', data_type='FLOAT',
                      interpolation_type='LINEAR', clamp=clamp)
        for i, v in enumerate((x, a0, a1, b0, b1)):
            self.set(n.inputs[i], v)
        return n.outputs[0]

    # ------------------------------------------------------------- vectors
    def vmath(self, op, a, b=None, scale=None, out=0):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        if scale is not None:
            self.set(n.inputs[3], scale)
        return n.outputs[out]

    def dot(self, a, b): return self.vmath('DOT_PRODUCT', a, b, out=1)
    def normalize(self, a): return self.vmath('NORMALIZE', a)
    def vscale(self, a, s): return self.vmath('SCALE', a, None, scale=s)

    def xyz(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self.set(n.inputs[0], x)
        self.set(n.inputs[1], y)
        self.set(n.inputs[2], z)
        return n.outputs[0]

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.set(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def mapping(self, vec, loc=None, rot=None, scale=None, kind='TEXTURE'):
        n = self.node('ShaderNodeMapping', vector_type=kind)
        self.set(n.inputs[0], vec)
        self.set(n.inputs[1], loc)
        self.set(n.inputs[2], rot)
        self.set(n.inputs[3], scale)
        return n.outputs[0]

    # --------------------------------------------------------------- mixing
    def mix(self, fac, a, b, kind='FLOAT', clamp=True):
        n = self.node('ShaderNodeMix', data_type=kind, clamp_factor=clamp)
        ia, ib = {'FLOAT': (2, 3), 'VECTOR': (4, 5), 'RGBA': (6, 7)}[kind]
        out = {'FLOAT': 0, 'VECTOR': 1, 'RGBA': 2}[kind]
        self.set(n.inputs[0], fac)
        self.set(n.inputs[ia], a)
        self.set(n.inputs[ib], b)
        return n.outputs[out]

    def cmix(self, fac, a, b):
        return self.mix(fac, a, b, kind='RGBA')

    def ramp(self, fac, stops, interpolation='LINEAR'):
        """stops: list of (position, (r, g, b, a)) sorted ascending."""
        n = self.node('ShaderNodeValToRGB')
        el = n.color_ramp.elements
        el[0].position, el[0].color = stops[0]
        el[1].position, el[1].color = stops[-1]
        for pos, col in stops[1:-1]:
            e = el.new(pos)
            e.color = col
        n.color_ramp.interpolation = interpolation
        self.set(n.inputs[0], fac)
        return n


def srgb(hexstr, a=1.0):
    """'#rrggbb' -> linear RGBA tuple (so palettes can be written in sRGB)."""
    h = hexstr.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c]
    return (lin[0], lin[1], lin[2], a)
