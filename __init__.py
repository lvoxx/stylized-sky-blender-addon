# SPDX-License-Identifier: GPL-3.0-or-later
bl_info = {
    "name": "LV Stylized Cloud Dome",
    "author": "Lvoxx",
    "version": (0, 5, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > Sky",
    "description": "Procedural stylized cloud sky dome with Sun-driven toon shading (EEVEE/Cycles)",
    "category": "Lighting",
}

from . import ui


def register():
    ui.register()


def unregister():
    ui.unregister()
