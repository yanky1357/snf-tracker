"""ReefPilot — Reference data: salt brands, parameter ranges, constants."""

# Salt brand mix ratios: grams of salt per liter of RODI water to reach ~1.026 SG
SALT_BRANDS = {
    "red_sea_coral_pro": {
        "name": "Red Sea Coral Pro",
        "grams_per_liter": 39.5,
        "notes": "Elevated Alk/Ca/Mg — designed for reef tanks"
    },
    "red_sea_blue": {
        "name": "Red Sea Blue Bucket",
        "grams_per_liter": 38.5,
        "notes": "Lower Alk — good for tanks that dose separately"
    },
    "instant_ocean": {
        "name": "Instant Ocean",
        "grams_per_liter": 36.0,
        "notes": "Classic mix, moderate parameters"
    },
    "instant_ocean_reef": {
        "name": "Instant Ocean Reef Crystals",
        "grams_per_liter": 37.5,
        "notes": "Enhanced calcium and buffering for reef tanks"
    },
    "fritz_rpm": {
        "name": "Fritz RPM",
        "grams_per_liter": 38.0,
        "notes": "Elevated Alk/Ca/Mg, clean dissolve"
    },
    "tropic_marin_pro": {
        "name": "Tropic Marin Pro Reef",
        "grams_per_liter": 37.0,
        "notes": "Natural seawater ratios, pharmaceutical-grade"
    },
    "aquaforest_reef": {
        "name": "Aquaforest Reef Salt",
        "grams_per_liter": 37.5,
        "notes": "Probiotic formula with beneficial bacteria"
    },
    "hw_reefer": {
        "name": "HW Reefer's Best",
        "grams_per_liter": 37.0,
        "notes": "German-made, very clean dissolve"
    },
    "brightwell_neomarine": {
        "name": "Brightwell NeoMarine",
        "grams_per_liter": 37.5,
        "notes": "Pharmaceutical-grade, consistent batches"
    },
    "kent_reef": {
        "name": "Kent Reef Salt",
        "grams_per_liter": 37.0,
        "notes": "Good all-around reef salt"
    },
}

# Parameter types with display info
PARAMETER_TYPES = {
    "salinity":    {"label": "Salinity",     "unit": "SG",   "icon": "S"},
    "ph":          {"label": "pH",           "unit": "",     "icon": "pH"},
    "alkalinity":  {"label": "Alkalinity",   "unit": "dKH",  "icon": "KH"},
    "calcium":     {"label": "Calcium",      "unit": "ppm",  "icon": "Ca"},
    "magnesium":   {"label": "Magnesium",    "unit": "ppm",  "icon": "Mg"},
    "nitrate":     {"label": "Nitrate",      "unit": "ppm",  "icon": "NO3"},
    "nitrite":     {"label": "Nitrite",      "unit": "ppm",  "icon": "NO2"},
    "ammonia":     {"label": "Ammonia",      "unit": "ppm",  "icon": "NH3"},
    "phosphate":   {"label": "Phosphate",    "unit": "ppm",  "icon": "PO4"},
    "temperature": {"label": "Temperature",  "unit": "F",    "icon": "T"},
}

# Parameter ranges by tank type
# green = ideal, yellow = caution, red = danger
PARAMETER_RANGES = {
    "fowlr": {
        "salinity":    {"min": 1.020, "max": 1.025, "warn_low": 1.018, "warn_high": 1.027},
        "ph":          {"min": 8.0,   "max": 8.4,   "warn_low": 7.8,   "warn_high": 8.5},
        "alkalinity":  {"min": 7.0,   "max": 12.0,  "warn_low": 6.0,   "warn_high": 14.0},
        "calcium":     {"min": 350,   "max": 500,   "warn_low": 300,   "warn_high": 550},
        "magnesium":   {"min": 1200,  "max": 1400,  "warn_low": 1100,  "warn_high": 1500},
        "nitrate":     {"min": 0,     "max": 40,    "warn_low": 0,     "warn_high": 80},
        "nitrite":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.25},
        "ammonia":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.25},
        "phosphate":   {"min": 0,     "max": 0.5,   "warn_low": 0,     "warn_high": 1.0},
        "temperature": {"min": 75,    "max": 80,    "warn_low": 72,    "warn_high": 84},
    },
    "soft_coral": {
        "salinity":    {"min": 1.024, "max": 1.026, "warn_low": 1.022, "warn_high": 1.028},
        "ph":          {"min": 8.0,   "max": 8.4,   "warn_low": 7.8,   "warn_high": 8.5},
        "alkalinity":  {"min": 7.0,   "max": 11.0,  "warn_low": 6.0,   "warn_high": 13.0},
        "calcium":     {"min": 380,   "max": 450,   "warn_low": 340,   "warn_high": 500},
        "magnesium":   {"min": 1250,  "max": 1350,  "warn_low": 1150,  "warn_high": 1450},
        "nitrate":     {"min": 0,     "max": 20,    "warn_low": 0,     "warn_high": 50},
        "nitrite":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.1},
        "ammonia":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.1},
        "phosphate":   {"min": 0,     "max": 0.1,   "warn_low": 0,     "warn_high": 0.3},
        "temperature": {"min": 76,    "max": 80,    "warn_low": 74,    "warn_high": 82},
    },
    "lps": {
        "salinity":    {"min": 1.024, "max": 1.026, "warn_low": 1.022, "warn_high": 1.028},
        "ph":          {"min": 8.0,   "max": 8.4,   "warn_low": 7.8,   "warn_high": 8.5},
        "alkalinity":  {"min": 7.0,   "max": 10.0,  "warn_low": 6.0,   "warn_high": 12.0},
        "calcium":     {"min": 400,   "max": 450,   "warn_low": 360,   "warn_high": 500},
        "magnesium":   {"min": 1280,  "max": 1350,  "warn_low": 1200,  "warn_high": 1450},
        "nitrate":     {"min": 2,     "max": 15,    "warn_low": 0,     "warn_high": 30},
        "nitrite":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.1},
        "ammonia":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.1},
        "phosphate":   {"min": 0.01,  "max": 0.08,  "warn_low": 0,     "warn_high": 0.2},
        "temperature": {"min": 76,    "max": 79,    "warn_low": 74,    "warn_high": 82},
    },
    "sps": {
        "salinity":    {"min": 1.025, "max": 1.026, "warn_low": 1.023, "warn_high": 1.028},
        "ph":          {"min": 8.1,   "max": 8.4,   "warn_low": 7.9,   "warn_high": 8.5},
        "alkalinity":  {"min": 7.0,   "max": 8.5,   "warn_low": 6.0,   "warn_high": 10.0},
        "calcium":     {"min": 420,   "max": 450,   "warn_low": 380,   "warn_high": 480},
        "magnesium":   {"min": 1300,  "max": 1350,  "warn_low": 1250,  "warn_high": 1400},
        "nitrate":     {"min": 1,     "max": 5,     "warn_low": 0,     "warn_high": 15},
        "nitrite":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.05},
        "ammonia":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.05},
        "phosphate":   {"min": 0.01,  "max": 0.05,  "warn_low": 0,     "warn_high": 0.1},
        "temperature": {"min": 77,    "max": 79,    "warn_low": 75,    "warn_high": 81},
    },
    "mixed_reef": {
        "salinity":    {"min": 1.024, "max": 1.026, "warn_low": 1.022, "warn_high": 1.028},
        "ph":          {"min": 8.0,   "max": 8.4,   "warn_low": 7.8,   "warn_high": 8.5},
        "alkalinity":  {"min": 7.0,   "max": 11.0,  "warn_low": 6.0,   "warn_high": 13.0},
        "calcium":     {"min": 400,   "max": 450,   "warn_low": 350,   "warn_high": 500},
        "magnesium":   {"min": 1250,  "max": 1350,  "warn_low": 1200,  "warn_high": 1450},
        "nitrate":     {"min": 1,     "max": 10,    "warn_low": 0,     "warn_high": 25},
        "nitrite":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.1},
        "ammonia":     {"min": 0,     "max": 0,     "warn_low": 0,     "warn_high": 0.1},
        "phosphate":   {"min": 0.01,  "max": 0.08,  "warn_low": 0,     "warn_high": 0.2},
        "temperature": {"min": 76,    "max": 80,    "warn_low": 74,    "warn_high": 82},
    },
}

# Tank type display names
TANK_TYPES = {
    "fowlr": "Fish Only with Live Rock",
    "soft_coral": "Soft Coral Reef",
    "lps": "LPS Dominant Reef",
    "sps": "SPS Dominant Reef",
    "mixed_reef": "Mixed Reef",
}

# Equipment categories
EQUIPMENT_CATEGORIES = [
    "lighting", "filtration", "pump", "skimmer", "heater",
    "ato", "doser", "controller", "powerhead", "reactor", "other"
]

# Common 2-part dosing: ml of solution per dKH per gallon
# Based on BRS 2-part (soda ash + calcium chloride)
DOSING_DATA = {
    "brs_soda_ash": {
        "name": "BRS Soda Ash (Alk)",
        "ml_per_dkh_per_gallon": 1.0,
        "notes": "1 ml per gallon raises Alk by ~1 dKH"
    },
    "brs_calcium_chloride": {
        "name": "BRS Calcium Chloride (Ca)",
        "ml_per_ppm_per_gallon": 0.05,
        "notes": "1 ml per gallon raises Ca by ~20 ppm"
    },
}

# ── Reef Light Fixtures Database ─────────────────────────────────────────

REEF_LIGHTS = {
    "ai": {
        "brand": "Aqua Illumination",
        "models": {
            "prime_16_hd":  {"name": "Prime 16 HD",  "watts": 55},
            "hydra_32_hd":  {"name": "Hydra 32 HD",  "watts": 95},
            "hydra_64_hd":  {"name": "Hydra 64 HD",  "watts": 190},
            "blade":        {"name": "Blade",         "watts": 53},
        },
    },
    "ecotech": {
        "brand": "Ecotech Marine",
        "models": {
            "radion_xr15":     {"name": "Radion XR15 G5/G6", "watts": 95},
            "radion_xr30":     {"name": "Radion XR30 G5/G6", "watts": 190},
            "radion_diffuser": {"name": "Radion + Diffuser",  "watts": 190},
        },
    },
    "kessil": {
        "brand": "Kessil",
        "models": {
            "a80":    {"name": "A80 Tuna Sun",  "watts": 15},
            "a160":   {"name": "A160WE",        "watts": 40},
            "a360x":  {"name": "A360X",         "watts": 90},
            "a500x":  {"name": "A500X",         "watts": 185},
            "ap9x":   {"name": "AP9X",          "watts": 120},
        },
    },
    "red_sea": {
        "brand": "Red Sea",
        "models": {
            "reefl_50":   {"name": "ReefLED 50",   "watts": 50},
            "reefl_90":   {"name": "ReefLED 90",   "watts": 90},
            "reefl_160":  {"name": "ReefLED 160S",  "watts": 160},
        },
    },
    "orphek": {
        "brand": "Orphek",
        "models": {
            "atlantik_v4": {"name": "Atlantik V4",    "watts": 250},
            "or3_120":     {"name": "OR3 120",         "watts": 120},
            "or3_60":      {"name": "OR3 60",          "watts": 60},
        },
    },
    "maxspect": {
        "brand": "Maxspect",
        "models": {
            "jump_mj65":  {"name": "Jump MJ-L65",  "watts": 65},
            "jump_mj130": {"name": "Jump MJ-L130", "watts": 130},
            "recurve":    {"name": "Recurve",       "watts": 120},
            "rsx_r5_100": {"name": "RSX R5 100",    "watts": 100},
            "rsx_r5_200": {"name": "RSX R5 200",    "watts": 200},
        },
    },
    "nicrew": {
        "brand": "Nicrew",
        "models": {
            "hyperreef_50w":  {"name": "HyperReef 50W",  "watts": 50},
            "hyperreef_100w": {"name": "HyperReef 100W", "watts": 100},
            "hyperreef_150w": {"name": "HyperReef 150W", "watts": 150},
        },
    },
    "current_usa": {
        "brand": "Current USA",
        "models": {
            "orbit_marine_ic":   {"name": "Orbit Marine IC",    "watts": 46},
            "orbit_marine_pro":  {"name": "Orbit Marine IC Pro","watts": 72},
        },
    },
    "viparspectra": {
        "brand": "ViparSpectra",
        "models": {
            "165w": {"name": "165W LED",  "watts": 165},
            "300w": {"name": "300W LED",  "watts": 300},
        },
    },
    "ati": {
        "brand": "ATI (T5)",
        "models": {
            "sunpower_4x24":  {"name": "Sunpower 4x24W",  "watts": 96},
            "sunpower_4x39":  {"name": "Sunpower 4x39W",  "watts": 156},
            "sunpower_6x39":  {"name": "Sunpower 6x39W",  "watts": 234},
            "sunpower_8x39":  {"name": "Sunpower 8x39W",  "watts": 312},
            "sunpower_6x54":  {"name": "Sunpower 6x54W",  "watts": 324},
            "sunpower_8x54":  {"name": "Sunpower 8x54W",  "watts": 432},
        },
    },
    "other": {
        "brand": "Other / Custom",
        "models": {},
    },
}

# ── Cost Reference Data ─────────────────────────────────────────────────

SALT_PRICES = {
    "red_sea_coral_pro": {"bucket_kg": 22, "price": 75, "name": "Red Sea Coral Pro 22kg"},
    "red_sea_blue":      {"bucket_kg": 22, "price": 65, "name": "Red Sea Blue 22kg"},
    "instant_ocean":     {"bucket_kg": 23, "price": 38, "name": "Instant Ocean 200gal"},
    "instant_ocean_reef":{"bucket_kg": 23, "price": 52, "name": "IO Reef Crystals 200gal"},
    "fritz_rpm":         {"bucket_kg": 22, "price": 68, "name": "Fritz RPM 22kg"},
    "tropic_marin_pro":  {"bucket_kg": 20, "price": 85, "name": "Tropic Marin Pro 20kg"},
    "aquaforest_reef":   {"bucket_kg": 22, "price": 70, "name": "Aquaforest Reef 22kg"},
    "hw_reefer":         {"bucket_kg": 20, "price": 72, "name": "HW Reefer 20kg"},
    "brightwell_neomarine":{"bucket_kg": 23, "price": 78, "name": "Brightwell NeoMarine"},
    "kent_reef":         {"bucket_kg": 23, "price": 45, "name": "Kent Reef Salt 200gal"},
}

DOSING_PRICES = {
    "brs_2part":          {"cost_per_liter": 3.50,  "name": "BRS 2-Part"},
    "red_sea_foundation": {"cost_per_liter": 8.00,  "name": "Red Sea Foundation"},
    "brightwell":         {"cost_per_liter": 6.50,  "name": "Brightwell Aquatics"},
    "all_for_reef":       {"cost_per_liter": 12.00, "name": "All For Reef"},
    "kalkwasser":         {"cost_per_liter": 2.00,  "name": "Kalkwasser"},
    "esv_b_ionic":        {"cost_per_liter": 5.50,  "name": "ESV B-Ionic"},
}

FILTER_MEDIA_PRICES = {
    "carbon":       {"cost_per_use": 5.00,  "name": "Activated Carbon"},
    "gfo":          {"cost_per_use": 8.00,  "name": "GFO (Phosphate Remover)"},
    "filter_socks": {"cost_per_use": 2.50,  "name": "Filter Sock"},
}

RODI_COSTS = {
    "3_stage": {"annual_cost": 60,  "rated_gallons": 1000},
    "4_stage": {"annual_cost": 80,  "rated_gallons": 1500},
    "5_stage": {"annual_cost": 110, "rated_gallons": 2000},
    "6_stage": {"annual_cost": 140, "rated_gallons": 2500},
}

FOOD_PRICES = {
    "pellets": {"cost_per_feeding": 0.15, "name": "Pellets"},
    "frozen":  {"cost_per_feeding": 0.50, "name": "Frozen"},
    "combo":   {"cost_per_feeding": 0.35, "name": "Pellets + Frozen"},
}

DEFAULT_ELECTRICITY_RATE = 0.15  # $/kWh

# Average wattage by equipment type and tank size class (small < 40gal, medium 40-120, large > 120)
DEFAULT_EQUIPMENT_WATTAGE = {
    "led":           {"small": 50,  "medium": 150, "large": 300},
    "t5":            {"small": 80,  "medium": 160, "large": 320},
    "metal_halide":  {"small": 150, "medium": 250, "large": 500},
    "hybrid":        {"small": 100, "medium": 180, "large": 350},
    "heater":        {"small": 100, "medium": 200, "large": 300},
    "return_pump":   {"small": 20,  "medium": 40,  "large": 65},
    "powerhead":     {"default": 15},
    "skimmer":       {"small": 15,  "medium": 25,  "large": 50},
}

# Estimated daily dosing ml by tank type (for "not sure" answers)
DEFAULT_DOSING_ML = {
    "sps":        {"small": 30, "medium": 80,  "large": 150},
    "lps":        {"small": 15, "medium": 40,  "large": 80},
    "mixed_reef": {"small": 20, "medium": 55,  "large": 110},
    "soft_coral": {"small": 8,  "medium": 20,  "large": 40},
    "fowlr":      {"small": 0,  "medium": 0,   "large": 0},
}

EVAPORATION_RATE_PER_GALLON_PER_DAY = 0.01  # ~1% daily
