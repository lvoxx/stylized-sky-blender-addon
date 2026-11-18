# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy.types import Operator, Panel, PropertyGroup, UIList
from . import presets, rig, shaders


def _rebuild(self, context):
    if context.scene.lv_sky.controller and not rig.SUSPEND[0]:
        rig.rebuild(context)


def _sun_angles_update(self, context):
    s = context.scene.lv_sky
    if s.sun:
        rig.set_sun_angles(s.sun, s.sun_elevation, s.sun_azimuth)


def _time_update(self, context):
    s = context.scene.lv_sky
    elev, az = presets.time_to_sun(s.time_of_day)
    s["sun_elevation"], s["sun_azimuth"] = elev, az
    if s.sun:
        rig.set_sun_angles(s.sun, elev, az)


def _sun_update(self, context):
    if context.scene.lv_sky.controller:
        rig.bind_globals(context.scene)


def _sun_poll(self, obj):
    return obj.type == 'LIGHT' and obj.data.type == 'SUN'


def _follow_update(self, context):
    rig.sync_follow_camera(context.scene)


class LVSkyLayer(PropertyGroup):
    uid: StringProperty()
    name: StringProperty(name="Name", default="Layer")
    genus: EnumProperty(name="Genus", items=presets.GENUS_ITEMS)
    enabled: BoolProperty(name="Enabled", default=True, update=_rebuild)
    use_voronoi: BoolProperty(name="Billow (Voronoi)", default=True, update=_rebuild,
                              description="Voronoi puffs for round cauliflower shapes (costlier)")
    tiers: IntProperty(name="Tiers", min=1, max=4, default=3, update=_rebuild,
                       description="Planes sampled between Altitude and Altitude+Height (gravity / tower shape)")
    use_transition: BoolProperty(name="Transition", default=False, update=_rebuild)
    t_start: FloatProperty(name="Start", min=0.0, max=1.0, default=0.0, update=_rebuild)
    t_end: FloatProperty(name="End", min=0.0, max=1.0, default=0.3, update=_rebuild)


class LVSkySettings(PropertyGroup):
    controller: PointerProperty(type=bpy.types.Object)
    dome: PointerProperty(type=bpy.types.Object)
    sun: PointerProperty(type=bpy.types.Object, name="Sun", poll=_sun_poll, update=_sun_update)
    variation: FloatProperty(name="Variation", default=1.0, min=0.0, max=2.0,
                             description="How much each weather preset is randomized when applied")
    sky_seed: IntProperty(name="Sky Seed", default=0, min=0, max=100000,
                          description="0 = new random sky every time; otherwise reproducible")
    dome_radius: FloatProperty(name="Dome Radius", default=900.0, min=50.0, soft_max=5000.0,
                               unit='LENGTH', update=_rebuild)
    follow_camera: BoolProperty(name="Follow Camera", default=True, update=_follow_update)
    celestial: BoolProperty(name="Sun / Moon Spheres", default=True, update=_rebuild,
                            description="Sun and Moon as spheres on opposite sides (follow the Sun light)")
    sun_size: FloatProperty(name="Sun Size", default=0.02, min=0.003, max=0.4, update=_rebuild,
                            description="Angular radius in radians (0.0047 = real)")
    moon_size: FloatProperty(name="Moon Size", default=0.023, min=0.003, max=0.4, update=_rebuild)
    light_scene: BoolProperty(name="Light / Reflect in Scene", default=False, update=_rebuild,
                              description="Let the dome contribute to Cycles lighting & reflections")
    layers: CollectionProperty(type=LVSkyLayer)
    layer_index: IntProperty(default=0)
    layers_changed_flag: BoolProperty(default=False)
    weather: EnumProperty(name="Weather", items=presets.WEATHER_ITEMS, default='FAIR')
    sun_elevation: FloatProperty(name="Elevation", default=40.0, min=-30.0, max=90.0,
                                 update=_sun_angles_update)
    sun_azimuth: FloatProperty(name="Azimuth", default=140.0, min=0.0, max=360.0,
                               update=_sun_angles_update)
    time_of_day: FloatProperty(name="Time of Day", default=10.0, min=0.0, max=24.0,
                               update=_time_update)


# ---------------------------------------------------------------- operators
class LVSKY_OT_create(Operator):
    bl_idname = "lv_sky.create_rig"
    bl_label = "Create Sky Rig"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.lv_sky
        if not s.controller:
            rig.ensure_controller(context.scene)
        rig.ensure_sun(context.scene)
        if len(s.layers) == 0:
            rig.apply_weather(context, s.weather)
        else:
            rig.rebuild(context)
        rig.fit_camera_clip(context)
        return {'FINISHED'}


class LVSKY_OT_rebuild(Operator):
    bl_idname = "lv_sky.rebuild"
    bl_label = "Rebuild Shaders"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig.rebuild(context)
        return {'FINISHED'}


class LVSKY_OT_delete(Operator):
    bl_idname = "lv_sky.delete_rig"
    bl_label = "Delete Sky Rig"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig.delete_rig(context)
        return {'FINISHED'}


class LVSKY_OT_weather(Operator):
    bl_idname = "lv_sky.apply_weather"
    bl_label = "Apply Weather Preset"
    bl_description = "Replace all layers with the selected weather preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig.apply_weather(context, context.scene.lv_sky.weather)
        return {'FINISHED'}


class LVSKY_OT_reroll(Operator):
    bl_idname = "lv_sky.reroll"
    bl_label = "Re-roll Clouds"
    bl_description = "New seeds and jittered scale/coverage/wind for every layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig.reroll(context)
        return {'FINISHED'}


class LVSKY_OT_layer_add(Operator):
    bl_idname = "lv_sky.layer_add"
    bl_label = "Add Layer"
    bl_options = {'REGISTER', 'UNDO'}
    genus: EnumProperty(name="Genus", items=presets.GENUS_ITEMS, default='CU_MEDIOCRIS')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        L, vals = rig.add_layer(context.scene, self.genus, {"Seed": float(len(context.scene.lv_sky.layers)) * 3.7})
        rig.rebuild(context, {L.uid: vals})
        return {'FINISHED'}


class LVSKY_OT_layer_remove(Operator):
    bl_idname = "lv_sky.layer_remove"
    bl_label = "Remove Layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.lv_sky
        if not s.layers:
            return {'CANCELLED'}
        L = s.layers[s.layer_index]
        rig.remove_layer_data(L)
        s.layers.remove(s.layer_index)
        s.layer_index = max(0, s.layer_index - 1)
        rig.rebuild(context)
        return {'FINISHED'}


class LVSKY_OT_layer_genus(Operator):
    bl_idname = "lv_sky.layer_apply_genus"
    bl_label = "Apply Genus Preset"
    bl_description = "Reset the active layer's parameters to its genus preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.lv_sky
        if not s.layers:
            return {'CANCELLED'}
        L = s.layers[s.layer_index]
        vals = presets.genus_values(L.genus)
        with rig.suspend():
            L.use_voronoi = vals.get("Billow", 0.0) > 0.0
        rig.rebuild(context, {L.uid: dict(shaders.LAYER_DEFAULTS, **vals)})
        return {'FINISHED'}


class LVSKY_OT_fit(Operator):
    bl_idname = "lv_sky.fit_clip"
    bl_label = "Fit Camera Clip to Dome"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig.fit_camera_clip(context)
        return {'FINISHED'}


class LVSKY_OT_open_globals(Operator):
    bl_idname = "lv_sky.select_dome"
    bl_label = "Select Dome"

    def execute(self, context):
        d = context.scene.lv_sky.dome
        if d:
            for o in context.selected_objects:
                o.select_set(False)
            d.select_set(True)
            context.view_layer.objects.active = d
        return {'FINISHED'}


# ---------------------------------------------------------------- UI
class LVSKY_UL_layers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False)
        row.label(text=item.genus)


def _draw_inputs(layout, node, panel, spec=None):
    col = layout.column(align=True)
    for p, name, *_ in (spec or shaders.CLOUD_INPUTS):
        if p != panel:
            continue
        sock = node.inputs.get(name)
        if sock is not None and not sock.is_linked:
            col.prop(sock, "default_value", text=name)


class LVSKY_PT_main(Panel):
    bl_label = "Stylized Cloud Dome"
    bl_idname = "LVSKY_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sky"

    def draw(self, context):
        s = context.scene.lv_sky
        lay = self.layout
        if not s.controller:
            lay.prop(s, "weather", text="")
            lay.operator("lv_sky.create_rig", icon='WORLD')
            return
        row = lay.row(align=True)
        row.operator("lv_sky.rebuild", icon='FILE_REFRESH')
        row.operator("lv_sky.fit_clip", text="Fit Clip", icon='CAMERA_DATA')
        row.operator("lv_sky.delete_rig", text="", icon='TRASH')
        col = lay.column(align=True)
        col.prop(s, "dome_radius")
        col.prop(s, "follow_camera")
        col.prop(s, "light_scene")
        col.prop(s, "celestial")
        if s.celestial:
            row = col.row(align=True)
            row.prop(s, "sun_size")
            row.prop(s, "moon_size")


class LVSKY_PT_sun(Panel):
    bl_label = "Sun & Time"
    bl_idname = "LVSKY_PT_sun"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sky"
    bl_parent_id = "LVSKY_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.lv_sky.controller is not None

    def draw(self, context):
        s = context.scene.lv_sky
        lay = self.layout
        lay.prop(s, "sun")
        col = lay.column(align=True)
        col.prop(s, "time_of_day")
        col.prop(s, "sun_elevation")
        col.prop(s, "sun_azimuth")
        lay.label(text="(or rotate / keyframe the Sun object itself)")
        c = s.controller
        col = lay.column(align=True)
        col.prop(c, '["lv_time_scale"]', text="Wind Time Scale")
        col.prop(c, '["lv_time_offset"]', text="Wind Time Offset")
        col.prop(c, '["lv_front"]', text="Weather Progress", slider=True)
        col.separator()
        col.prop(c, '["lv_haze"]', text="Atmospheric Haze", slider=True)
        col.prop(c, '["lv_visibility"]', text="Visibility (km)")
        col.prop(c, '["lv_storm"]', text="Precipitation / Storm", slider=True)
        g = bpy.data.node_groups.get(shaders.GLOBALS)
        if g:
            pk = g.nodes.get("PlanetKm")
            if pk:
                lay.prop(pk.outputs[0], "default_value", text="Planet Radius (km)")
            lay.separator()
            for nm in ("RampSun", "RampZenith", "RampHorizon", "RampAmbient"):
                n = g.nodes.get(nm)
                if n:
                    lay.label(text=n.label)
                    lay.template_color_ramp(n, "color_ramp")


class LVSKY_PT_weather(Panel):
    bl_label = "Weather & Layers"
    bl_idname = "LVSKY_PT_weather"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sky"
    bl_parent_id = "LVSKY_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.lv_sky.controller is not None

    def draw(self, context):
        s = context.scene.lv_sky
        lay = self.layout
        row = lay.row(align=True)
        row.prop(s, "weather", text="")
        row.operator("lv_sky.apply_weather", text="Apply")
        row = lay.row(align=True)
        row.prop(s, "variation")
        row.prop(s, "sky_seed", text="Seed")
        lay.operator("lv_sky.reroll", icon='FILE_REFRESH')
        lay.template_list("LVSKY_UL_layers", "", s, "layers", s, "layer_index", rows=4)
        row = lay.row(align=True)
        row.operator("lv_sky.layer_add", text="Add", icon='ADD')
        row.operator("lv_sky.layer_remove", text="Remove", icon='REMOVE')


class LVSKY_PT_layer(Panel):
    bl_label = "Active Layer"
    bl_idname = "LVSKY_PT_layer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sky"
    bl_parent_id = "LVSKY_PT_main"

    @classmethod
    def poll(cls, context):
        s = context.scene.lv_sky
        return s.controller is not None and len(s.layers) > 0

    def draw(self, context):
        s = context.scene.lv_sky
        lay = self.layout
        L = s.layers[min(s.layer_index, len(s.layers) - 1)]
        node = rig.layer_node(s, L)
        row = lay.row(align=True)
        row.prop(L, "genus", text="")
        row.operator("lv_sky.layer_apply_genus", text="Reset")
        lay.prop(L, "use_voronoi")
        lay.prop(L, "tiers")
        box = lay.box()
        box.prop(L, "use_transition")
        if L.use_transition:
            r = box.row(align=True)
            r.prop(L, "t_start")
            r.prop(L, "t_end")
        if node is None:
            lay.label(text="Layer not built / disabled", icon='INFO')
            return
        lay.label(text="Altitude sets shell order: press Rebuild after changing it", icon='INFO')
        for p in shaders.CLOUD_PANELS:
            sub = lay.box()
            sub.label(text=p)
            _draw_inputs(sub, node, p, shaders.CLOUD_INPUTS)
        sky = (s.dome.active_material.node_tree.nodes.get("SKY") if s.dome and s.dome.active_material else None)
        if sky:
            box = lay.box()
            box.label(text="Sky Base")
            col = box.column(align=True)
            for name, *_ in shaders.SKY_INPUTS:
                if name == "Sun Disc":
                    continue
                col.prop(sky.inputs[name], "default_value", text=name)


CLASSES = (LVSkyLayer, LVSkySettings, LVSKY_OT_reroll, LVSKY_OT_create, LVSKY_OT_rebuild, LVSKY_OT_delete,
           LVSKY_OT_weather, LVSKY_OT_layer_add, LVSKY_OT_layer_remove, LVSKY_OT_layer_genus,
           LVSKY_OT_fit, LVSKY_OT_open_globals, LVSKY_UL_layers, LVSKY_PT_main, LVSKY_PT_sun,
           LVSKY_PT_weather, LVSKY_PT_layer)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.lv_sky = PointerProperty(type=LVSkySettings)


def unregister():
    del bpy.types.Scene.lv_sky
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
