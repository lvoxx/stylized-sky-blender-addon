# SPDX-License-Identifier: GPL-3.0-or-later
"""Presets for 2D cloud shells (parameter sets of ONE shader), plus randomization.

Gravity: Height + Taper + tiers give wide heavy bases and narrower tops. Distribution:
Cluster/Cluster Scale create big and small groups with clear-sky gaps. Heavy clouds
(rain / thunderstorm) use Heaviness -> dark slate colors instead of the neutral blue.
"""
import math
import random

_D = {}   # shared building blocks


def G(label, tiers, **v):
    return dict(label=label, tiers=tiers, v=v)


GENUS = {
    # --- low cumulus family -------------------------------------------------------------
    "CU_HUMILIS": G("Cumulus humilis (flat, low)", 2, Coverage=0.52, Softness=0.07, Scale=1500.0,
        Detail=4.5, Billow=0.7, Warp=0.5, Altitude=1400.0, Height=450.0, Taper=0.5, Relief=1.2,
        **{"Puff Detail": 0.4, "Base Dark": 0.3, "Wind Speed": 5.0}),
    "CU_MEDIOCRIS": G("Cumulus mediocris", 3, Coverage=0.58, Softness=0.07, Scale=2300.0,
        Detail=4.5, Billow=0.75, Warp=0.5, Altitude=1500.0, Height=1100.0, Taper=0.6, Relief=1.2,
        **{"Puff Detail": 0.45, "Wind Speed": 5.0}),
    "CU_CAULI": G("Cumulus cauliflower (big)", 4, Coverage=0.64, Softness=0.06, Scale=3000.0,
        Detail=5.0, Billow=0.7, Warp=0.65, Altitude=1600.0, Height=1700.0, Taper=0.72, Relief=1.4,
        **{"Puff Detail": 0.6, "Top Light": 0.45, "Base Dark": 0.32, "Wind Speed": 6.0}),
    "CU_FRACTUS": G("Cumulus fractus (ragged bits)", 1, Coverage=0.34, Softness=0.12, Scale=800.0,
        Detail=5.0, Billow=0.2, Warp=1.3, Altitude=1200.0, Height=250.0, Taper=0.3, Relief=0.9,
        **{"Edge Ragged": 0.85, "Alpha Hardness": 0.6, "Puff Detail": 0.3, "Cluster": 0.7,
           "Wind Speed": 9.0}),
    "CU_SCATTER": G("Cumulus scattered (small puffs)", 2, Coverage=0.32, Softness=0.07, Scale=1100.0,
        Detail=4.0, Billow=0.8, Warp=0.4, Altitude=1500.0, Height=550.0, Taper=0.55, Relief=1.2,
        Cluster=0.8, **{"Cluster Scale": 9000.0, "Puff Detail": 0.4}),
    "CU_CLUSTER": G("Cumulus clusters (with sky gaps)", 3, Coverage=0.66, Softness=0.07, Scale=2000.0,
        Detail=4.5, Billow=0.7, Warp=0.5, Altitude=1550.0, Height=1000.0, Taper=0.6, Relief=1.3,
        Cluster=1.0, **{"Cluster Scale": 8000.0, "Puff Detail": 0.45}),
    "CG": G("Cumulus congestus (tall tower)", 4, Coverage=0.6, Softness=0.06, Scale=3200.0,
        Detail=5.0, Billow=0.7, Warp=0.6, Altitude=1600.0, Height=3400.0, Taper=0.78, Relief=1.6,
        Heaviness=0.1, **{"Top Light": 0.55, "Base Dark": 0.35, "Core Shade": 0.3, "Wind Speed": 6.0}),
    # --- cumulonimbus family ------------------------------------------------------------
    "CB": G("Cumulonimbus (storm tower + anvil)", 4, Coverage=0.5, Softness=0.07, Scale=7000.0,
        Detail=5.0, Billow=0.55, Warp=0.7, Altitude=1800.0, Height=7500.0, Taper=0.66, Anvil=0.9,
        Relief=1.8, Heaviness=0.8,
        **{"Storm Response": 1.0, "Base Dark": 0.65, "Top Light": 0.5, "Core Shade": 0.35,
           "Wind Speed": 8.0, "Ambient": 0.28}),
    "CB_ANVIL": G("Anvil crown (high spread)", 2, Coverage=0.5, Softness=0.2, Scale=9000.0,
        Detail=4.0, Billow=0.2, Warp=0.8, Stretch=2.2, Altitude=9500.0, Height=1500.0, Taper=0.2,
        Anvil=0.9, Relief=0.8, Heaviness=0.25,
        **{"Alpha Hardness": 0.4, "Wind Speed": 18.0, "Top Light": 0.4}),
    "CB_SHELF": G("Shelf / arcus (storm front)", 2, Coverage=0.5, Softness=0.08, Scale=5000.0,
        Detail=4.0, Billow=0.3, Warp=0.5, Stretch=5.0, Altitude=1000.0, Height=800.0, Taper=0.5,
        Relief=1.4, Heaviness=0.9,
        **{"Storm Response": 1.0, "Base Dark": 0.7, "Wind Speed": 14.0}),
    "CB_MAMMATUS": G("Mammatus (hanging pouches)", 2, Coverage=0.6, Softness=0.1, Scale=650.0,
        Detail=3.0, Billow=0.95, Warp=0.3, Altitude=1300.0, Height=300.0, Taper=0.3, Relief=2.0,
        Heaviness=0.75, **{"Storm Response": 1.0, "Base Dark": 0.6, "Puff Detail": 0.7}),
    # --- stratiform low -----------------------------------------------------------------
    "SC_OPEN": G("Stratocumulus (open cells)", 2, Coverage=0.5, Softness=0.08, Scale=2500.0,
        Detail=4.0, Billow=0.6, Warp=0.5, Altitude=1900.0, Height=500.0, Taper=0.35, Relief=1.3,
        Cluster=0.5, **{"Wind Speed": 7.0}),
    "SC_CLOSED": G("Stratocumulus (closed deck)", 2, Coverage=0.78, Softness=0.08, Scale=2200.0,
        Detail=4.0, Billow=0.5, Warp=0.5, Altitude=1800.0, Height=500.0, Taper=0.3, Relief=1.3,
        Cluster=0.2, **{"Wind Speed": 7.0, "Ambient": 0.42}),
    "ST": G("Stratus (low sheet)", 1, Coverage=0.9, Softness=0.5, Scale=7000.0, Detail=2.5, Billow=0.0,
        Warp=0.3, Altitude=700.0, Height=200.0, Taper=0.0, Relief=0.5, Ambient=0.55,
        **{"Core Shade": 0.15, "Toon Mix": 0.5, "Alpha Hardness": 0.2, "Edge Ragged": 0.1,
           "Wind Speed": 3.0, "Top Light": 0.1, "Base Dark": 0.15, "Cluster": 0.4}),
    "ST_FOG": G("Fog bank (valley mist)", 1, Coverage=0.55, Softness=0.6, Scale=6000.0, Detail=2.0,
        Billow=0.0, Warp=0.4, Altitude=250.0, Height=100.0, Taper=0.0, Relief=0.2, Ambient=0.7,
        Cluster=0.9, **{"Alpha Hardness": 0.0, "Edge Ragged": 0.0, "Toon Mix": 0.3, "Opacity": 0.75,
                        "Core Shade": 0.05, "Base Dark": 0.05, "Top Light": 0.05, "Haze": 2.0,
                        "Wind Speed": 1.5}),
    "NS": G("Nimbostratus (rain)", 2, Coverage=0.97, Softness=0.5, Scale=8000.0, Detail=3.0, Billow=0.0,
        Warp=0.3, Altitude=1300.0, Height=2500.0, Taper=0.3, Relief=0.7, Heaviness=0.8,
        **{"Storm Response": 1.0, "Toon Mix": 0.5, "Alpha Hardness": 0.1, "Edge Ragged": 0.0,
           "Wind Speed": 6.0, "Cluster": 0.2, "Core Shade": 0.3, "Base Dark": 0.4}),
    "NS_HEAVY": G("Nimbostratus (heavy rain, dark)", 2, Coverage=1.0, Softness=0.5, Scale=6000.0,
        Detail=3.5, Billow=0.0, Warp=0.4, Altitude=1000.0, Height=2500.0, Taper=0.3, Relief=0.8,
        Heaviness=1.0, **{"Storm Response": 1.0, "Toon Mix": 0.6, "Alpha Hardness": 0.1,
                          "Edge Ragged": 0.0, "Wind Speed": 9.0, "Core Shade": 0.4, "Base Dark": 0.35,
                          "Cluster": 0.2}),
    # --- middle -------------------------------------------------------------------------
    "AC": G("Altocumulus (patches)", 2, Coverage=0.5, Softness=0.1, Scale=1100.0, Detail=3.5, Billow=0.6,
        Warp=0.5, Stretch=1.3, Altitude=4500.0, Height=500.0, Taper=0.4, Relief=1.3,
        **{"Core Shade": 0.2, "Wind Speed": 10.0, "Cluster": 0.6}),
    "AC_UNDULATUS": G("Altocumulus undulatus (rolls)", 1, Coverage=0.55, Softness=0.1, Scale=900.0,
        Detail=3.0, Billow=0.0, Warp=0.35, Stretch=6.0, Altitude=4300.0, Height=250.0, Taper=0.0,
        Relief=1.4, **{"Wind Angle": 1.5708, "Wind Speed": 8.0, "Cluster": 0.4}),
    "AS": G("Altostratus (grey veil)", 1, Coverage=0.88, Softness=0.45, Scale=9000.0, Detail=3.0,
        Billow=0.0, Warp=0.3, Altitude=4000.0, Height=500.0, Taper=0.0, Relief=0.4, Ambient=0.5,
        Heaviness=0.2, **{"Core Shade": 0.2, "Toon Mix": 0.5, "Alpha Hardness": 0.1,
                          "Edge Ragged": 0.1, "Wind Speed": 8.0, "Cluster": 0.3}),
    "LENT": G("Lenticularis (mountain lens)", 2, Coverage=0.28, Softness=0.08, Scale=3500.0, Detail=2.0,
        Billow=0.0, Warp=0.15, Stretch=3.0, Altitude=4200.0, Height=450.0, Taper=0.5, Relief=1.8,
        **{"Wind Speed": 1.0, "Cluster": 0.2}),
    "CAP": G("Cap cloud (over a peak)", 2, Coverage=0.3, Softness=0.1, Scale=2500.0, Detail=3.0,
        Billow=0.3, Warp=0.4, Altitude=2600.0, Height=500.0, Taper=0.5, Relief=1.4,
        Cluster=1.0, **{"Cluster Scale": 20000.0, "Wind Speed": 2.0}),
    # --- high ice clouds ------------------------------------------------------------------
    "CI": G("Cirrus (wisps)", 1, Coverage=0.4, Softness=0.3, Scale=5200.0, Detail=5.0, Billow=0.0,
        Warp=1.0, Stretch=8.0, Altitude=9000.0, Height=300.0, Taper=0.0, Relief=0.6, Ambient=0.5,
        **{"Core Shade": 0.1, "Sun Tint": 1.0, "Toon Mix": 0.4, "Alpha Hardness": 0.15,
           "Edge Ragged": 0.15, "Wind Speed": 25.0, "Opacity": 0.85, "Haze": 0.2, "Base Dark": 0.0,
           "Top Light": 0.1}),
    "CI_FIBRATUS": G("Cirrus fibratus (long streaks)", 1, Coverage=0.35, Softness=0.35, Scale=6000.0,
        Detail=5.5, Billow=0.0, Warp=0.5, Stretch=16.0, Altitude=9200.0, Height=300.0, Taper=0.0,
        Relief=0.4, Ambient=0.5, **{"Sun Tint": 1.0, "Toon Mix": 0.3, "Alpha Hardness": 0.0,
                                    "Edge Ragged": 0.1, "Wind Speed": 28.0, "Opacity": 0.8,
                                    "Haze": 0.2, "Base Dark": 0.0, "Top Light": 0.1, "Core Shade": 0.05}),
    "CI_UNCINUS": G("Cirrus uncinus (hooks)", 1, Coverage=0.38, Softness=0.25, Scale=4500.0,
        Detail=5.0, Billow=0.0, Warp=2.2, Stretch=6.0, Altitude=8800.0, Height=300.0, Taper=0.0,
        Relief=0.6, Ambient=0.5, **{"Sun Tint": 1.0, "Toon Mix": 0.4, "Alpha Hardness": 0.2,
                                    "Edge Ragged": 0.2, "Wind Speed": 22.0, "Opacity": 0.85,
                                    "Haze": 0.2, "Base Dark": 0.0, "Top Light": 0.1, "Core Shade": 0.1}),
    "CI_MARES": G("Mares' tails (streaks, high contrast)", 1, Coverage=0.3, Softness=0.2, Scale=4000.0,
        Detail=5.0, Billow=0.0, Warp=1.5, Stretch=11.0, Altitude=8500.0, Height=300.0, Taper=0.0,
        Relief=0.8, Ambient=0.45, **{"Sun Tint": 1.0, "Toon Mix": 0.55, "Alpha Hardness": 0.35,
                                     "Edge Ragged": 0.2, "Wind Speed": 30.0, "Opacity": 0.95,
                                     "Haze": 0.2, "Base Dark": 0.0, "Top Light": 0.1, "Core Shade": 0.1}),
    "CS": G("Cirrostratus (veil + halo)", 1, Coverage=0.85, Softness=0.55, Scale=14000.0, Detail=2.5,
        Billow=0.0, Warp=0.4, Stretch=1.5, Altitude=8500.0, Height=300.0, Taper=0.0, Relief=0.3,
        Ambient=0.55, Halo=0.8, **{"Core Shade": 0.0, "Sun Tint": 1.0, "Toon Mix": 0.3,
                                   "Alpha Hardness": 0.0, "Edge Ragged": 0.0, "Wind Speed": 15.0,
                                   "Opacity": 0.7, "Haze": 0.2, "Base Dark": 0.0, "Top Light": 0.0}),
    "CC": G("Cirrocumulus (mackerel sky)", 1, Coverage=0.5, Softness=0.12, Scale=800.0, Detail=2.5,
        Billow=0.85, Warp=0.5, Altitude=7500.0, Height=250.0, Taper=0.0, Relief=1.2, Ambient=0.5,
        **{"Core Shade": 0.15, "Sun Tint": 1.0, "Wind Speed": 12.0, "Haze": 0.3, "Base Dark": 0.1,
           "Top Light": 0.1, "Cluster": 0.6}),
}
# keep the previous keys working in saved files
GENUS["CU"] = dict(GENUS["CU_MEDIOCRIS"], label="Cumulus (puffy)")
GENUS["SC"] = dict(GENUS["SC_OPEN"], label="Stratocumulus")
GENUS_ITEMS = [(k, v["label"], "") for k, v in GENUS.items() if k not in ("CU", "SC")]


def genus_values(genus):
    return dict(GENUS[genus]["v"])


def genus_tiers(genus):
    return GENUS[genus]["tiers"]


# (genus, overrides, transition) ; 'storm' darkens sky + heavy clouds, 'haze' / 'vis'(km)
def W(label, layers, storm=0.0, haze=0.35, vis=40.0):
    return dict(label=label, layers=layers, storm=storm, haze=haze, vis=vis)


WEATHER = {
    "CLEAR": W("Clear Sky", [], haze=0.25, vis=60.0),
    "WISPY": W("Wispy Sky", [("CI", {"Altitude": 9000.0}, None), ("CI_FIBRATUS", {"Altitude": 10000.0, "Coverage": 0.25}, None)]),
    "MARES": W("Mares' Tails Day", [("CI_MARES", {}, None), ("CU_SCATTER", {"Coverage": 0.25}, None)]),
    "MACKEREL": W("Mackerel Sky", [("CC", {}, None), ("CI", {"Coverage": 0.25}, None)]),
    "WAVES": W("Wave Sky (undulatus)", [("AC_UNDULATUS", {}, None), ("CI_FIBRATUS", {"Coverage": 0.2}, None)]),
    "FAIR": W("Fair Weather", [("CU_HUMILIS", {}, None), ("CU_SCATTER", {"Altitude": 1900.0}, None),
                               ("CI", {"Coverage": 0.2, "Opacity": 0.6}, None)]),
    "FRACTUS": W("Scattered Fractus", [("CU_FRACTUS", {}, None), ("CU_SCATTER", {"Coverage": 0.28, "Altitude": 1800.0}, None),
                                       ("CI_UNCINUS", {"Coverage": 0.25}, None)]),
    "BROKEN": W("Broken Clouds (big gaps)", [("CU_CLUSTER", {}, None), ("CU_HUMILIS", {"Coverage": 0.3, "Cluster": 1.0, "Altitude": 1100.0}, None),
                                             ("CI", {"Coverage": 0.2}, None)]),
    "PUFFY": W("Puffy Summer", [("CU_MEDIOCRIS", {"Altitude": 1400.0}, None),
                                ("CU_CAULI", {"Coverage": 0.55, "Altitude": 2200.0}, None),
                                ("CI", {"Coverage": 0.2, "Opacity": 0.6}, None)]),
    "CAULI": W("Cauliflower Afternoon", [("CU_CAULI", {}, None), ("CU_MEDIOCRIS", {"Altitude": 1100.0, "Coverage": 0.4}, None),
                                         ("CI_FIBRATUS", {"Coverage": 0.2}, None)], haze=0.45),
    "DRAMATIC": W("Dramatic Sky", [("CG", {}, None), ("CU_CAULI", {"Coverage": 0.38, "Altitude": 1100.0}, None),
                                   ("AC", {"Coverage": 0.3, "Altitude": 4600.0}, None),
                                   ("CI_UNCINUS", {"Coverage": 0.3}, None)]),
    "DECK": W("Cloud Deck", [("SC_CLOSED", {}, None), ("AC", {"Coverage": 0.3}, None), ("CI", {"Coverage": 0.2}, None)]),
    "HAZY": W("Hazy Summer", [("CU_HUMILIS", {"Haze": 1.5}, None), ("CU_SCATTER", {"Altitude": 1900.0, "Haze": 1.5}, None)],
              haze=0.85, vis=10.0),
    "FOG": W("Morning Fog", [("ST_FOG", {}, None), ("ST", {"Coverage": 0.5, "Altitude": 900.0, "Opacity": 0.6}, None)],
             haze=0.85, vis=6.0),
    "OVERCAST": W("Overcast", [("ST", {"Coverage": 0.92}, None), ("AS", {"Coverage": 0.92}, None)], storm=0.35, haze=0.5, vis=25.0),
    "LIGHT_RAIN": W("Light Rain", [("NS", {"Heaviness": 0.55}, None), ("AS", {"Coverage": 0.95}, None),
                                   ("ST", {"Coverage": 0.6, "Altitude": 600.0, "Heaviness": 0.5}, None)], storm=0.55, haze=0.6, vis=14.0),
    "RAINY": W("Rainy", [("NS", {}, None), ("AS", {"Coverage": 1.0, "Heaviness": 0.6}, None),
                         ("ST", {"Coverage": 0.7, "Altitude": 650.0, "Heaviness": 0.8}, None)], storm=0.75, haze=0.65, vis=9.0),
    "FRONT": W("Approaching Front (animate 'Weather Progress')", [
        ("CI", {"Coverage": 0.45}, (0.00, 0.20)), ("CS", {}, (0.15, 0.45)),
        ("AS", {"Coverage": 0.95}, (0.35, 0.70)), ("NS", {}, (0.60, 1.00))], haze=0.45, vis=30.0),
    "STORM": W("Thunderstorm", [("CB", {}, None), ("CB_ANVIL", {}, None),
                                ("ST", {"Coverage": 0.5, "Altitude": 800.0, "Heaviness": 0.9}, None),
                                ("AS", {"Coverage": 0.75, "Heaviness": 0.7}, None)], storm=0.85, haze=0.55, vis=14.0),
    "SQUALL": W("Squall Line (shelf + mammatus)", [("CB_SHELF", {}, None), ("CB_MAMMATUS", {}, None),
                                                   ("CB", {"Coverage": 0.34, "Altitude": 2100.0}, None)],
                storm=0.8, haze=0.6, vis=12.0),
    "HEAVY": W("Heavy Rain (dark)", [("NS_HEAVY", {}, None), ("CB_MAMMATUS", {"Coverage": 0.5, "Altitude": 1100.0}, None),
                                     ("ST", {"Coverage": 0.8, "Altitude": 500.0, "Heaviness": 1.0}, None)],
               storm=1.0, haze=0.7, vis=5.0),
    "TROPICAL": W("Tropical", [("CU_MEDIOCRIS", {"Coverage": 0.48}, None), ("CB", {"Coverage": 0.28, "Altitude": 2000.0, "Heaviness": 0.4}, None),
                               ("CI", {"Coverage": 0.22}, None)], haze=0.6, vis=22.0),
    "MOUNTAIN": W("Mountain (lens + cap)", [("LENT", {}, None), ("CAP", {}, None), ("CU_SCATTER", {"Coverage": 0.2, "Altitude": 2200.0}, None)]),
}
WEATHER_ITEMS = [(k, v["label"], "") for k, v in WEATHER.items()]


# ------------------------------------------------------------------ randomization
def _limits():
    from . import shaders
    return {n: (a, b) for (_p, n, _t, _d, a, b) in shaders.CLOUD_INPUTS if a is not None}


def jitter(vals, amount, rng):
    """Randomize a parameter dict so repeated presets don't look identical."""
    v = dict(vals)
    if amount <= 0:
        return v
    lim = _limits()

    def mul(k, spread):
        if k in v and isinstance(v[k], (int, float)):
            v[k] = v[k] * (1.0 + rng.uniform(-spread, spread) * amount)

    def add(k, spread):
        if k in v and isinstance(v[k], (int, float)):
            v[k] = v[k] + rng.uniform(-spread, spread) * amount

    v["Seed"] = rng.uniform(0.0, 900.0)
    mul("Scale", 0.3)
    mul("Height", 0.3)
    mul("Stretch", 0.2)
    mul("Altitude", 0.06)
    mul("Wind Speed", 0.3)
    add("Coverage", 0.09)
    add("Taper", 0.12)
    add("Cluster", 0.2)
    add("Warp", 0.2)
    add("Puff Detail", 0.12)
    if "Wind Angle" in v or amount > 0:
        v["Wind Angle"] = v.get("Wind Angle", 0.0) + rng.uniform(-0.9, 0.9) * amount
    for k, x in list(v.items()):
        if k in lim and isinstance(x, (int, float)):
            a, b = lim[k]
            v[k] = max(a, min(b, x))
    return v


def time_to_sun(hour):
    """Simple stylized solar path: hour 0-24 -> (elevation_deg, azimuth_deg)."""
    s = math.sin((hour - 6.0) / 12.0 * math.pi)
    elev = 72.0 * s if s > 0 else 30.0 * s
    az = 90.0 + (hour - 6.0) / 12.0 * 180.0
    return elev, az % 360.0
