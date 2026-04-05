"""ReefPilot — Cost calculation engine.

Calculates estimated monthly recurring costs from user profile + wizard answers.
"""

import json

from reef_data import (
    SALT_BRANDS, SALT_PRICES, DOSING_PRICES, FILTER_MEDIA_PRICES,
    RODI_COSTS, FOOD_PRICES, DEFAULT_ELECTRICITY_RATE,
    DEFAULT_EQUIPMENT_WATTAGE, DEFAULT_DOSING_ML,
    EVAPORATION_RATE_PER_GALLON_PER_DAY,
)

GALLONS_TO_LITERS = 3.78541


def _tank_size_class(gallons):
    if gallons and gallons > 120:
        return 'large'
    if gallons and gallons >= 40:
        return 'medium'
    return 'small'


def _get_answer(answers, key, default=None):
    """Get an answer value from the wizard answers dict, respecting skipped."""
    entry = answers.get(key)
    if entry is None:
        return default
    if entry.get('skipped'):
        return default
    val = entry.get('value')
    return val if val not in (None, '', 'null') else default


def _float(val, default=0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ── Individual calculators ──────────────────────────────────────────────

def calculate_salt_cost(tank_gallons, sump_gallons, wc_schedule, salt_brand,
                        bucket_price=None):
    """Monthly salt cost based on water change volume and salt brand."""
    total_vol = (tank_gallons or 75) + (sump_gallons or 0)

    # Parse water change schedule -> fraction and frequency per month
    wc_map = {
        '10_weekly':   (0.10, 4.33),
        '20_biweekly': (0.20, 2.17),
        '25_monthly':  (0.25, 1.0),
    }
    fraction, times = wc_map.get(wc_schedule, (0.20, 2.17))
    gallons_per_month = total_vol * fraction * times
    liters_per_month = gallons_per_month * GALLONS_TO_LITERS

    # Grams needed
    brand_info = SALT_BRANDS.get(salt_brand, {})
    grams_per_liter = brand_info.get('grams_per_liter', 37.5)
    grams_per_month = liters_per_month * grams_per_liter

    # Price per gram from bucket
    price_info = SALT_PRICES.get(salt_brand, {'bucket_kg': 22, 'price': 60})
    price = bucket_price if bucket_price else price_info['price']
    bucket_grams = price_info['bucket_kg'] * 1000
    cost_per_gram = price / bucket_grams

    return round(grams_per_month * cost_per_gram, 2)


def calculate_electricity_cost(answers, tank_gallons):
    """Monthly electricity cost from equipment wattage."""
    size_class = _tank_size_class(tank_gallons)
    rate = _float(_get_answer(answers, 'electricity_rate'), DEFAULT_ELECTRICITY_RATE)

    total_kwh = 0

    # Lighting — supports multi-light fixtures via JSON list
    fixtures_json = _get_answer(answers, 'light_fixtures')
    if fixtures_json:
        try:
            fixtures = json.loads(fixtures_json) if isinstance(fixtures_json, str) else fixtures_json
        except (json.JSONDecodeError, TypeError):
            fixtures = []
        for fix in fixtures:
            w = _float(fix.get('watts'), 100)
            q = _int(fix.get('qty'), 1)
            h = _float(fix.get('hours'), 8)
            total_kwh += w * q * h * 30 / 1000
    else:
        # Fallback: single light or defaults
        light_watts = _float(_get_answer(answers, 'light_wattage'),
                             DEFAULT_EQUIPMENT_WATTAGE.get('led', {}).get(size_class, 100))
        light_hours = _float(_get_answer(answers, 'light_hours'), 8)
        total_kwh += light_watts * light_hours * 30 / 1000

    # Heater (~50% duty cycle)
    heater_watts = _float(_get_answer(answers, 'heater_wattage'),
                          DEFAULT_EQUIPMENT_WATTAGE['heater'].get(size_class, 200))
    total_kwh += heater_watts * 0.5 * 24 * 30 / 1000

    # Return pump (24/7)
    pump_watts = _float(_get_answer(answers, 'return_pump_wattage'),
                        DEFAULT_EQUIPMENT_WATTAGE['return_pump'].get(size_class, 40))
    total_kwh += pump_watts * 24 * 30 / 1000

    # Powerheads (24/7)
    ph_count = _int(_get_answer(answers, 'powerhead_count'), 2)
    ph_watts = _float(_get_answer(answers, 'powerhead_wattage'),
                      DEFAULT_EQUIPMENT_WATTAGE['powerhead']['default'])
    total_kwh += ph_count * ph_watts * 24 * 30 / 1000

    # Skimmer (24/7)
    skimmer_watts = _float(_get_answer(answers, 'skimmer_wattage'),
                           DEFAULT_EQUIPMENT_WATTAGE['skimmer'].get(size_class, 25))
    total_kwh += skimmer_watts * 24 * 30 / 1000

    return round(total_kwh * rate, 2)


def calculate_rodi_cost(tank_gallons, sump_gallons, wc_schedule, answers):
    """Monthly RO/DI water cost (filters or purchase)."""
    total_vol = (tank_gallons or 75) + (sump_gallons or 0)

    # Water change volume per month
    wc_map = {
        '10_weekly':   (0.10, 4.33),
        '20_biweekly': (0.20, 2.17),
        '25_monthly':  (0.25, 1.0),
    }
    fraction, times = wc_map.get(wc_schedule, (0.20, 2.17))
    wc_gallons = total_vol * fraction * times

    # Evaporation top-off
    evap_gallons = total_vol * EVAPORATION_RATE_PER_GALLON_PER_DAY * 30

    total_gallons = wc_gallons + evap_gallons

    makes_own = _get_answer(answers, 'rodi_makes_own', 'yes')
    if makes_own == 'no':
        buy_price = _float(_get_answer(answers, 'rodi_buy_price'), 0.50)
        return round(total_gallons * buy_price, 2)

    # Amortize filter cost
    stage = _get_answer(answers, 'rodi_stage', '4_stage')
    rodi_info = RODI_COSTS.get(stage, RODI_COSTS['4_stage'])
    monthly_filter_cost = rodi_info['annual_cost'] / 12
    # Scale if usage exceeds rated capacity
    annual_gallons = total_gallons * 12
    if annual_gallons > rodi_info['rated_gallons']:
        monthly_filter_cost *= annual_gallons / rodi_info['rated_gallons']

    return round(monthly_filter_cost, 2)


def calculate_dosing_cost(answers, tank_gallons, tank_type, dosing_method):
    """Monthly dosing supplement cost."""
    if dosing_method == 'none':
        return 0

    size_class = _tank_size_class(tank_gallons)
    brand = _get_answer(answers, 'dosing_brand', 'brs_2part')
    daily_ml = _get_answer(answers, 'dosing_daily_ml')

    if daily_ml is None or daily_ml == 'not_sure':
        # Estimate from tank type and size
        type_defaults = DEFAULT_DOSING_ML.get(tank_type, DEFAULT_DOSING_ML['mixed_reef'])
        daily_ml = type_defaults.get(size_class, 40)
    else:
        daily_ml = _float(daily_ml, 40)

    brand_info = DOSING_PRICES.get(brand, DOSING_PRICES['brs_2part'])
    cost_per_ml = brand_info['cost_per_liter'] / 1000
    return round(daily_ml * 30 * cost_per_ml, 2)


def calculate_filter_media_cost(answers):
    """Monthly filter media replacement cost."""
    freq_map = {'weekly': 4.33, 'biweekly': 2.17, 'monthly': 1.0, 'none': 0}
    total = 0

    uses_carbon = _get_answer(answers, 'uses_carbon', 'no')
    if uses_carbon == 'yes':
        freq = _get_answer(answers, 'carbon_frequency', 'monthly')
        total += FILTER_MEDIA_PRICES['carbon']['cost_per_use'] * freq_map.get(freq, 1.0)

    uses_gfo = _get_answer(answers, 'uses_gfo', 'no')
    if uses_gfo == 'yes':
        freq = _get_answer(answers, 'gfo_frequency', 'monthly')
        total += FILTER_MEDIA_PRICES['gfo']['cost_per_use'] * freq_map.get(freq, 1.0)

    sock_freq = _get_answer(answers, 'filter_sock_frequency', 'none')
    if sock_freq != 'none':
        total += FILTER_MEDIA_PRICES['filter_socks']['cost_per_use'] * freq_map.get(sock_freq, 0)

    return round(total, 2)


def calculate_food_cost(answers, fish_count):
    """Monthly fish food cost."""
    feedings = _int(_get_answer(answers, 'feedings_per_day'), 2)
    food_type = _get_answer(answers, 'food_type', 'combo')
    price = FOOD_PRICES.get(food_type, FOOD_PRICES['combo'])
    # Scale slightly with fish count (more fish = slightly more food)
    count = max(fish_count or 2, 1)
    scale = min(count / 5, 3)  # caps at 3x for 15+ fish
    return round(feedings * 30 * price['cost_per_feeding'] * scale, 2)


# ── Orchestrator ────────────────────────────────────────────────────────

def calculate_all_costs(user, answers):
    """Calculate all recurring monthly costs.

    Args:
        user: dict with user profile fields (tank_size_gallons, salt_brand, etc.)
        answers: dict of {question_key: {value, skipped}} from cost_wizard_profile

    Returns:
        list of {category, description, monthly_amount} dicts
    """
    tank_gallons = user.get('tank_size_gallons') or 75
    sump_gallons = user.get('sump_size_gallons') or 0
    wc_schedule = user.get('water_change_schedule', '20_biweekly')
    salt_brand = user.get('salt_brand', 'instant_ocean')
    tank_type = user.get('tank_type', 'mixed_reef')
    dosing_method = user.get('dosing', 'none')
    fish_count = user.get('fish_count') or 2

    bucket_price = _float(_get_answer(answers, 'salt_bucket_price'), None)

    costs = []

    # Salt
    salt = calculate_salt_cost(tank_gallons, sump_gallons, wc_schedule,
                               salt_brand, bucket_price)
    if salt > 0:
        brand_name = SALT_BRANDS.get(salt_brand, {}).get('name', 'Salt Mix')
        costs.append({
            'category': 'Salt',
            'description': f'{brand_name} ({wc_schedule.replace("_", " ")})',
            'monthly_amount': salt,
        })

    # Electricity
    elec = calculate_electricity_cost(answers, tank_gallons)
    if elec > 0:
        costs.append({
            'category': 'Electricity',
            'description': 'Equipment power consumption',
            'monthly_amount': elec,
        })

    # RO/DI
    rodi = calculate_rodi_cost(tank_gallons, sump_gallons, wc_schedule, answers)
    if rodi > 0:
        makes_own = _get_answer(answers, 'rodi_makes_own', 'yes')
        desc = 'Filter replacement' if makes_own == 'yes' else 'Water purchase'
        costs.append({
            'category': 'RO/DI Water',
            'description': desc,
            'monthly_amount': rodi,
        })

    # Dosing
    dosing = calculate_dosing_cost(answers, tank_gallons, tank_type, dosing_method)
    if dosing > 0:
        brand = _get_answer(answers, 'dosing_brand', 'brs_2part')
        brand_name = DOSING_PRICES.get(brand, {}).get('name', '2-Part Solution')
        costs.append({
            'category': 'Dosing',
            'description': brand_name,
            'monthly_amount': dosing,
        })

    # Filter Media
    media = calculate_filter_media_cost(answers)
    if media > 0:
        costs.append({
            'category': 'Filter Media',
            'description': 'Carbon, GFO, filter socks',
            'monthly_amount': media,
        })

    # Food
    food = calculate_food_cost(answers, fish_count)
    if food > 0:
        food_type = _get_answer(answers, 'food_type', 'combo')
        costs.append({
            'category': 'Food',
            'description': FOOD_PRICES.get(food_type, {}).get('name', 'Fish food'),
            'monthly_amount': food,
        })

    return costs
