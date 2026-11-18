# LV Stylized Cloud Dome v0.5 (Blender 4.2+ / 5.x)

2D clouds on nested hemisphere shells (no cloud meshes, no volumes):
- Sky dome (outer): gradient, night stars + Milky Way, moon glow.
- One hemisphere shell per cloud layer; higher altitude = bigger shell enclosing the lower ones.
  Opaque cut-out alpha -> shells sort by real depth, no dither/sorting noise.
- Shading from a 2D height-field: density slope toward the Sun gives lit/shaded sides, a sun-offset
  sample gives broad self-shadow, toon bands, silver lining; Voronoi puffs only on the rim.
- Sun and Moon are spheres on opposite sides following the Sun light's rotation.
Install: Preferences > Add-ons > Install from Disk. Panel: 3D Viewport > N > "Sky".

v0.5: tiered gravity structure (Height/Taper/Anvil, Tiers per layer), coverage mask (Cluster) for
big/small groups and sky gaps, global Atmospheric Haze / Visibility / Precipitation (controller
properties, driven into every shader), heavy-cloud palette (Heaviness, Storm Lit/Shade),
30 genus variants, 24 weather presets, Variation + Re-roll so skies don't repeat.
