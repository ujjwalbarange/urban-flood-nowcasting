"""LULC-to-Hydrologic Parameter Configuration.

Maps Mumbai LULC class codes to physically-based hydrologic parameters.
All values are sourced from standard hydrology literature:
- Manning's n: Chow (1959), USGS, HEC-RAS manual
- CN: USDA TR-55 (SCS Curve Number) for Type II storm, HSG B/C
- Horton f0/f_min: Standard urban hydrology texts

IMPORTANT: These are ASSUMED values from literature, NOT calibrated for Mumbai.
Every simulation using these values must record quality_status='assumed'.
"""

# LULC class_code -> hydrologic parameters
# class_code mapping from actual database:
#   1  = dense built-up
#   2  = medium built-up
#   3  = low-density built-up
#   4  = industrial
#   5  = commercial
#   6  = residential
#   7  = roads/transport
#   8  = railway land
#   9  = vegetation
#   10 = forest
#   11 = agricultural/open land
#   12 = wetlands
#   13 = mangroves
#   14 = lakes/water bodies
#   15 = rivers/drainage
#   16 = beaches/coastal
#   17 = barren/open ground

LULC_PARAMS = {
    # class_code: {
    #   manning_n:      Manning's roughness coefficient (s/m^{1/3})
    #   imperviousness: fraction of impervious surface [0-1]
    #   cn:             SCS Curve Number for HSG C (dominant in Mumbai laterite/alluvial)
    #   horton_f0_mmh:  Horton initial infiltration rate (mm/hr)
    #   horton_fmin_mmh: Horton minimum (saturated) infiltration rate (mm/hr)
    #   horton_k_per_h: Horton decay constant (1/hr)
    #   source:         literature source for values
    # }
    1: {
        "class": "dense built-up",
        "manning_n": 0.015,
        "imperviousness": 0.90,
        "cn": 95,
        "horton_f0_mmh": 25.0,
        "horton_fmin_mmh": 1.0,
        "horton_k_per_h": 4.0,
        "source": "Chow 1959 / TR-55 / urban hydrology standard",
    },
    2: {
        "class": "medium built-up",
        "manning_n": 0.020,
        "imperviousness": 0.75,
        "cn": 90,
        "horton_f0_mmh": 40.0,
        "horton_fmin_mmh": 2.5,
        "horton_k_per_h": 3.5,
        "source": "Chow 1959 / TR-55",
    },
    3: {
        "class": "low-density built-up",
        "manning_n": 0.030,
        "imperviousness": 0.55,
        "cn": 85,
        "horton_f0_mmh": 55.0,
        "horton_fmin_mmh": 4.0,
        "horton_k_per_h": 3.0,
        "source": "Chow 1959 / TR-55",
    },
    4: {
        "class": "industrial",
        "manning_n": 0.015,
        "imperviousness": 0.85,
        "cn": 93,
        "horton_f0_mmh": 30.0,
        "horton_fmin_mmh": 1.5,
        "horton_k_per_h": 4.0,
        "source": "TR-55 / HEC-RAS manual",
    },
    5: {
        "class": "commercial",
        "manning_n": 0.015,
        "imperviousness": 0.88,
        "cn": 94,
        "horton_f0_mmh": 28.0,
        "horton_fmin_mmh": 1.2,
        "horton_k_per_h": 4.0,
        "source": "TR-55 / HEC-RAS manual",
    },
    6: {
        "class": "residential",
        "manning_n": 0.025,
        "imperviousness": 0.65,
        "cn": 88,
        "horton_f0_mmh": 50.0,
        "horton_fmin_mmh": 3.0,
        "horton_k_per_h": 3.0,
        "source": "TR-55 / Chow 1959",
    },
    7: {
        "class": "roads/transport",
        "manning_n": 0.013,
        "imperviousness": 0.95,
        "cn": 98,
        "horton_f0_mmh": 10.0,
        "horton_fmin_mmh": 0.5,
        "horton_k_per_h": 5.0,
        "source": "HEC-RAS manual / ASCE",
    },
    8: {
        "class": "railway land",
        "manning_n": 0.025,
        "imperviousness": 0.60,
        "cn": 86,
        "horton_f0_mmh": 45.0,
        "horton_fmin_mmh": 3.0,
        "horton_k_per_h": 3.0,
        "source": "TR-55 / estimated",
    },
    9: {
        "class": "vegetation",
        "manning_n": 0.050,
        "imperviousness": 0.10,
        "cn": 72,
        "horton_f0_mmh": 120.0,
        "horton_fmin_mmh": 8.0,
        "horton_k_per_h": 2.0,
        "source": "Chow 1959 / TR-55 grassland",
    },
    10: {
        "class": "forest",
        "manning_n": 0.100,
        "imperviousness": 0.05,
        "cn": 60,
        "horton_f0_mmh": 200.0,
        "horton_fmin_mmh": 12.0,
        "horton_k_per_h": 1.5,
        "source": "Chow 1959 / USGS forest channels",
    },
    11: {
        "class": "agricultural/open land",
        "manning_n": 0.035,
        "imperviousness": 0.15,
        "cn": 78,
        "horton_f0_mmh": 100.0,
        "horton_fmin_mmh": 6.0,
        "horton_k_per_h": 2.0,
        "source": "TR-55 / cultivated land HSG C",
    },
    12: {
        "class": "wetlands",
        "manning_n": 0.070,
        "imperviousness": 0.02,
        "cn": 78,
        "horton_f0_mmh": 60.0,
        "horton_fmin_mmh": 5.0,
        "horton_k_per_h": 2.5,
        "source": "Chow 1959 / wetland hydrology",
    },
    13: {
        "class": "mangroves",
        "manning_n": 0.120,
        "imperviousness": 0.02,
        "cn": 65,
        "horton_f0_mmh": 80.0,
        "horton_fmin_mmh": 8.0,
        "horton_k_per_h": 2.0,
        "source": "Mangrove forest hydrology literature",
    },
    14: {
        "class": "lakes/water bodies",
        "manning_n": 0.030,
        "imperviousness": 0.0,
        "cn": 100,
        "horton_f0_mmh": 0.0,
        "horton_fmin_mmh": 0.0,
        "horton_k_per_h": 0.0,
        "source": "Open water — no infiltration",
    },
    15: {
        "class": "rivers/drainage",
        "manning_n": 0.030,
        "imperviousness": 0.0,
        "cn": 100,
        "horton_f0_mmh": 0.0,
        "horton_fmin_mmh": 0.0,
        "horton_k_per_h": 0.0,
        "source": "Open channel — no infiltration",
    },
    16: {
        "class": "beaches/coastal",
        "manning_n": 0.025,
        "imperviousness": 0.0,
        "cn": 82,
        "horton_f0_mmh": 150.0,
        "horton_fmin_mmh": 10.0,
        "horton_k_per_h": 2.0,
        "source": "Sandy soil infiltration / beach hydrology",
    },
    17: {
        "class": "barren/open ground",
        "manning_n": 0.025,
        "imperviousness": 0.10,
        "cn": 86,
        "horton_f0_mmh": 80.0,
        "horton_fmin_mmh": 5.0,
        "horton_k_per_h": 2.5,
        "source": "TR-55 / bare soil compacted",
    },
}

# Default for unknown LULC class (conservative urban assumption)
DEFAULT_PARAMS = {
    "class": "unknown",
    "manning_n": 0.025,
    "imperviousness": 0.70,
    "cn": 88,
    "horton_f0_mmh": 50.0,
    "horton_fmin_mmh": 3.0,
    "horton_k_per_h": 3.0,
    "source": "conservative urban default — NOT calibrated",
}


def get_params_for_class(class_code: int) -> dict:
    """Get hydrologic parameters for a LULC class code."""
    return LULC_PARAMS.get(class_code, DEFAULT_PARAMS)
