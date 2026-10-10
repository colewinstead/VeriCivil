from app_info import CALCULATION_ENGINE_VERSION
from criteria_info import (
    MDOT_PROFILE_ID,
    applicable_drawings_label,
    calculation_sources_label,
    criteria_for_result,
    criteria_metadata,
    normalize_profile_id,
)
import tdot_criteria
import re
import math


def parse_station(value: str) -> float:
    """
    Parse a station string (e.g., "10+50.25" or "1050.25") into feet.
    """
    value = value.strip()
    if "+" in value:
        left, right = value.split("+", 1)
        return float(left) * 100 + float(right)
    return float(value)


def format_station(feet: float, station_format: bool = True) -> str:
    """
    Format feet into a highway station string if requested.
    """
    if not station_format:
        return f"{feet:.3f} ft"
    hundreds = int(feet // 100)
    remainder = feet - hundreds * 100
    return f"{hundreds}+{remainder:06.3f}"


def normalize_station_equations(equations: list[dict] | None) -> list[dict[str, float]]:
    """Normalize LandXML/manual station equations to internal/back/ahead feet."""
    normalized: list[dict[str, float]] = []
    for equation in equations or []:
        try:
            back = float(equation.get("staBack", equation.get("back", "")))
            ahead = float(equation.get("staAhead", equation.get("ahead", "")))
            internal = float(equation.get("staInternal", equation.get("internal", back)))
        except (TypeError, ValueError):
            continue
        normalized.append({"internal": internal, "back": back, "ahead": ahead})
    return sorted(normalized, key=lambda item: item["internal"])


def civil_to_internal_station(
    station: float, equations: list[dict] | None, station_range: tuple[float, float] | None = None,
    station_region: int | None = None,
) -> float:
    """Convert displayed civil stationing to continuous alignment chainage."""
    candidates: list[float] = []
    prior_internal = float("-inf")
    prior_offset = 0.0
    normalized=normalize_station_equations(equations)
    for region,equation in enumerate(normalized,1):
        candidate = station - prior_offset
        if prior_internal <= candidate <= equation["internal"] and station_region in (None,region):
            candidates.append(candidate)
        prior_internal = equation["internal"]
        prior_offset = equation["ahead"] - equation["internal"]
    candidate = station - prior_offset
    if candidate >= prior_internal and station_region in (None,len(normalized)+1):
        candidates.append(candidate)
    if station_range is not None:
        start, end = station_range
        candidates = [candidate for candidate in candidates if start - 1e-6 <= candidate <= end + 1e-6]
    if not candidates:
        raise ValueError(f"Station {format_station(station)} cannot be mapped through the station equation.")
    candidates=list(dict.fromkeys(candidates))
    if len(candidates) > 1:
        raise ValueError(
            f"Station {format_station(station)} occurs on more than one side of a station equation. "
            "Use a station region (R1, R2, …) or a narrower internal alignment range to identify the correct location."
        )
    return candidates[0]


def strict_station_equations(equations: list[dict] | None) -> list[dict]:
    """Validate new-model stationing; derive manual internal stations cumulatively."""
    result=[]
    offset=0.0
    for equation in equations or []:
        try:
            back=float(equation.get("staBack",equation.get("back")))
            ahead=float(equation.get("staAhead",equation.get("ahead")))
            internal=float(equation.get("staInternal",equation.get("internal",back-offset)))
        except (ValueError,TypeError,AttributeError) as exc:
            raise ValueError("Station equations require finite back, ahead, and internal station definitions.") from exc
        if not all(math.isfinite(n) for n in (back,ahead,internal)) or abs(back-internal-offset)>1e-5:
            raise ValueError("Station equation back station is inconsistent with continuous internal stationing.")
        if result and internal<=result[-1]["internal"]:
            raise ValueError("Station equation internal stations must be strictly increasing.")
        result.append({"internal":internal,"back":back,"ahead":ahead})
        offset=ahead-internal
    return result


def parse_station_reference(text: str, equations=None, station_range=None) -> float:
    """An explicit ORD region resolves repeated station labels."""
    match=re.fullmatch(r"(.*?)\s*[Rr](\d+)",str(text).strip())
    region=int(match[2]) if match else None
    return civil_to_internal_station(parse_station(match[1] if match else str(text)),equations,station_range,region)


def station_input_label(station: float, equations=None, station_range=None) -> str:
    civil=internal_to_civil_station(station,equations)
    label=format_station(civil,True)
    try:
        civil_to_internal_station(civil,equations,station_range)
    except ValueError:
        region=1+sum(station>=e["internal"] for e in normalize_station_equations(equations))
        return f"{label}R{region}"
    return label


def internal_to_civil_station(station: float, equations: list[dict] | None) -> float:
    civil = station
    for equation in normalize_station_equations(equations):
        if station >= equation["internal"]:
            civil = station + equation["ahead"] - equation["internal"]
        else:
            break
    return civil


def format_result_station(results: dict, station: float | None, station_format: bool = True) -> str:
    if station is None:
        return "n/a"
    if station_format and results.get("transition_method")=="aashto_fixed_pivot":
        return station_input_label(float(station),results.get("station_equations"),results.get("alignment_station_range"))
    return format_station(internal_to_civil_station(float(station), results.get("station_equations")), station_format)


def compute_superelevation_rate(
    speed_mph: float,
    radius_ft: float,
    e_manual: float | None,
    side_friction: float,
    e_max: float,
) -> tuple[float, str | None]:
    """
    Compute superelevation rate e (ft/ft).
    - If a manual value is provided, use it.
    - Otherwise, use a simple AASHTO-style balance: e = V^2/(15R) - f,
      capped at 0.10 per the MDOT standard sheet.
    """
    if e_manual is not None:
        return e_manual, None

    e_req = (speed_mph ** 2) / (15 * radius_ft) - side_friction
    note = None
    if e_req <= 0:
        note = "Computed e <= 0; clamped to 0. Adjust side friction if needed."
    return max(0.0, min(e_max, e_req)), note


def relative_gradient_from_speed(speed_mph: float) -> float:
    """
    Use AASHTO-style Table 3-4-C maximum relative gradients (percent).
    Returns ft/ft. Linear interpolation between table speeds.
    """
    table = {
        30: 0.66,
        35: 0.62,
        40: 0.58,
        45: 0.54,
        50: 0.50,
        55: 0.47,
        60: 0.45,
        65: 0.43,
        70: 0.40,
    }
    speeds = sorted(table.keys())
    if speed_mph <= speeds[0]:
        return table[speeds[0]] / 100.0
    if speed_mph >= speeds[-1]:
        return table[speeds[-1]] / 100.0
    for i in range(len(speeds) - 1):
        s0, s1 = speeds[i], speeds[i + 1]
        if s0 <= speed_mph <= s1:
            g0, g1 = table[s0], table[s1]
            t = (speed_mph - s0) / (s1 - s0)
            return (g0 + (g1 - g0) * t) / 100.0
    return table[speeds[-1]] / 100.0


def parse_relative_gradient(value: str, speed_mph: float) -> tuple[float, str | None]:
    """
    Parse relative gradient input; blank uses Table 3-4-C by speed.
    Accepts percent values (e.g., 0.43) or ft/ft (e.g., 0.0043).
    """
    if not value:
        g = relative_gradient_from_speed(speed_mph)
        return g, "Using Table 3-4-C by design speed."
    raw = float(value)
    if raw > 0.1:
        return raw / 100.0, "Interpreted input as percent."
    return raw, None


RURAL_SUPER_SPEEDS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
RURAL_SUPER_TABLE = {
    "NC": [947, 1680, 2420, 3320, 4350, 5520, 6830, 8280, 9890, 11700, 13100, 14700, 16300, 18000],
    "RC": [694, 1230, 1780, 2440, 3210, 4080, 5050, 6130, 7330, 8630, 9720, 10900, 12200, 13500],
    2.2: [625, 1110, 1600, 2200, 2900, 3680, 4570, 5540, 6630, 7810, 8800, 9860, 11000, 12200],
    2.4: [567, 1010, 1460, 2000, 2640, 3350, 4160, 5050, 6050, 7130, 8040, 9010, 10100, 11200],
    2.6: [517, 916, 1330, 1840, 2420, 3080, 3820, 4640, 5550, 6550, 7390, 8290, 9260, 10300],
    2.8: [475, 841, 1230, 1690, 2230, 2840, 3520, 4280, 5130, 6050, 6840, 7680, 8580, 9550],
    3.0: [438, 777, 1140, 1570, 2060, 2630, 3270, 3970, 4760, 5620, 6360, 7140, 7990, 8900],
    3.2: [406, 720, 1050, 1450, 1920, 2450, 3040, 3700, 4440, 5250, 5930, 6680, 7480, 8330],
    3.4: [377, 670, 978, 1360, 1790, 2290, 2850, 3470, 4160, 4910, 5560, 6260, 7020, 7830],
    3.6: [352, 625, 913, 1270, 1680, 2150, 2670, 3250, 3900, 4620, 5230, 5900, 6620, 7390],
    3.8: [329, 584, 856, 1190, 1580, 2020, 2510, 3060, 3680, 4350, 4940, 5570, 6260, 6990],
    4.0: [308, 547, 804, 1120, 1490, 1900, 2370, 2890, 3470, 4110, 4670, 5270, 5930, 6630],
    4.2: [289, 514, 756, 1060, 1400, 1800, 2240, 2740, 3290, 3900, 4430, 5010, 5630, 6300],
    4.4: [271, 483, 713, 994, 1330, 1700, 2120, 2590, 3120, 3700, 4210, 4760, 5370, 6010],
    4.6: [255, 455, 673, 940, 1260, 1610, 2020, 2460, 2970, 3520, 4010, 4540, 5120, 5740],
    4.8: [240, 429, 636, 890, 1190, 1530, 1920, 2340, 2830, 3360, 3830, 4340, 4900, 5490],
    5.0: [226, 404, 601, 844, 1130, 1460, 1830, 2240, 2700, 3200, 3660, 4150, 4690, 5270],
    5.2: [213, 381, 569, 802, 1080, 1390, 1740, 2130, 2580, 3060, 3500, 3980, 4500, 5060],
    5.4: [200, 359, 539, 762, 1030, 1330, 1660, 2040, 2460, 2930, 3360, 3820, 4320, 4860],
    5.6: [188, 339, 511, 724, 974, 1270, 1590, 1950, 2360, 2810, 3220, 3670, 4160, 4680],
    5.8: [176, 319, 484, 689, 929, 1210, 1520, 1870, 2260, 2700, 3090, 3530, 4000, 4510],
    6.0: [164, 299, 458, 656, 886, 1160, 1460, 1790, 2170, 2590, 2980, 3400, 3860, 4360],
    6.2: [152, 280, 433, 624, 846, 1110, 1400, 1720, 2090, 2490, 2870, 3280, 3730, 4210],
    6.4: [140, 260, 409, 594, 808, 1060, 1340, 1650, 2010, 2400, 2760, 3160, 3600, 4070],
    6.6: [130, 242, 386, 564, 772, 1020, 1290, 1590, 1930, 2310, 2670, 3060, 3480, 3940],
    6.8: [120, 226, 363, 536, 737, 971, 1230, 1530, 1860, 2230, 2570, 2960, 3370, 3820],
    7.0: [112, 212, 343, 509, 704, 931, 1190, 1470, 1790, 2150, 2490, 2860, 3270, 3710],
    7.2: [105, 199, 324, 483, 671, 892, 1140, 1410, 1730, 2070, 2410, 2770, 3170, 3600],
    7.4: [98, 187, 306, 460, 641, 855, 1100, 1360, 1670, 2000, 2330, 2680, 3070, 3500],
    7.6: [92, 176, 290, 437, 612, 820, 1050, 1310, 1610, 1940, 2250, 2600, 2990, 3400],
    7.8: [86, 165, 274, 416, 585, 786, 1010, 1260, 1550, 1870, 2180, 2530, 2900, 3310],
    8.0: [81, 156, 260, 396, 558, 754, 968, 1220, 1500, 1810, 2120, 2450, 2820, 3220],
    8.2: [76, 147, 246, 377, 533, 722, 930, 1170, 1440, 1750, 2050, 2380, 2750, 3140],
    8.4: [72, 139, 234, 359, 509, 692, 893, 1130, 1390, 1690, 1990, 2320, 2670, 3060],
    8.6: [68, 131, 221, 341, 486, 662, 856, 1080, 1340, 1630, 1930, 2250, 2600, 2980],
    8.8: [64, 124, 209, 324, 463, 633, 820, 1040, 1290, 1570, 1870, 2190, 2540, 2910],
    9.0: [60, 116, 198, 307, 440, 604, 784, 992, 1240, 1520, 1810, 2130, 2470, 2840],
    9.2: [56, 109, 186, 291, 418, 574, 748, 948, 1190, 1460, 1740, 2060, 2410, 2770],
    9.4: [52, 102, 175, 274, 395, 545, 710, 903, 1130, 1390, 1670, 1990, 2340, 2710],
    9.6: [48, 95, 163, 256, 370, 513, 671, 854, 1080, 1320, 1600, 1910, 2260, 2640],
    9.8: [44, 87, 150, 236, 343, 477, 625, 798, 1010, 1250, 1510, 1820, 2160, 2550],
    10.0: [36, 72, 126, 200, 292, 410, 540, 694, 877, 1090, 1340, 1630, 1970, 2370],
}


LOCAL_SUPER_SPEEDS = [30, 35, 40, 45]
LOCAL_SUPER_TABLE = {
    "NC": [3130, 4100, 5230, 6480],
    "RC": [2240, 2950, 3770, 4680],
    0.022: [2000, 2630, 3370, 4190],
    0.024: [1790, 2360, 3030, 3770],
    0.026: [1610, 2130, 2740, 3420],
    0.028: [1460, 1930, 2490, 3110],
    0.030: [1320, 1760, 2270, 2840],
    0.032: [1200, 1600, 2080, 2600],
    0.034: [1080, 1460, 1900, 2390],
    0.036: [972, 1320, 1740, 2190],
    0.038: [864, 1190, 1590, 2010],
    0.040: [766, 1070, 1440, 1840],
    0.042: [684, 960, 1310, 1680],
    0.044: [615, 868, 1190, 1540],
    0.046: [555, 788, 1090, 1410],
    0.048: [502, 718, 995, 1300],
    0.050: [456, 654, 911, 1190],
    0.052: [413, 595, 833, 1090],
    0.054: [373, 540, 759, 995],
    0.056: [335, 487, 687, 903],
    0.058: [296, 431, 611, 806],
    0.060: [231, 340, 485, 643],
}

EXTRA_WIDTH_TABLE = {
    5500: {20: {45: 2.0}},
    5000: {20: {40: 2.0, 45: 2.1}},
    4500: {20: {35: 2.0, 40: 2.1, 45: 2.1}},
    4000: {20: {30: 2.0, 40: 2.2, 45: 2.2}},
    3500: {20: {35: 2.2, 40: 2.3, 45: 2.4}},
    3000: {20: {30: 2.3, 35: 2.4, 40: 2.4, 45: 2.5}},
    2500: {20: {30: 2.5, 35: 2.6, 40: 2.7, 45: 2.8}},
    2000: {22: {40: 2.0, 45: 2.1}, 20: {30: 2.7, 35: 2.9, 40: 3.0, 45: 3.1}},
    1800: {22: {35: 2.0, 40: 2.1, 45: 2.3}, 20: {30: 2.9, 35: 3.0, 40: 3.1, 45: 3.3}},
    1600: {22: {35: 2.2, 40: 2.3, 45: 2.5}, 20: {35: 3.2, 40: 3.3, 45: 3.5}},
    1400: {
        22: {30: 2.3, 35: 2.5, 40: 2.6, 45: 2.7},
        20: {30: 3.3, 35: 3.5, 40: 3.6, 45: 3.7},
    },
    1200: {
        24: {45: 2.1},
        22: {30: 2.7, 35: 2.8, 40: 2.9, 45: 3.1},
        20: {30: 3.7, 35: 3.8, 40: 3.9, 45: 4.1},
    },
    1000: {
        24: {35: 2.3, 40: 2.4, 45: 2.6},
        22: {35: 3.3, 40: 3.4, 45: 3.6},
        20: {35: 4.3, 40: 4.4, 45: 4.6},
    },
    900: {
        24: {30: 2.4, 35: 2.6, 40: 2.7, 45: 2.9},
        22: {30: 3.4, 35: 3.6, 40: 3.7, 45: 3.9},
        20: {30: 4.4, 35: 4.6, 40: 4.7, 45: 4.9},
    },
    800: {
        24: {30: 2.7, 35: 2.9, 40: 3.1, 45: 3.3},
        22: {30: 3.7, 35: 3.9, 40: 4.1, 45: 4.3},
        20: {30: 4.7, 35: 4.9, 40: 5.1, 45: 5.3},
    },
    700: {
        24: {30: 3.2, 35: 3.4, 40: 3.6, 45: 3.8},
        22: {30: 4.2, 35: 4.4, 40: 4.6, 45: 4.8},
        20: {30: 5.2, 35: 5.4, 40: 5.6, 45: 5.8},
    },
    600: {
        24: {30: 3.8, 35: 4.0, 40: 4.2, 45: 4.4},
        22: {30: 4.8, 35: 5.0, 40: 5.2, 45: 5.4},
        20: {30: 5.8, 35: 6.0, 40: 6.2, 45: 6.4},
    },
    500: {
        24: {30: 4.6, 35: 4.9, 40: 5.1, 45: 5.3},
        22: {30: 5.6, 35: 5.9, 40: 6.1, 45: 6.3},
        20: {30: 6.6, 35: 6.9, 40: 7.1, 45: 7.3},
    },
    450: {
        24: {30: 5.2, 35: 5.4, 40: 5.7},
        22: {30: 6.2, 35: 6.4, 40: 6.7},
        20: {30: 7.2, 35: 7.4, 40: 7.7},
    },
    400: {
        24: {30: 5.9, 35: 6.1, 40: 6.4},
        22: {30: 6.9, 35: 7.1, 40: 7.4},
        20: {30: 7.9, 40: 8.4},
    },
    350: {
        24: {30: 6.8, 35: 7.0, 40: 7.3},
        22: {30: 7.8, 35: 8.0, 40: 8.3},
        20: {30: 8.8, 35: 9.0, 40: 9.3},
    },
    300: {
        24: {30: 7.9, 35: 8.2},
        22: {30: 8.9, 35: 9.2},
        20: {30: 9.9, 35: 10.2},
    },
    250: {24: {30: 9.6}, 22: {30: 10.6}, 20: {30: 11.6}},
    200: {24: {30: 12.0}, 22: {30: 13.0}, 20: {30: 14.0}},
}


def interpolate_by_speed(speeds: list[int], values: list[int], speed_mph: float) -> tuple[float, str | None]:
    if speed_mph <= speeds[0]:
        return float(values[0]), "Using minimum speed row."
    if speed_mph >= speeds[-1]:
        return float(values[-1]), "Using maximum speed row."
    for i in range(len(speeds) - 1):
        s0, s1 = speeds[i], speeds[i + 1]
        if s0 <= speed_mph <= s1:
            v0, v1 = values[i], values[i + 1]
            t = (speed_mph - s0) / (s1 - s0)
            return v0 + (v1 - v0) * t, "Interpolated by speed."
    return float(values[-1]), None


def rural_table_superelevation(speed_mph: float, radius_ft: float) -> tuple[float, str, str | None]:
    r_nc, nc_note = interpolate_by_speed(
        RURAL_SUPER_SPEEDS, RURAL_SUPER_TABLE["NC"], speed_mph
    )
    r_rc, rc_note = interpolate_by_speed(
        RURAL_SUPER_SPEEDS, RURAL_SUPER_TABLE["RC"], speed_mph
    )
    if radius_ft >= r_nc:
        note = nc_note or "Normal crown applies."
        return 0.0, "Normal crown", note
    if radius_ft >= r_rc:
        note = rc_note or "Reverse crown applies."
        return 0.0, "Reverse crown", note

    e_rows = sorted(k for k in RURAL_SUPER_TABLE.keys() if isinstance(k, float))
    for e_percent in e_rows:
        r_min, _ = interpolate_by_speed(
            RURAL_SUPER_SPEEDS, RURAL_SUPER_TABLE[e_percent], speed_mph
        )
        if radius_ft >= r_min:
            return e_percent / 100.0, "Superelevation (table)", None
    return e_rows[-1] / 100.0, "Superelevation (table, min radius exceeded)", None


def local_table_superelevation(speed_mph: float, radius_ft: float) -> tuple[float, str, str | None]:
    speed_key = min(LOCAL_SUPER_SPEEDS, key=lambda s: abs(s - speed_mph))
    note = None
    if speed_key != speed_mph:
        note = f"Using {speed_key} mph row for {speed_mph} mph."

    idx = LOCAL_SUPER_SPEEDS.index(speed_key)
    r_nc = LOCAL_SUPER_TABLE["NC"][idx]
    r_rc = LOCAL_SUPER_TABLE["RC"][idx]
    if radius_ft >= r_nc:
        return 0.0, "Normal crown", note or "Normal crown applies."
    if radius_ft >= r_rc:
        return 0.0, "Reverse crown", note or "Reverse crown applies."

    e_rows = sorted(k for k in LOCAL_SUPER_TABLE.keys() if isinstance(k, float))
    for e_val in e_rows:
        r_min = LOCAL_SUPER_TABLE[e_val][idx]
        if radius_ft >= r_min:
            return e_val, "Superelevation (local table)", note
    return e_rows[-1], "Superelevation (local table, min radius exceeded)", note


def local_extra_width(
    speed_mph: float,
    radius_ft: float,
    lane_width_ft: float,
) -> tuple[float, str | None]:
    width_options = [20, 22, 24]
    traveled_width = lane_width_ft * 2.0
    width_key = min(width_options, key=lambda w: abs(w - traveled_width))
    note_parts = []
    if abs(width_key - traveled_width) > 0.01:
        note_parts.append(f"Using {width_key} ft traveled way for {traveled_width:.1f} ft input.")

    speed_key = min(LOCAL_SUPER_SPEEDS, key=lambda s: abs(s - speed_mph))
    if speed_key != speed_mph:
        note_parts.append(f"Using {speed_key} mph extra width column for {speed_mph} mph.")

    available_radii = [
        r for r, row in EXTRA_WIDTH_TABLE.items()
        if width_key in row and speed_key in row[width_key]
    ]
    if not available_radii:
        return 0.0, None

    max_radius = max(available_radii)
    if radius_ft > max_radius:
        return 0.0, None

    radius_key = max([r for r in available_radii if r <= radius_ft], default=min(available_radii))
    if radius_key != radius_ft:
        note_parts.append(f"Using R={radius_key} ft row for R={radius_ft:.0f} ft.")

    extra_width = float(EXTRA_WIDTH_TABLE[radius_key][width_key][speed_key])
    if extra_width <= 0:
        return 0.0, None
    return extra_width, "; ".join(note_parts) if note_parts else None


URBAN_CENTERLINE_V50_TABLE = {
    "NC": {"r": 7870, "L_A": 0, "L_B": 0},
    "RC": {"r": 5700, "L_A": 48, "L_B": 72},
    0.022: {"r": 5100, "L_A": 53, "L_B": 79},
    0.024: {"r": 4600, "L_A": 58, "L_B": 86},
    0.026: {"r": 4170, "L_A": 62, "L_B": 94},
    0.028: {"r": 3800, "L_A": 67, "L_B": 101},
    0.030: {"r": 3480, "L_A": 72, "L_B": 108},
    0.032: {"r": 3200, "L_A": 77, "L_B": 115},
    0.034: {"r": 2940, "L_A": 82, "L_B": 122},
    0.036: {"r": 2710, "L_A": 86, "L_B": 130},
    0.038: {"r": 2490, "L_A": 91, "L_B": 137},
    0.040: {"r": 2300, "L_A": 96, "L_B": 144},
    0.042: {"r": 2110, "L_A": 101, "L_B": 151},
    0.044: {"r": 1940, "L_A": 106, "L_B": 158},
    0.046: {"r": 1780, "L_A": 110, "L_B": 166},
    0.048: {"r": 1640, "L_A": 115, "L_B": 173},
    0.050: {"r": 1510, "L_A": 120, "L_B": 180},
    0.052: {"r": 1390, "L_A": 125, "L_B": 187},
    0.054: {"r": 1280, "L_A": 130, "L_B": 194},
    0.056: {"r": 1160, "L_A": 134, "L_B": 202},
    0.058: {"r": 1040, "L_A": 139, "L_B": 209},
    0.060: {"r": 833, "L_A": 144, "L_B": 216},
}


URBAN_EDGE_V50_TABLE = {
    "NC": {"r": 7870, "L_A": 0, "L_B": 0},
    "RC": {"r": 5700, "L_A": 48, "L_B": 72},
    0.022: {"r": 5100, "L_A": 53, "L_B": 79},
    0.024: {"r": 4600, "L_A": 58, "L_B": 86},
    0.026: {"r": 4170, "L_A": 62, "L_B": 94},
    0.028: {"r": 3800, "L_A": 67, "L_B": 101},
    0.030: {"r": 3480, "L_A": 72, "L_B": 108},
    0.032: {"r": 3200, "L_A": 77, "L_B": 115},
    0.034: {"r": 2940, "L_A": 82, "L_B": 122},
    0.036: {"r": 2710, "L_A": 86, "L_B": 130},
    0.038: {"r": 2490, "L_A": 91, "L_B": 137},
    0.040: {"r": 2300, "L_A": 96, "L_B": 144},
    0.042: {"r": 2110, "L_A": 101, "L_B": 151},
    0.044: {"r": 1940, "L_A": 106, "L_B": 158},
    0.046: {"r": 1780, "L_A": 110, "L_B": 166},
    0.048: {"r": 1640, "L_A": 115, "L_B": 173},
    0.050: {"r": 1510, "L_A": 120, "L_B": 180},
    0.052: {"r": 1390, "L_A": 125, "L_B": 187},
    0.054: {"r": 1280, "L_A": 130, "L_B": 194},
    0.056: {"r": 1160, "L_A": 134, "L_B": 202},
    0.058: {"r": 1040, "L_A": 139, "L_B": 209},
    0.060: {"r": 833, "L_A": 144, "L_B": 216},
}


URBAN_CENTERLINE_LE45_SPEEDS = [20, 25, 30, 35, 40, 45]
URBAN_CENTERLINE_LE45_TABLE = {
    20: {
        "NC": {"r": 1410, "L_A": 0, "L_B": 0},
        "RC": {"r": 902, "L_A": 32, "L_B": 49},
        0.022: {"r": 723, "L_A": 36, "L_B": 54},
        0.024: {"r": 513, "L_A": 39, "L_B": 58},
        0.026: {"r": 388, "L_A": 42, "L_B": 63},
        0.028: {"r": 308, "L_A": 45, "L_B": 68},
        0.030: {"r": 251, "L_A": 49, "L_B": 73},
        0.032: {"r": 209, "L_A": 52, "L_B": 78},
        0.034: {"r": 175, "L_A": 55, "L_B": 83},
        0.036: {"r": 147, "L_A": 58, "L_B": 88},
        0.038: {"r": 122, "L_A": 62, "L_B": 92},
        0.040: {"r": 86, "L_A": 65, "L_B": 97},
    },
    25: {
        "NC": {"r": 2050, "L_A": 0, "L_B": 0},
        "RC": {"r": 1340, "L_A": 34, "L_B": 51},
        0.022: {"r": 1110, "L_A": 38, "L_B": 57},
        0.024: {"r": 838, "L_A": 41, "L_B": 62},
        0.026: {"r": 650, "L_A": 45, "L_B": 67},
        0.028: {"r": 524, "L_A": 48, "L_B": 72},
        0.030: {"r": 433, "L_A": 51, "L_B": 77},
        0.032: {"r": 363, "L_A": 55, "L_B": 82},
        0.034: {"r": 307, "L_A": 58, "L_B": 87},
        0.036: {"r": 259, "L_A": 62, "L_B": 93},
        0.038: {"r": 215, "L_A": 65, "L_B": 98},
        0.040: {"r": 154, "L_A": 69, "L_B": 103},
    },
    30: {
        "NC": {"r": 2830, "L_A": 0, "L_B": 0},
        "RC": {"r": 1880, "L_A": 36, "L_B": 55},
        0.022: {"r": 1580, "L_A": 40, "L_B": 60},
        0.024: {"r": 1270, "L_A": 44, "L_B": 65},
        0.026: {"r": 1000, "L_A": 47, "L_B": 71},
        0.028: {"r": 817, "L_A": 51, "L_B": 76},
        0.030: {"r": 681, "L_A": 55, "L_B": 82},
        0.032: {"r": 576, "L_A": 58, "L_B": 87},
        0.034: {"r": 490, "L_A": 62, "L_B": 93},
        0.036: {"r": 416, "L_A": 65, "L_B": 98},
        0.038: {"r": 348, "L_A": 69, "L_B": 104},
        0.040: {"r": 250, "L_A": 73, "L_B": 109},
    },
    35: {
        "NC": {"r": 3730, "L_A": 0, "L_B": 0},
        "RC": {"r": 2490, "L_A": 39, "L_B": 58},
        0.022: {"r": 2120, "L_A": 43, "L_B": 64},
        0.024: {"r": 1760, "L_A": 46, "L_B": 70},
        0.026: {"r": 1420, "L_A": 50, "L_B": 75},
        0.028: {"r": 1170, "L_A": 54, "L_B": 81},
        0.030: {"r": 982, "L_A": 58, "L_B": 87},
        0.032: {"r": 835, "L_A": 62, "L_B": 93},
        0.034: {"r": 714, "L_A": 66, "L_B": 99},
        0.036: {"r": 610, "L_A": 70, "L_B": 105},
        0.038: {"r": 512, "L_A": 74, "L_B": 110},
        0.040: {"r": 371, "L_A": 77, "L_B": 116},
    },
    40: {
        "NC": {"r": 4770, "L_A": 0, "L_B": 0},
        "RC": {"r": 3220, "L_A": 41, "L_B": 62},
        0.022: {"r": 2760, "L_A": 46, "L_B": 68},
        0.024: {"r": 2340, "L_A": 50, "L_B": 74},
        0.026: {"r": 1930, "L_A": 54, "L_B": 81},
        0.028: {"r": 1620, "L_A": 58, "L_B": 87},
        0.030: {"r": 1370, "L_A": 62, "L_B": 93},
        0.032: {"r": 1180, "L_A": 66, "L_B": 99},
        0.034: {"r": 1010, "L_A": 70, "L_B": 106},
        0.036: {"r": 865, "L_A": 74, "L_B": 112},
        0.038: {"r": 730, "L_A": 79, "L_B": 118},
        0.040: {"r": 533, "L_A": 83, "L_B": 124},
    },
    45: {
        "NC": {"r": 5930, "L_A": 0, "L_B": 0},
        "RC": {"r": 4040, "L_A": 44, "L_B": 67},
        0.022: {"r": 3480, "L_A": 49, "L_B": 73},
        0.024: {"r": 2980, "L_A": 53, "L_B": 80},
        0.026: {"r": 2490, "L_A": 58, "L_B": 87},
        0.028: {"r": 2100, "L_A": 62, "L_B": 93},
        0.030: {"r": 1800, "L_A": 67, "L_B": 100},
        0.032: {"r": 1550, "L_A": 71, "L_B": 107},
        0.034: {"r": 1340, "L_A": 76, "L_B": 113},
        0.036: {"r": 1150, "L_A": 80, "L_B": 120},
        0.038: {"r": 970, "L_A": 84, "L_B": 127},
        0.040: {"r": 711, "L_A": 89, "L_B": 133},
    },
}

URBAN_CENTERLINE_LE45_LT = {
    20: {"A": 32, "B": 49},
    25: {"A": 34, "B": 51},
    30: {"A": 36, "B": 55},
    35: {"A": 39, "B": 58},
    40: {"A": 41, "B": 62},
    45: {"A": 44, "B": 67},
}

RURAL_CENTERLINE_RUNOFF_TABLE = {
    "RC": {
        30: {"A": 36, "B": 55},
        35: {"A": 39, "B": 58},
        40: {"A": 41, "B": 62},
        45: {"A": 44, "B": 67},
        50: {"A": 48, "B": 72},
        55: {"A": 51, "B": 77},
        60: {"A": 53, "B": 80},
        65: {"A": 56, "B": 84},
        70: {"A": 60, "B": 90},
    },
    0.022: {
        30: {"A": 40, "B": 60},
        35: {"A": 43, "B": 64},
        40: {"A": 46, "B": 68},
        45: {"A": 49, "B": 73},
        50: {"A": 53, "B": 79},
        55: {"A": 56, "B": 84},
        60: {"A": 59, "B": 88},
        65: {"A": 61, "B": 92},
        70: {"A": 66, "B": 99},
    },
    0.024: {
        30: {"A": 44, "B": 65},
        35: {"A": 46, "B": 70},
        40: {"A": 50, "B": 74},
        45: {"A": 53, "B": 80},
        50: {"A": 58, "B": 86},
        55: {"A": 61, "B": 92},
        60: {"A": 64, "B": 96},
        65: {"A": 67, "B": 100},
        70: {"A": 72, "B": 108},
    },
    0.026: {
        30: {"A": 47, "B": 71},
        35: {"A": 50, "B": 75},
        40: {"A": 54, "B": 81},
        45: {"A": 58, "B": 87},
        50: {"A": 62, "B": 94},
        55: {"A": 66, "B": 100},
        60: {"A": 69, "B": 104},
        65: {"A": 73, "B": 109},
        70: {"A": 78, "B": 117},
    },
    0.028: {
        30: {"A": 51, "B": 76},
        35: {"A": 54, "B": 81},
        40: {"A": 58, "B": 87},
        45: {"A": 62, "B": 93},
        50: {"A": 67, "B": 101},
        55: {"A": 71, "B": 107},
        60: {"A": 75, "B": 112},
        65: {"A": 78, "B": 117},
        70: {"A": 84, "B": 126},
    },
    0.030: {
        30: {"A": 55, "B": 82},
        35: {"A": 58, "B": 87},
        40: {"A": 62, "B": 93},
        45: {"A": 67, "B": 100},
        50: {"A": 72, "B": 108},
        55: {"A": 77, "B": 115},
        60: {"A": 80, "B": 120},
        65: {"A": 84, "B": 126},
        70: {"A": 90, "B": 135},
    },
    0.032: {
        30: {"A": 58, "B": 87},
        35: {"A": 62, "B": 93},
        40: {"A": 66, "B": 99},
        45: {"A": 71, "B": 107},
        50: {"A": 77, "B": 115},
        55: {"A": 82, "B": 123},
        60: {"A": 85, "B": 128},
        65: {"A": 89, "B": 134},
        70: {"A": 96, "B": 144},
    },
    0.034: {
        30: {"A": 62, "B": 93},
        35: {"A": 66, "B": 99},
        40: {"A": 70, "B": 106},
        45: {"A": 76, "B": 113},
        50: {"A": 82, "B": 122},
        55: {"A": 87, "B": 130},
        60: {"A": 91, "B": 136},
        65: {"A": 95, "B": 142},
        70: {"A": 102, "B": 153},
    },
    0.036: {
        30: {"A": 65, "B": 98},
        35: {"A": 70, "B": 105},
        40: {"A": 74, "B": 112},
        45: {"A": 80, "B": 120},
        50: {"A": 86, "B": 130},
        55: {"A": 92, "B": 138},
        60: {"A": 96, "B": 144},
        65: {"A": 100, "B": 151},
        70: {"A": 108, "B": 162},
    },
    0.038: {
        30: {"A": 69, "B": 104},
        35: {"A": 74, "B": 110},
        40: {"A": 79, "B": 118},
        45: {"A": 84, "B": 127},
        50: {"A": 91, "B": 137},
        55: {"A": 97, "B": 146},
        60: {"A": 101, "B": 152},
        65: {"A": 106, "B": 159},
        70: {"A": 114, "B": 171},
    },
    0.040: {
        30: {"A": 73, "B": 109},
        35: {"A": 77, "B": 116},
        40: {"A": 83, "B": 124},
        45: {"A": 89, "B": 133},
        50: {"A": 96, "B": 144},
        55: {"A": 102, "B": 153},
        60: {"A": 107, "B": 160},
        65: {"A": 112, "B": 167},
        70: {"A": 120, "B": 180},
    },
    0.042: {
        30: {"A": 76, "B": 115},
        35: {"A": 81, "B": 122},
        40: {"A": 87, "B": 130},
        45: {"A": 93, "B": 140},
        50: {"A": 101, "B": 151},
        55: {"A": 107, "B": 161},
        60: {"A": 112, "B": 168},
        65: {"A": 117, "B": 176},
        70: {"A": 126, "B": 189},
    },
    0.044: {
        30: {"A": 80, "B": 120},
        35: {"A": 85, "B": 128},
        40: {"A": 91, "B": 137},
        45: {"A": 98, "B": 147},
        50: {"A": 106, "B": 158},
        55: {"A": 112, "B": 169},
        60: {"A": 117, "B": 176},
        65: {"A": 123, "B": 184},
        70: {"A": 132, "B": 198},
    },
    0.046: {
        30: {"A": 84, "B": 125},
        35: {"A": 89, "B": 134},
        40: {"A": 95, "B": 143},
        45: {"A": 102, "B": 153},
        50: {"A": 110, "B": 166},
        55: {"A": 117, "B": 176},
        60: {"A": 123, "B": 184},
        65: {"A": 128, "B": 193},
        70: {"A": 138, "B": 207},
    },
    0.048: {
        30: {"A": 87, "B": 131},
        35: {"A": 93, "B": 139},
        40: {"A": 99, "B": 149},
        45: {"A": 107, "B": 160},
        50: {"A": 115, "B": 173},
        55: {"A": 123, "B": 184},
        60: {"A": 128, "B": 192},
        65: {"A": 134, "B": 201},
        70: {"A": 144, "B": 216},
    },
    0.050: {
        30: {"A": 91, "B": 136},
        35: {"A": 97, "B": 145},
        40: {"A": 103, "B": 155},
        45: {"A": 111, "B": 167},
        50: {"A": 120, "B": 180},
        55: {"A": 128, "B": 191},
        60: {"A": 133, "B": 200},
        65: {"A": 140, "B": 209},
        70: {"A": 150, "B": 225},
    },
    0.052: {
        30: {"A": 95, "B": 142},
        35: {"A": 101, "B": 151},
        40: {"A": 108, "B": 161},
        45: {"A": 116, "B": 173},
        50: {"A": 125, "B": 187},
        55: {"A": 133, "B": 199},
        60: {"A": 139, "B": 208},
        65: {"A": 145, "B": 218},
        70: {"A": 156, "B": 234},
    },
    0.054: {
        30: {"A": 98, "B": 147},
        35: {"A": 105, "B": 157},
        40: {"A": 112, "B": 168},
        45: {"A": 120, "B": 180},
        50: {"A": 130, "B": 194},
        55: {"A": 138, "B": 207},
        60: {"A": 144, "B": 216},
        65: {"A": 151, "B": 226},
        70: {"A": 162, "B": 243},
    },
    0.056: {
        30: {"A": 102, "B": 153},
        35: {"A": 108, "B": 163},
        40: {"A": 116, "B": 174},
        45: {"A": 124, "B": 187},
        50: {"A": 134, "B": 202},
        55: {"A": 143, "B": 214},
        60: {"A": 149, "B": 224},
        65: {"A": 156, "B": 234},
        70: {"A": 168, "B": 252},
    },
    0.058: {
        30: {"A": 105, "B": 158},
        35: {"A": 112, "B": 168},
        40: {"A": 120, "B": 180},
        45: {"A": 129, "B": 193},
        50: {"A": 139, "B": 209},
        55: {"A": 148, "B": 222},
        60: {"A": 155, "B": 232},
        65: {"A": 162, "B": 243},
        70: {"A": 174, "B": 261},
    },
    0.060: {
        30: {"A": 109, "B": 164},
        35: {"A": 116, "B": 174},
        40: {"A": 124, "B": 186},
        45: {"A": 133, "B": 200},
        50: {"A": 144, "B": 216},
        55: {"A": 153, "B": 230},
        60: {"A": 160, "B": 240},
        65: {"A": 167, "B": 251},
        70: {"A": 180, "B": 270},
    },
    0.062: {
        30: {"A": 113, "B": 169},
        35: {"A": 120, "B": 180},
        40: {"A": 128, "B": 192},
        45: {"A": 138, "B": 207},
        50: {"A": 149, "B": 223},
        55: {"A": 158, "B": 237},
        60: {"A": 165, "B": 248},
        65: {"A": 173, "B": 260},
        70: {"A": 186, "B": 279},
    },
    0.064: {
        30: {"A": 116, "B": 175},
        35: {"A": 124, "B": 186},
        40: {"A": 132, "B": 199},
        45: {"A": 142, "B": 213},
        50: {"A": 154, "B": 230},
        55: {"A": 163, "B": 245},
        60: {"A": 171, "B": 256},
        65: {"A": 179, "B": 268},
        70: {"A": 192, "B": 288},
    },
    0.066: {
        30: {"A": 120, "B": 180},
        35: {"A": 128, "B": 192},
        40: {"A": 137, "B": 205},
        45: {"A": 147, "B": 220},
        50: {"A": 158, "B": 238},
        55: {"A": 169, "B": 253},
        60: {"A": 176, "B": 264},
        65: {"A": 184, "B": 276},
        70: {"A": 198, "B": 297},
    },
    0.068: {
        30: {"A": 124, "B": 185},
        35: {"A": 132, "B": 197},
        40: {"A": 141, "B": 211},
        45: {"A": 151, "B": 227},
        50: {"A": 163, "B": 245},
        55: {"A": 174, "B": 260},
        60: {"A": 181, "B": 272},
        65: {"A": 190, "B": 285},
        70: {"A": 204, "B": 306},
    },
    0.070: {
        30: {"A": 127, "B": 191},
        35: {"A": 135, "B": 203},
        40: {"A": 145, "B": 217},
        45: {"A": 156, "B": 233},
        50: {"A": 168, "B": 252},
        55: {"A": 179, "B": 268},
        60: {"A": 187, "B": 280},
        65: {"A": 195, "B": 293},
        70: {"A": 210, "B": 315},
    },
    0.072: {
        30: {"A": 131, "B": 196},
        35: {"A": 139, "B": 209},
        40: {"A": 149, "B": 223},
        45: {"A": 160, "B": 240},
        50: {"A": 173, "B": 259},
        55: {"A": 184, "B": 276},
        60: {"A": 192, "B": 288},
        65: {"A": 201, "B": 301},
        70: {"A": 216, "B": 324},
    },
    0.074: {
        30: {"A": 135, "B": 202},
        35: {"A": 143, "B": 215},
        40: {"A": 153, "B": 230},
        45: {"A": 164, "B": 247},
        50: {"A": 178, "B": 266},
        55: {"A": 189, "B": 283},
        60: {"A": 197, "B": 296},
        65: {"A": 207, "B": 310},
        70: {"A": 222, "B": 333},
    },
    0.076: {
        30: {"A": 138, "B": 207},
        35: {"A": 147, "B": 221},
        40: {"A": 157, "B": 236},
        45: {"A": 169, "B": 253},
        50: {"A": 182, "B": 274},
        55: {"A": 194, "B": 291},
        60: {"A": 203, "B": 304},
        65: {"A": 212, "B": 318},
        70: {"A": 228, "B": 342},
    },
    0.078: {
        30: {"A": 142, "B": 213},
        35: {"A": 151, "B": 226},
        40: {"A": 161, "B": 242},
        45: {"A": 173, "B": 260},
        50: {"A": 187, "B": 281},
        55: {"A": 199, "B": 299},
        60: {"A": 208, "B": 312},
        65: {"A": 218, "B": 327},
        70: {"A": 234, "B": 351},
    },
    0.080: {
        30: {"A": 145, "B": 218},
        35: {"A": 155, "B": 232},
        40: {"A": 166, "B": 248},
        45: {"A": 178, "B": 267},
        50: {"A": 192, "B": 288},
        55: {"A": 204, "B": 306},
        60: {"A": 213, "B": 320},
        65: {"A": 223, "B": 335},
        70: {"A": 240, "B": 360},
    },
    0.082: {
        30: {"A": 149, "B": 224},
        35: {"A": 159, "B": 238},
        40: {"A": 170, "B": 254},
        45: {"A": 182, "B": 273},
        50: {"A": 197, "B": 295},
        55: {"A": 209, "B": 314},
        60: {"A": 219, "B": 328},
        65: {"A": 229, "B": 343},
        70: {"A": 246, "B": 369},
    },
    0.084: {
        30: {"A": 153, "B": 229},
        35: {"A": 163, "B": 244},
        40: {"A": 174, "B": 261},
        45: {"A": 187, "B": 280},
        50: {"A": 202, "B": 302},
        55: {"A": 214, "B": 322},
        60: {"A": 224, "B": 336},
        65: {"A": 234, "B": 352},
        70: {"A": 252, "B": 378},
    },
    0.086: {
        30: {"A": 156, "B": 235},
        35: {"A": 166, "B": 250},
        40: {"A": 178, "B": 267},
        45: {"A": 191, "B": 287},
        50: {"A": 206, "B": 310},
        55: {"A": 220, "B": 329},
        60: {"A": 229, "B": 344},
        65: {"A": 240, "B": 360},
        70: {"A": 258, "B": 387},
    },
    0.088: {
        30: {"A": 160, "B": 240},
        35: {"A": 170, "B": 255},
        40: {"A": 182, "B": 273},
        45: {"A": 196, "B": 293},
        50: {"A": 211, "B": 317},
        55: {"A": 225, "B": 337},
        60: {"A": 235, "B": 352},
        65: {"A": 246, "B": 368},
        70: {"A": 264, "B": 396},
    },
    0.090: {
        30: {"A": 164, "B": 245},
        35: {"A": 174, "B": 261},
        40: {"A": 186, "B": 279},
        45: {"A": 200, "B": 300},
        50: {"A": 216, "B": 324},
        55: {"A": 230, "B": 345},
        60: {"A": 240, "B": 360},
        65: {"A": 251, "B": 377},
        70: {"A": 270, "B": 405},
    },
    0.092: {
        30: {"A": 167, "B": 251},
        35: {"A": 178, "B": 267},
        40: {"A": 190, "B": 286},
        45: {"A": 204, "B": 307},
        50: {"A": 221, "B": 331},
        55: {"A": 235, "B": 352},
        60: {"A": 245, "B": 368},
        65: {"A": 257, "B": 385},
        70: {"A": 276, "B": 414},
    },
    0.094: {
        30: {"A": 171, "B": 256},
        35: {"A": 182, "B": 273},
        40: {"A": 194, "B": 292},
        45: {"A": 209, "B": 313},
        50: {"A": 226, "B": 338},
        55: {"A": 240, "B": 360},
        60: {"A": 251, "B": 376},
        65: {"A": 262, "B": 393},
        70: {"A": 282, "B": 423},
    },
    0.096: {
        30: {"A": 175, "B": 262},
        35: {"A": 186, "B": 279},
        40: {"A": 199, "B": 298},
        45: {"A": 213, "B": 320},
        50: {"A": 230, "B": 346},
        55: {"A": 245, "B": 368},
        60: {"A": 256, "B": 384},
        65: {"A": 268, "B": 402},
        70: {"A": 288, "B": 432},
    },
    0.098: {
        30: {"A": 178, "B": 267},
        35: {"A": 190, "B": 285},
        40: {"A": 203, "B": 304},
        45: {"A": 218, "B": 327},
        50: {"A": 235, "B": 353},
        55: {"A": 250, "B": 375},
        60: {"A": 261, "B": 392},
        65: {"A": 273, "B": 410},
        70: {"A": 294, "B": 441},
    },
    0.100: {
        30: {"A": 182, "B": 273},
        35: {"A": 194, "B": 290},
        40: {"A": 207, "B": 310},
        45: {"A": 222, "B": 333},
        50: {"A": 240, "B": 360},
        55: {"A": 255, "B": 383},
        60: {"A": 267, "B": 400},
        65: {"A": 279, "B": 419},
        70: {"A": 300, "B": 450},
    },
}

RURAL_CENTERLINE_TANGENT_RUNOUT = {
    30: {"A": 36, "B": 55},
    35: {"A": 39, "B": 58},
    40: {"A": 41, "B": 62},
    45: {"A": 44, "B": 67},
    50: {"A": 48, "B": 72},
    55: {"A": 51, "B": 77},
    60: {"A": 53, "B": 80},
    65: {"A": 56, "B": 84},
    70: {"A": 60, "B": 90},
}


def urban_centerline_v50_lookup(
    radius_ft: float, lanes_rotated: float
) -> tuple[float, float | None, str, str | None]:
    """
    Urban facility, V=50 mph, rotation about centerline table lookup.
    Returns (e, Lr, source, note). Lr uses column A (<=2 lanes) or B (>2 lanes).
    """
    col = "L_A" if lanes_rotated <= 2 else "L_B"
    if radius_ft >= URBAN_CENTERLINE_V50_TABLE["NC"]["r"]:
        return 0.0, 0.0, "Normal crown (urban v=50 table)", None
    if radius_ft >= URBAN_CENTERLINE_V50_TABLE["RC"]["r"]:
        Lr = URBAN_CENTERLINE_V50_TABLE["RC"][col]
        return 0.0, float(Lr), "Reverse crown (urban v=50 table)", None
    e_rows = sorted(k for k in URBAN_CENTERLINE_V50_TABLE.keys() if isinstance(k, float))
    for e in e_rows:
        if radius_ft >= URBAN_CENTERLINE_V50_TABLE[e]["r"]:
            Lr = URBAN_CENTERLINE_V50_TABLE[e][col]
            return e, float(Lr), "Superelevation (urban v=50 table)", None
    Lr = URBAN_CENTERLINE_V50_TABLE[e_rows[-1]][col]
    return e_rows[-1], float(Lr), "Superelevation (urban v=50 table, min radius exceeded)", None


def urban_edge_v50_lookup(
    radius_ft: float, lanes_rotated: float
) -> tuple[float, float | None, str, str | None]:
    """
    Urban facility, V=50 mph, rotation about edge table lookup.
    Returns (e, Lr, source, note). Lr uses column A (<=2 lanes) or B (>2 lanes).
    """
    col = "L_A" if lanes_rotated <= 2 else "L_B"
    if radius_ft >= URBAN_EDGE_V50_TABLE["NC"]["r"]:
        return 0.0, 0.0, "Normal crown (urban v=50 edge table)", None
    if radius_ft >= URBAN_EDGE_V50_TABLE["RC"]["r"]:
        Lr = URBAN_EDGE_V50_TABLE["RC"][col]
        return 0.0, float(Lr), "Reverse crown (urban v=50 edge table)", None
    e_rows = sorted(k for k in URBAN_EDGE_V50_TABLE.keys() if isinstance(k, float))
    for e in e_rows:
        if radius_ft >= URBAN_EDGE_V50_TABLE[e]["r"]:
            Lr = URBAN_EDGE_V50_TABLE[e][col]
            return e, float(Lr), "Superelevation (urban v=50 edge table)", None
    Lr = URBAN_EDGE_V50_TABLE[e_rows[-1]][col]
    return e_rows[-1], float(Lr), "Superelevation (urban v=50 edge table, min radius exceeded)", None


def urban_centerline_le45_lookup(
    speed_mph: float, radius_ft: float, lanes_rotated: float
) -> tuple[float, float | None, float | None, str, str | None]:
    """
    Urban facility, V<=45 mph, rotation about centerline table lookup.
    Returns (e, Lr, Lt, source, note).
    """
    speed_key = min(
        URBAN_CENTERLINE_LE45_SPEEDS, key=lambda s: abs(s - speed_mph)
    )
    note = None
    if speed_key != speed_mph:
        note = f"Using {speed_key} mph row for {speed_mph} mph."
    table = URBAN_CENTERLINE_LE45_TABLE[speed_key]
    col = "L_A" if lanes_rotated <= 2 else "L_B"
    if radius_ft >= table["NC"]["r"]:
        Lt = URBAN_CENTERLINE_LE45_LT[speed_key]["A" if col == "L_A" else "B"]
        return 0.0, 0.0, float(Lt), "Normal crown (urban <=45 table)", note
    if radius_ft >= table["RC"]["r"]:
        Lr = table["RC"][col]
        Lt = URBAN_CENTERLINE_LE45_LT[speed_key]["A" if col == "L_A" else "B"]
        return 0.0, float(Lr), float(Lt), "Reverse crown (urban <=45 table)", note
    e_rows = sorted(k for k in table.keys() if isinstance(k, float))
    for e in e_rows:
        if radius_ft >= table[e]["r"]:
            Lr = table[e][col]
            Lt = URBAN_CENTERLINE_LE45_LT[speed_key]["A" if col == "L_A" else "B"]
            return e, float(Lr), float(Lt), "Superelevation (urban <=45 table)", note
    Lr = table[e_rows[-1]][col]
    Lt = URBAN_CENTERLINE_LE45_LT[speed_key]["A" if col == "L_A" else "B"]
    return e_rows[-1], float(Lr), float(Lt), "Superelevation (urban <=45 table, min radius exceeded)", note


def rural_centerline_runoff_runout(
    speed_mph: float,
    e: float,
    e_source: str,
    lanes_rotated: float,
) -> tuple[float, float, str | None]:
    speeds = sorted(RURAL_CENTERLINE_TANGENT_RUNOUT.keys())
    speed_key = min(speeds, key=lambda s: abs(s - speed_mph))
    note_parts = []
    if speed_key != speed_mph:
        note_parts.append(f"Using {speed_key} mph SE-3A row for {speed_mph} mph.")

    col = "A" if lanes_rotated <= 2 else "B"
    factor = 1.0
    if lanes_rotated > 2:
        factors = {2.5: 1.20, 3.0: 1.33, 4.0: 1.67}
        factor = factors.get(round(lanes_rotated, 1), 1.0)
        if factor != 1.0:
            note_parts.append(f"Scaled SE-3A column B by {factor:.2f} for {lanes_rotated:.1f} lanes.")
        else:
            note_parts.append("Using SE-3A column B without scaling.")

    if e_source.lower().startswith("normal"):
        return 0.0, 0.0, "; ".join(note_parts) if note_parts else None

    if e_source.lower().startswith("reverse"):
        base_lr = RURAL_CENTERLINE_RUNOFF_TABLE["RC"][speed_key][col]
    else:
        e_rows = [k for k in RURAL_CENTERLINE_RUNOFF_TABLE.keys() if isinstance(k, float)]
        e_key = min(e_rows, key=lambda v: abs(v - e))
        if e_key != e:
            note_parts.append(f"Using SE-3A e={e_key:.3f} row for e={e:.3f}.")
        base_lr = RURAL_CENTERLINE_RUNOFF_TABLE[e_key][speed_key][col]

    base_lt = RURAL_CENTERLINE_TANGENT_RUNOUT[speed_key][col]
    return base_lr * factor, base_lt * factor, "; ".join(note_parts) if note_parts else None


DEFAULT_FRICTION_SCALE = 0.24


def friction_from_speed(speed_mph: float) -> float:
    """
    Default side-friction factors by speed (AASHTO-style).
    Returns unitless f. Linear interpolation between table speeds.
    """
    table = {
        30: 0.16,
        35: 0.15,
        40: 0.14,
        45: 0.13,
        50: 0.12,
        55: 0.11,
        60: 0.10,
        65: 0.10,
        70: 0.09,
    }
    speeds = sorted(table.keys())
    if speed_mph <= speeds[0]:
        return table[speeds[0]] * DEFAULT_FRICTION_SCALE
    if speed_mph >= speeds[-1]:
        return table[speeds[-1]] * DEFAULT_FRICTION_SCALE
    for i in range(len(speeds) - 1):
        s0, s1 = speeds[i], speeds[i + 1]
        if s0 <= speed_mph <= s1:
            f0, f1 = table[s0], table[s1]
            t = (speed_mph - s0) / (s1 - s0)
            return (f0 + (f1 - f0) * t) * DEFAULT_FRICTION_SCALE
    return table[speeds[-1]] * DEFAULT_FRICTION_SCALE


def parse_friction(value: str, speed_mph: float) -> tuple[float, str | None]:
    """
    Parse side-friction input; blank uses default table by speed.
    Accepts percent values (e.g., 2 for 2%) or unitless (e.g., 0.02).
    """
    if not value:
        return (
            friction_from_speed(speed_mph),
            f"Using default speed-based friction table scaled by {DEFAULT_FRICTION_SCALE:.2f}.",
        )
    raw = float(value)
    if raw >= 1:
        return raw / 100.0, "Interpreted friction input as percent."
    return raw, None


def round_to_half(value: float) -> float:
    return round(value * 2) / 2


def lanes_to_n1_bw(lanes_rotated: float) -> tuple[float, float, float, str | None]:
    """
    Convert total lanes rotated to n1 and bw using Table 3-4-B.
    """
    table = {
        2: (1.0, 1.00),
        3: (1.5, 0.83),
        4: (2.0, 0.75),
        5: (2.5, 0.70),
        6: (3.0, 0.67),
        7: (3.5, 0.64),
        8: (4.0, 0.625),
    }
    rounded = round_to_half(lanes_rotated)
    note = None
    if rounded < 2:
        note = "Lanes rotated < 2; using 2-lane minimum for Table 3-4-B."
        rounded = 2.0
    if rounded not in table:
        nearest = min(table.keys(), key=lambda k: abs(k - rounded))
        note = note or f"Rounded lanes {rounded} not in Table 3-4-B; using {nearest}."
        rounded = float(nearest)
    n1, bw = table[int(rounded)]
    return n1, bw, rounded, note


def min_radius_for_crown(speed_mph: float) -> tuple[float, float, str | None]:
    """
    Table 3-4-A minimum radii for normal and reverse crown (2% typical).
    Returns (R_normal, R_reverse) with linear interpolation by speed.
    """
    table = {
        30: (3320, 2440),
        40: (5520, 4080),
        50: (8280, 6130),
        55: (9890, 7330),
        60: (11700, 8630),
        65: (13100, 9720),
        70: (14700, 10900),
    }
    speeds = sorted(table.keys())
    if speed_mph <= speeds[0]:
        return table[speeds[0]][0], table[speeds[0]][1], "Using minimum speed row."
    if speed_mph >= speeds[-1]:
        return table[speeds[-1]][0], table[speeds[-1]][1], "Using maximum speed row."
    for i in range(len(speeds) - 1):
        s0, s1 = speeds[i], speeds[i + 1]
        if s0 <= speed_mph <= s1:
            n0, r0 = table[s0]
            n1, r1 = table[s1]
            t = (speed_mph - s0) / (s1 - s0)
            r_normal = n0 + (n1 - n0) * t
            r_reverse = r0 + (r1 - r0) * t
            return r_normal, r_reverse, "Interpolated from Table 3-4-A."
    return table[speeds[-1]][0], table[speeds[-1]][1], None


def compute_runoff_length(
    lane_width_ft: float,
    n1: float,
    e: float,
    relative_gradient: float,
    bw: float,
) -> float:
    """
    Superelevation runoff length per Eq. 3-4-1:
    Lr = (w * n1 * e / Δ) * bw
    """
    return (lane_width_ft * n1 * e / relative_gradient) * bw


def compute_tangent_runout(
    lane_width_ft: float,
    n1: float,
    normal_crown: float,
    relative_gradient: float,
    bw: float,
) -> float:
    """
    Tangent runout length to remove adverse crown before the reverse crown point.
    Uses the same relative gradient assumption as runoff for simplicity.
    """
    return (lane_width_ft * n1 * normal_crown / relative_gradient) * bw


def parse_required(value: str, name: str) -> float:
    if not value.strip():
        raise ValueError(f"{name} is required.")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {name}.") from exc


def parse_optional(value: str, default: float | None = None) -> float | None:
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    return float(value)


def _calculate_tdot_superelevation(
    pc_input: str,
    pt_input: str,
    speed_input: str,
    radius_input: str,
    facility: str,
    area_type: str,
    lane_width_input: str,
    lanes_rotated_input: str,
    e_manual_input: str,
    friction_input: str,
    rel_grad_input: str,
    normal_crown_input: str,
    L_manual_input: str,
    Lt_manual_input: str,
    station_equations: list[dict] | None,
    alignment_station_range: tuple[float, float] | None,
) -> dict:
    """Calculate the TDOT RD11 table profile without changing MDOT behavior."""
    speed_mph = parse_required(speed_input, "Design speed")
    radius_ft = parse_required(radius_input, "Curve radius")
    lane_width_ft = parse_optional(lane_width_input, 12.0) or 12.0
    lanes_rotated = parse_optional(lanes_rotated_input, 2.0) or 2.0
    normal_crown = parse_optional(normal_crown_input, 0.02) or 0.02
    e_manual = parse_optional(e_manual_input, None)
    L_manual = parse_optional(L_manual_input, None)
    Lt_manual = parse_optional(Lt_manual_input, None)
    if radius_ft <= 0 or lane_width_ft <= 0 or normal_crown <= 0:
        raise ValueError("Curve radius, lane width, and normal crown must be positive.")
    if str(friction_input or "").strip():
        raise ValueError(
            "The TDOT RD11 profile selects e from RD11-LR tables and does not consume a side-friction "
            "override. Use the manual e field for an engineer-approved exception."
        )

    area = (area_type or "rural").strip().lower() or "rural"
    if not (area.startswith("rural") or area.startswith("urban")):
        raise ValueError("The TDOT RD11 profile supports rural or urban highway tables; select one.")
    facility_text = str(facility).strip().lower()
    layout = "divided" if (facility_text.startswith("divided") or "edge" in facility_text) else "undivided"
    if layout == "divided":
        raise ValueError(
            "TDOT divided-roadway lane events require a carriageway-specific lane/pivot model. "
            "RD11-SE-3/3A are recorded as supporting sources, but this release intentionally blocks "
            "divided output rather than applying the undivided lane geometry."
        )
    lookup = tdot_criteria.lookup_superelevation(speed_mph, radius_ft, area)
    n1, bw, lanes_used = tdot_criteria.lane_factors(lanes_rotated)

    pc_civil_ft = parse_station(pc_input)
    pt_civil_ft = parse_station(pt_input) if pt_input.strip() else None
    normalized_equations = normalize_station_equations(station_equations)
    pc_ft = civil_to_internal_station(pc_civil_ft, normalized_equations, alignment_station_range)
    pt_ft = (
        civil_to_internal_station(pt_civil_ft, normalized_equations, alignment_station_range)
        if pt_civil_ft is not None
        else None
    )

    if str(rel_grad_input or "").strip():
        relative_gradient, rel_grad_note = parse_relative_gradient(rel_grad_input, speed_mph)
        rel_grad_note = rel_grad_note or "Using user-entered relative gradient."
    else:
        relative_gradient = tdot_criteria.relative_gradient(speed_mph)
        rel_grad_note = "Using TDOT STD. DWG RD11-SE-1, Table 1."
    if relative_gradient <= 0:
        raise ValueError("Relative gradient must be positive.")

    e = float(e_manual) if e_manual is not None else float(lookup["e"])
    if e < 0:
        raise ValueError("Superelevation rate e cannot be negative.")
    e_source = "Manual" if e_manual is not None else str(lookup["source"])
    e_note = (
        "Engineer-entered TDOT superelevation-rate override; confirm the applicable design exception."
        if e_manual is not None
        else str(lookup["note"])
    )
    normal_crown_only = abs(e) < 1e-12

    if normal_crown_only:
        L = 0.0
        Lt = 0.0
        runoff_note = "Normal crown maintained; runoff and tangent runout are zero."
    else:
        if L_manual is not None:
            if L_manual <= 0:
                raise ValueError("Manual runoff length Lr must be positive.")
            L = float(L_manual)
            runoff_note = "Using engineer-entered TDOT runoff-length override."
        else:
            L, n1, bw, lanes_used = tdot_criteria.runoff_length(
                lane_width_ft, lanes_rotated, e, relative_gradient
            )
            runoff_note = (
                "Calculated with RD11-SE-1 and rounded to the nearest whole foot to match the "
                "RD11-LR table convention."
            )
        if Lt_manual is not None:
            if Lt_manual < 0:
                raise ValueError("Manual tangent runout Lt cannot be negative.")
            Lt = float(Lt_manual)
        else:
            Lt = L * normal_crown / e

    total_transition = L + Lt
    pnc_ft = pc_ft - total_transition / 2.0
    zero_crown_ft = pnc_ft + Lt
    reverse_section_ft = zero_crown_ft + Lt
    full_super_ft = pc_ft + total_transition / 2.0

    full_super_out_ft = None
    zero_crown_out_ft = None
    reverse_section_out_ft = None
    pnc_out_ft = None
    if pt_ft is not None:
        full_super_out_ft = pt_ft - total_transition / 2.0
        zero_crown_out_ft = full_super_out_ft + L
        reverse_section_out_ft = zero_crown_out_ft - Lt
        pnc_out_ft = pt_ft + total_transition / 2.0

    warnings: list[str] = []
    if lookup.get("below_minimum_radius") and e_manual is None:
        warnings.append(str(lookup["note"]))
    if speed_mph >= 50 and e >= 0.03:
        warnings.append(
            "TDOT RD11-SE-1 recommends a spiral for design speed 50 mph or greater and e of 3% or greater."
        )
    profile_id = tdot_criteria.TDOT_PROFILE_ID
    result = {
        "calculation_metadata": {
            "engine_version": CALCULATION_ENGINE_VERSION,
            "criteria": criteria_metadata(profile_id),
            "manual_overrides": {
                "superelevation_rate": e_manual is not None,
                "runoff_length": L_manual is not None,
                "tangent_runout": Lt_manual is not None,
                "side_friction": False,
                "relative_gradient": bool(str(rel_grad_input or "").strip()),
                "normal_crown": str(normal_crown_input or "").strip() not in {"", "0.02", "0.0200"},
            },
        },
        "inputs": {
            "criteria_profile": profile_id,
            "pc": pc_input,
            "pt": pt_input,
            "speed_mph": speed_mph,
            "radius_ft": radius_ft,
            "facility": layout,
            "area_type": area,
            "lane_width_ft": lane_width_ft,
            "lanes_rotated": lanes_rotated,
            "e_manual": e_manual,
            "friction_input": friction_input,
            "relative_gradient_input": rel_grad_input,
            "normal_crown": normal_crown,
            "Lr_manual": L_manual,
            "Lt_manual": Lt_manual,
        },
        "facility": layout,
        "area_type": area,
        "pc_ft": pc_ft,
        "pt_ft": pt_ft,
        "station_equations": normalized_equations,
        "alignment_station_range": alignment_station_range,
        "e": e,
        "e_max": float(lookup["e_max"]),
        "e_source": e_source,
        "e_note": e_note,
        "runoff_note": runoff_note,
        "extra_width": 0.0,
        "extra_width_note": None,
        "friction": None,
        "friction_note": "Not used by the TDOT RD11 table profile.",
        "relative_gradient": relative_gradient,
        "rel_grad_note": rel_grad_note,
        "Lr": L,
        "Lt": Lt,
        "lanes_used": float(lanes_used),
        "n1": n1,
        "bw": bw,
        "lanes_note": "Using TDOT RD11-SE-1, Table 2.",
        "r_normal": float(lookup["normal_radius"]),
        "r_reverse": float(lookup["reverse_radius"]),
        "r_note": f"Using {lookup['source']} exact speed row.",
        "crown_state": "Normal crown" if normal_crown_only else "See standard drawings",
        "normal_crown_only": normal_crown_only,
        "transition_method": "tdot_simple_curve_half_total",
        "pnc_ft": pnc_ft,
        "zero_crown_ft": zero_crown_ft,
        "reverse_section_ft": reverse_section_ft,
        # Compatibility names used by existing reports and project files.
        "reverse_crown_ft": zero_crown_ft,
        "full_super_ft": full_super_ft,
        "pnc_out_ft": pnc_out_ft,
        "zero_crown_out_ft": zero_crown_out_ft,
        "reverse_section_out_ft": reverse_section_out_ft,
        "reverse_crown_out_ft": zero_crown_out_ft,
        "full_super_out_ft": full_super_out_ft,
        "segments": {
            "runoff_Lr": L,
            "runout_Lt": Lt,
            "half_total_transition": total_transition / 2.0,
            "total_transition": total_transition,
        },
        "warnings": warnings,
    }
    result["calculation_metadata"]["criteria"] = criteria_for_result(result)
    return result


def calculate_superelevation(
    pc_input: str,
    pt_input: str,
    speed_input: str,
    radius_input: str,
    facility: str,
    area_type: str,
    lane_width_input: str,
    lanes_rotated_input: str,
    e_manual_input: str,
    friction_input: str,
    rel_grad_input: str,
    normal_crown_input: str,
    L_manual_input: str,
    Lt_manual_input: str,
    station_equations: list[dict] | None = None,
    alignment_station_range: tuple[float, float] | None = None,
    criteria_profile: str = MDOT_PROFILE_ID,
    profile_options: dict | None = None,
) -> dict:
    profile_id = normalize_profile_id(criteria_profile)
    from aashto_criteria import PROFILE_ID as AASHTO_PROFILE_ID
    if profile_options and profile_options.get("alignment_type")=="spiral" and profile_id!=AASHTO_PROFILE_ID:
        raise ValueError("Spiral transition calculations are currently supported only by the AASHTO profile.")
    if profile_id == AASHTO_PROFILE_ID:
        from aashto_superelevation import calculate
        values = {**(profile_options or {}), "pc": pc_input, "pt": pt_input, "speed": speed_input, "radius": radius_input,
                  "area": area_type, "e_manual": e_manual_input, "normal_crown": normal_crown_input,
                  "Lr_manual": L_manual_input, "Lt_manual": Lt_manual_input,
                  "friction":friction_input, "rel_grad":rel_grad_input}
        return calculate(values, station_equations, alignment_station_range)
    if profile_options and str(profile_options.get("override_standard_placement")).lower() in {"true","1"}:
        from aashto_superelevation import override_circular_placement
        result = calculate_superelevation(pc_input, pt_input, speed_input, radius_input, facility, area_type,
            lane_width_input, lanes_rotated_input, e_manual_input, friction_input, rel_grad_input,
            normal_crown_input, L_manual_input, Lt_manual_input, station_equations, alignment_station_range, profile_id)
        return override_circular_placement(result, profile_options.get("runoff_tangent_percent", ""))
    if profile_id == tdot_criteria.TDOT_PROFILE_ID:
        return _calculate_tdot_superelevation(
            pc_input,
            pt_input,
            speed_input,
            radius_input,
            facility,
            area_type,
            lane_width_input,
            lanes_rotated_input,
            e_manual_input,
            friction_input,
            rel_grad_input,
            normal_crown_input,
            L_manual_input,
            Lt_manual_input,
            station_equations,
            alignment_station_range,
        )
    speed_mph = parse_required(speed_input, "Design speed")
    radius_ft = parse_required(radius_input, "Curve radius")
    lane_width_ft = parse_optional(lane_width_input, 12.0) or 12.0
    lanes_rotated = parse_optional(lanes_rotated_input, 2.0) or 2.0
    normal_crown = parse_optional(normal_crown_input, 0.02) or 0.02
    e_manual = parse_optional(e_manual_input, None)
    L_manual = parse_optional(L_manual_input, None)
    Lt_manual = parse_optional(Lt_manual_input, None)

    pc_civil_ft = parse_station(pc_input)
    pt_civil_ft = parse_station(pt_input) if pt_input.strip() else None
    normalized_equations = normalize_station_equations(station_equations)
    pc_ft = civil_to_internal_station(pc_civil_ft, normalized_equations, alignment_station_range)
    pt_ft = civil_to_internal_station(pt_civil_ft, normalized_equations, alignment_station_range) if pt_civil_ft is not None else None
    area = (area_type or "rural").strip().lower() or "rural"
    if area.startswith("local"):
        facility = "centerline"

    if area.startswith("local"):
        e_max = 0.06
    elif area.startswith("urban"):
        if speed_mph <= 45:
            e_max = 0.04
        elif speed_mph == 50:
            e_max = 0.06
        else:
            e_max = 0.10
    else:
        e_max = 0.10

    relative_gradient, rel_grad_note = parse_relative_gradient(rel_grad_input, speed_mph)
    n1, bw, lanes_used, lanes_note = lanes_to_n1_bw(lanes_rotated)
    r_normal, r_reverse, r_note = min_radius_for_crown(speed_mph)
    if radius_ft >= r_normal:
        crown_state = "Normal crown"
    elif radius_ft >= r_reverse:
        crown_state = "Reverse crown"
    else:
        crown_state = "See standard drawings"

    friction = None
    friction_note = None
    e_note = None
    e_source = "Manual"
    Lr_override = None
    Lt_override = None
    runoff_note = None
    extra_width = 0.0
    extra_width_note = None

    if e_manual is not None:
        e = e_manual
    elif area.startswith("local"):
        e, e_source, e_note = local_table_superelevation(speed_mph, radius_ft)
    elif area.startswith("rural"):
        e, e_source, e_note = rural_table_superelevation(speed_mph, radius_ft)
        if "center" in facility.lower():
            Lr_override, Lt_override, runoff_note = rural_centerline_runoff_runout(
                speed_mph, e, e_source, lanes_rotated
            )
    elif area.startswith("urban") and speed_mph == 50 and "center" in facility.lower():
        e, Lr_override, e_source, e_note = urban_centerline_v50_lookup(
            radius_ft, lanes_rotated
        )
    elif area.startswith("urban") and speed_mph == 50 and "edge" in facility.lower():
        e, Lr_override, e_source, e_note = urban_edge_v50_lookup(radius_ft, lanes_rotated)
    elif area.startswith("urban") and speed_mph <= 45 and "center" in facility.lower():
        e, Lr_override, Lt_override, e_source, e_note = urban_centerline_le45_lookup(
            speed_mph, radius_ft, lanes_rotated
        )
    else:
        friction, friction_note = parse_friction(friction_input, speed_mph)
        e, e_note = compute_superelevation_rate(speed_mph, radius_ft, e_manual, friction, e_max)
        e_source = "Formula"

    if area.startswith("local"):
        Lr_override, Lt_override, runoff_note = rural_centerline_runoff_runout(
            speed_mph, e, e_source, lanes_rotated
        )
        extra_width, extra_width_note = local_extra_width(speed_mph, radius_ft, lane_width_ft)

    # A zero-rate curve above the Table 3-4-A normal-crown radius has no
    # superelevation transition.  Do not create coincident 0%/full-super events.
    normal_crown_only = crown_state == "Normal crown" and abs(e) < 1e-9
    if normal_crown_only:
        L = 0.0
        Lt = 0.0
    elif L_manual is not None:
        L = L_manual
    elif Lr_override is not None:
        L = Lr_override
    else:
        L = compute_runoff_length(lane_width_ft, n1, e, relative_gradient, bw)

    if normal_crown_only:
        Lt = 0.0
    elif Lt_manual is not None:
        Lt = Lt_manual
    elif Lt_override is not None:
        Lt = Lt_override
    else:
        Lt = compute_tangent_runout(lane_width_ft, n1, normal_crown, relative_gradient, bw)

    reverse_crown_ft = pc_ft - 0.7 * L
    pnc_ft = reverse_crown_ft - Lt
    full_super_ft = pc_ft + 0.3 * L

    full_super_out_ft = None
    reverse_crown_out_ft = None
    pnc_out_ft = None
    if pt_ft is not None:
        full_super_out_ft = pt_ft - 0.3 * L
        reverse_crown_out_ft = pt_ft + 0.7 * L
        pnc_out_ft = reverse_crown_out_ft + Lt

    result = {
        "calculation_metadata": {
            "engine_version": CALCULATION_ENGINE_VERSION,
            "criteria": criteria_metadata(profile_id),
            "manual_overrides": {
                "superelevation_rate": e_manual is not None,
                "runoff_length": L_manual is not None,
                "tangent_runout": Lt_manual is not None,
                "side_friction": bool(friction_input.strip()),
                "relative_gradient": bool(rel_grad_input.strip()),
                "normal_crown": normal_crown_input.strip() not in {"", "0.02", "0.0200"},
            },
        },
        "inputs": {
            "criteria_profile": profile_id,
            "pc": pc_input,
            "pt": pt_input,
            "speed_mph": speed_mph,
            "radius_ft": radius_ft,
            "facility": facility,
            "area_type": area,
            "lane_width_ft": lane_width_ft,
            "lanes_rotated": lanes_rotated,
            "e_manual": e_manual,
            "friction_input": friction_input,
            "relative_gradient_input": rel_grad_input,
            "normal_crown": normal_crown,
            "Lr_manual": L_manual,
            "Lt_manual": Lt_manual,
        },
        "facility": facility,
        "area_type": area,
        "pc_ft": pc_ft,
        "pt_ft": pt_ft,
        "station_equations": normalized_equations,
        "alignment_station_range": alignment_station_range,
        "e": e,
        "e_max": e_max,
        "e_source": e_source,
        "e_note": e_note,
        "runoff_note": runoff_note,
        "extra_width": extra_width,
        "extra_width_note": extra_width_note,
        "friction": friction,
        "friction_note": friction_note,
        "relative_gradient": relative_gradient,
        "rel_grad_note": rel_grad_note,
        "Lr": L,
        "Lt": Lt,
        "lanes_used": lanes_used,
        "n1": n1,
        "bw": bw,
        "lanes_note": lanes_note,
        "r_normal": r_normal,
        "r_reverse": r_reverse,
        "r_note": r_note,
        "crown_state": crown_state,
        "normal_crown_only": normal_crown_only,
        "transition_method": "mdot_70_30_runoff",
        "pnc_ft": pnc_ft,
        "reverse_crown_ft": reverse_crown_ft,
        "full_super_ft": full_super_ft,
        "pnc_out_ft": pnc_out_ft,
        "reverse_crown_out_ft": reverse_crown_out_ft,
        "full_super_out_ft": full_super_out_ft,
        "segments": {
            "runoff_Lr": L,
            "runout_Lt": Lt,
            "approx_0p7L": 0.7 * L,
            "approx_0p3L": 0.3 * L,
            "total_transition": L + Lt,
        },
    }
    result["calculation_metadata"]["criteria"] = criteria_for_result(result)
    return result


def format_results(results: dict, station_format: bool) -> list[str]:
    if results.get("transition_method") == "aashto_fixed_pivot" or results.get("runoff_tangent_fraction") is not None:
        lines=[f"Criteria: {results.get('calculation_metadata', {}).get('criteria', {}).get('profile_name', '')}",
               f"Rate: {results['e']:.4f} ft/ft", f"Runoff: {results['Lr']:.3f} ft", f"Runout: {results['Lt']:.3f} ft",
               f"Rotation axis: {results.get('facility')}"]
        for label,key in [("Start transition","pnc_ft"),("Start runoff","reverse_crown_ft"),("Full super entry","full_super_ft"),("Full super exit","full_super_out_ft"),("End runoff","reverse_crown_out_ft"),("End transition","pnc_out_ft")]:
            lines.append(f"{label}: {format_result_station(results,results.get(key),station_format)}")
        lines.extend(f"Warning: {warning}" for warning in results.get("warnings",[]))
        return lines
    inputs = results.get("inputs", {})
    segments = results.get("segments", {})
    criteria = criteria_for_result(results)
    is_tdot = str(criteria.get("profile_id", "")).startswith("tdot")

    lines = ["--- Criteria References ---"]
    lines.append(f"Profile: {criteria.get('profile_name', criteria.get('profile_id', 'unknown'))}")
    lines.append(f"Applicable: {applicable_drawings_label(criteria)}")
    lines.append(f"Calculation sources: {calculation_sources_label(criteria)}")
    lines.append("\n--- Inputs ---")
    lines.append(f"PC station: {inputs.get('pc', '')}")
    lines.append(f"PT station: {inputs.get('pt', '') or 'n/a'}")
    lines.append(f"Design speed: {inputs.get('speed_mph', '')} mph")
    lines.append(f"Curve radius: {inputs.get('radius_ft', '')} ft")
    lines.append(f"Facility / rotation: {inputs.get('facility', '')}")
    lines.append(f"Area type: {inputs.get('area_type', '')}")
    lines.append(f"Lane width: {inputs.get('lane_width_ft', '')} ft")
    lines.append(f"Lanes rotated: {inputs.get('lanes_rotated', '')}")
    lines.append(f"Manual e: {inputs.get('e_manual', '') if inputs.get('e_manual') is not None else 'auto'}")
    lines.append(
        f"Manual Lr: {inputs.get('Lr_manual', '') if inputs.get('Lr_manual') is not None else 'auto'} ft"
    )
    lines.append(
        f"Manual Lt: {inputs.get('Lt_manual', '') if inputs.get('Lt_manual') is not None else 'auto'} ft"
    )
    lines.append(f"Normal crown: {inputs.get('normal_crown', '')} ft/ft")
    lines.append(f"Relative gradient input: {inputs.get('relative_gradient_input', '') or 'auto'}")
    lines.append(f"Side friction input: {inputs.get('friction_input', '') or 'auto'}")

    lines.append("\n--- Results ---")
    lines.append(f"Facility case: {results['facility'] or 'n/a'}")
    if results.get("pt_ft") is not None:
        lines.append(f"PT: {format_result_station(results, results['pt_ft'], station_format)}")
    lines.append(f"Superelevation rate e: {results['e']:.4f} ft/ft")
    lines.append(f"e_max used: {results['e_max']:.2f} ft/ft")
    lines.append(f"e source: {results['e_source']}")
    if results.get("friction") is not None:
        lines.append(f"Side friction factor f: {results['friction']:.4f}")
    if results.get("friction_note"):
        lines.append(f"Note: {results['friction_note']}")
    if results.get("e_note"):
        lines.append(f"Note: {results['e_note']}")
    if results.get("runoff_note"):
        lines.append(f"Note: {results['runoff_note']}")
    lines.append(
        f"Lanes rotated used: {results['lanes_used']:.1f} (n1={results['n1']:.1f}, bw={results['bw']:.3f})"
    )
    if results.get("lanes_note"):
        lines.append(f"Note: {results['lanes_note']}")
    lines.append(f"Relative gradient used: {results['relative_gradient']:.4f} ft/ft")
    if results.get("rel_grad_note"):
        lines.append(f"Note: {results['rel_grad_note']}")
    radius_label = "TDOT table radii (Rnc, R at 2%)" if is_tdot else "Table 3-4-A radii (Rnc, Rrc)"
    lines.append(f"{radius_label}: {results['r_normal']:.0f} ft, {results['r_reverse']:.0f} ft")
    if results.get("r_note"):
        lines.append(f"Note: {results['r_note']}")
    lines.append(f"Crown condition by governing table: {results['crown_state']}")
    for warning in results.get("warnings", []) or []:
        lines.append(f"Warning: {warning}")
    if results.get("normal_crown_only"):
        lines.append("Normal crown is maintained through this curve; no superelevation transition is required.")
        return lines
    lines.append(f"Runoff length Lr: {results['Lr']:.2f} ft")
    lines.append(f"Tangent runout Lt: {results['Lt']:.2f} ft")
    if results.get("extra_width", 0.0) > 0:
        lines.append(f"Extra width (inside of curve): {results['extra_width']:.2f} ft")
        if results.get("extra_width_note"):
            lines.append(f"Note: {results['extra_width_note']}")
    lines.append(f"Total transition (Lt + Lr): {segments.get('total_transition', 0.0):.2f} ft")
    if is_tdot:
        lines.append(f"One-half total transition: {segments.get('half_total_transition', 0.0):.2f} ft")
        lines.append(
            f"Start of normal-crown transition: {format_result_station(results, results['pnc_ft'], station_format)}"
        )
        lines.append(
            f"Zero crown / start of runoff: {format_result_station(results, results['zero_crown_ft'], station_format)}"
        )
        lines.append(
            f"Reverse-crown section: {format_result_station(results, results['reverse_section_ft'], station_format)}"
        )
        lines.append(
            f"Full super (PC + one-half total): {format_result_station(results, results['full_super_ft'], station_format)}"
        )
        if results.get("pt_ft") is not None:
            lines.append(
                f"Full super (PT - one-half total): {format_result_station(results, results['full_super_out_ft'], station_format)}"
            )
            lines.append(
                f"Zero crown / end of runoff: {format_result_station(results, results['zero_crown_out_ft'], station_format)}"
            )
            lines.append(
                f"Normal crown restored: {format_result_station(results, results['pnc_out_ft'], station_format)}"
            )
        return lines
    lines.append(f"Approx. 0.7Lr: {segments.get('approx_0p7L', 0.0):.2f} ft")
    lines.append(f"Approx. 0.3Lr: {segments.get('approx_0p3L', 0.0):.2f} ft")
    if results.get("reverse_curve_entry_zero_ft") is not None:
        lines.append(
            f"Shared reverse-curve 0% meeting: {format_result_station(results, results['reverse_curve_entry_zero_ft'], station_format)}"
        )
        lines.append(
            f"Full super (PC + 0.3Lr): {format_result_station(results, results['full_super_ft'], station_format)}"
        )
    else:
        lines.append(
            f"Point of normal crown (start of tangential runout): {format_result_station(results, results['pnc_ft'], station_format)}"
        )
        lines.append(
            f"Point of reverse crown (PC - 0.7L): {format_result_station(results, results['reverse_crown_ft'], station_format)}"
        )
        lines.append(
            f"Full super (PC + 0.3L): {format_result_station(results, results['full_super_ft'], station_format)}"
        )
    if results.get("pt_ft") is not None:
        if results.get("reverse_curve_exit_zero_ft") is not None:
            lines.append(
                f"Full super (PT - 0.3Lr): {format_result_station(results, results['full_super_out_ft'], station_format)}"
            )
            lines.append(
                f"Shared reverse-curve 0% meeting: {format_result_station(results, results['reverse_curve_exit_zero_ft'], station_format)}"
            )
        else:
            lines.append(
                f"Full super (PT - 0.3L): {format_result_station(results, results['full_super_out_ft'], station_format)}"
            )
            lines.append(
                f"Point of reverse crown (PT + 0.7L): {format_result_station(results, results['reverse_crown_out_ft'], station_format)}"
            )
            lines.append(
                f"Point of normal crown (end of tangential runout): {format_result_station(results, results['pnc_out_ft'], station_format)}"
            )
    coordination = results.get("reverse_curve_coordination", {}) or {}
    if coordination.get("checks"):
        check = coordination["checks"][0]
        lines.append(
            f"Reverse-curve tangent: {float(check.get('available_tangent_ft', 0.0)):.2f} ft available; "
            f"{float(check.get('minimum_tangent_ft', 0.0)):.2f} ft minimum"
        )
        lines.append(f"Reverse-curve rule: {check.get('rule', 'Tmin = 0.7Lr(exit) + 0.7Lr(entry)')}")
        if check.get("transition_rate_status"):
            lines.append(f"Reverse-curve transition rate: {str(check['transition_rate_status']).replace('_', ' ')}")
        for side in ("left", "right"):
            lane = (check.get("lanes", {}) or {}).get(side, {}) or {}
            if lane.get("handoff_station_ft") is None:
                continue
            lines.append(
                f"{side.title()}-lane reverse handoff: "
                f"{format_result_station(results, lane['handoff_station_ft'], station_format)} "
                f"at {float(lane.get('handoff_slope_pct', 0.0)):+.2f}%"
            )
            hold = lane.get("normal_crown_hold") or {}
            if hold:
                lines.append(
                    f"{side.title()}-lane normal-crown hold: "
                    f"{format_result_station(results, hold['start_ft'], station_format)} to "
                    f"{format_result_station(results, hold['end_ft'], station_format)} "
                    f"({float(hold.get('length_ft', 0.0)):.2f} ft)"
                )
    return lines

def main():
    print("Superelevation Transition Calculator (MDOT-style geometry)")
    print("Enter stations as feet (e.g., 1050) or highway format (e.g., 10+50).")

    pc_input = input("PC station: ").strip()
    pt_input = input("PT station (optional, for your reference): ").strip()
    speed_input = input("Design speed (mph): ").strip()
    radius_input = input("Curve radius (ft): ").strip()
    facility = input("Facility / rotation case (e.g., centerline, outside edge): ").strip()
    area_type = input("Area type (rural/urban/local, default rural): ").strip().lower() or "rural"

    lane_width_input = input("Lane width used for rotation (ft, default 12): ").strip()
    lanes_rotated_input = input(
        "Number of lanes rotated (total lanes in roadway, e.g., 2-8): "
    ).strip()

    e_manual_input = input("Superelevation rate e (ft/ft), leave blank to auto-compute: ").strip()
    friction_input = input(
        "Side friction factor f (unitless or %, blank uses default table): "
    ).strip()
    rel_grad_input = input(
        "Relative gradient for runoff (ft/ft or %, blank uses Table 3-4-C): "
    ).strip()
    normal_crown_input = input("Normal crown magnitude (ft/ft, default 0.02): ").strip()

    L_manual_input = input("Runoff length Lr (ft), leave blank to compute: ").strip()
    Lt_manual_input = input("Tangent runout length Lt (ft), leave blank to compute: ").strip()
    station_fmt = input("Display stations in highway format (y/n, default y): ").strip().lower() or "y"
    station_format = station_fmt.startswith("y")

    results = calculate_superelevation(
        pc_input,
        pt_input,
        speed_input,
        radius_input,
        facility,
        area_type,
        lane_width_input,
        lanes_rotated_input,
        e_manual_input,
        friction_input,
        rel_grad_input,
        normal_crown_input,
        L_manual_input,
        Lt_manual_input,
    )
    for line in format_results(results, station_format):
        print(line)


if __name__ == "__main__":
    main()
