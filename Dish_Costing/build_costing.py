import json

with open(r'E:\Cloud Kitchen\AI Teams\canonical_price_list.json', 'r') as f:
    prices = json.load(f)
with open(r'E:\Cloud Kitchen\AI Teams\korean_recipes.json', 'r') as f:
    recipes = json.load(f)

# Step 1: Build base price map from canonical price list (lowest prices)
price_map = {}
for item in prices['items']:
    price_map[item['ingredient'].strip().lower()] = {
        'price': item['price_per_unit'],
        'uom': item['uom']
    }

# Step 2: Fix known pricing/UOM issues
# Tap water = free
price_map['tap water'] = {'price': 0.0, 'uom': 'L'}

# Gyoza Wrapper: 140gm pack = ~25 wrappers @ AED 6.5 => AED 0.26/piece
price_map['gyoza wrapper'] = {'price': 0.26, 'uom': 'Piece'}

# Chicken Wings Uncooked: price is 15 AED/Kg, recipes use Pieces
# Each wing weighs ~60g = 0.06 Kg
# 15 AED/Kg * 0.06 Kg/piece = 0.90 AED/piece
price_map['chicken wings uncooked'] = {'price': 0.90, 'uom': 'Piece'}

# Crab Whole: price is 16 AED/Kg (NOT per piece). Recipe uses 1 Piece.
# One piece of crab ~120g = 0.12 Kg
# 16 AED/Kg * 0.12 Kg/piece = 1.92 AED/piece
price_map['crab whole'] = {'price': 1.92, 'uom': 'Piece'}

# Vermicelli Noodles: bought raw at 28 AED/Kg, but 1 Kg raw -> 2 Kg cooked
# Recipes use COOKED weight, so effective cost = 28 / 2 = 14 AED per Kg (cooked)
price_map['vermicelli noodles'] = {'price': 14.00, 'uom': 'Kg'}

# Beef Tenderloin (India): AED 750 for 20 Kg = 37.50/Kg
price_map['beef tenderloin (india)'] = {'price': 37.50, 'uom': 'Kg'}

# Chicken: AED 13/Kg across the board
price_map['chicken breast (aurora)'] = {'price': 13.00, 'uom': 'Kg'}
price_map['chicken thigh boneless'] = {'price': 13.00, 'uom': 'Kg'}

# Korean Soybean Paste: AED 16.875/Kg
price_map['korean soybean paste'] = {'price': 16.875, 'uom': 'Kg'}

# Arwa water 500ml = 1 bottle
if 'arwa water' in price_map:
    price_map['arwa 500ml'] = price_map['arwa water']

# Step 3: UOM conversion factors for recipe-ingredient mismatches
UOM_CONVERSIONS = {
    ('Piece', 'Kg'): {
        'chicken wings uncooked': 0.06,   # ~60g per wing
        'chicken wings (pre-cooked)': 0.06,
        'crab whole': 0.12,               # ~120g per crab piece
    },
    ('Kg', 'Piece'): {},
}

def get_unit_price(ingredient_lower, recipe_uom):
    """Get unit price, handling UOM mismatches."""
    if ingredient_lower not in price_map:
        return 0, False

    p = price_map[ingredient_lower]
    price = p['price']
    price_uom = p['uom']

    if recipe_uom == price_uom:
        return price, True

    conv_key = (recipe_uom, price_uom)
    if conv_key in UOM_CONVERSIONS and ingredient_lower in UOM_CONVERSIONS[conv_key]:
        factor = UOM_CONVERSIONS[conv_key][ingredient_lower]
        return price * factor, True

    return price, True

# Step 4: Build SF recipe lookup by name
sf_by_name = {}
for r in recipes['semi_finished_recipes']:
    sf_by_name[r['dish_name'].strip().lower()] = r

# Step 5: Build finished recipe lookup (for combo/set meals)
finished_by_name = {}
for r in recipes['finished_recipes']:
    finished_by_name[r['dish_name'].strip().lower()] = r

# Step 6: Recipe-level ingredient overrides
# Soondubu Jjigae: replace Spicy Chili Paste - SF (0.300 Kg) with Gochugaru (0.060 Kg)
RECIPE_OVERRIDES = {
    'soondubu jjigae': {
        'remove': ['spicy chili paste - sf'],
        'add': [{'ingredient': 'Gochugaru', 'ep_qty': 0.060, 'uom': 'Kg',
                 'wastage_pct': 0, 'is_semi_finished_ref': False}]
    }
}

def get_recipe_ingredients(recipe):
    """Return ingredient list with any overrides applied."""
    dish_lower = recipe['dish_name'].strip().lower()
    ingredients = list(recipe['ingredients'])

    if dish_lower in RECIPE_OVERRIDES:
        override = RECIPE_OVERRIDES[dish_lower]
        remove_set = {x.lower() for x in override.get('remove', [])}
        ingredients = [ing for ing in ingredients
                       if ing['ingredient'].strip().lower() not in remove_set]
        ingredients.extend(override.get('add', []))

    return ingredients

# Step 7: Compute SF costs with dependency resolution
sf_costs = {}

def compute_sf_cost(sf_name_lower, depth=0):
    if sf_name_lower in sf_costs:
        return sf_costs[sf_name_lower]
    if depth > 10 or sf_name_lower not in sf_by_name:
        return 0

    recipe = sf_by_name[sf_name_lower]
    total_cost = 0
    total_yield = 0

    for ing in recipe['ingredients']:
        name_lower = ing['ingredient'].strip().lower()
        qty = ing['ep_qty']
        wastage = ing['wastage_pct'] / 100.0 if ing['wastage_pct'] else 0
        gross = qty / (1 - wastage) if 0 < wastage < 1 else qty
        total_yield += qty

        if ing['is_semi_finished_ref']:
            nested_cost = compute_sf_cost(name_lower, depth + 1)
            total_cost += gross * nested_cost
        else:
            unit_price, _ = get_unit_price(name_lower, ing['uom'])
            total_cost += gross * unit_price

    cost_per_unit = total_cost / total_yield if total_yield > 0 else total_cost
    sf_costs[sf_name_lower] = cost_per_unit
    return cost_per_unit

for sf_name in sf_by_name:
    compute_sf_cost(sf_name)

for sf_name, cost in sf_costs.items():
    price_map[sf_name] = {'price': cost, 'uom': 'Kg'}

# Print SF costs
print("=" * 60)
print("SEMI-FINISHED RECIPE COSTS (per unit)")
print("=" * 60)
for sf_name in sorted(sf_costs.keys()):
    recipe = sf_by_name[sf_name]
    print(f"  {recipe['dish_name']:<40s} AED {sf_costs[sf_name]:>8.4f}")
print()

# Step 8: Compute finished recipe costs
dish_cost_map = {}

def compute_dish_cost(recipe):
    total_cost = 0
    missing = []
    ingredients = get_recipe_ingredients(recipe)
    for ing in ingredients:
        name_lower = ing['ingredient'].strip().lower()
        qty = ing['ep_qty']
        wastage = ing['wastage_pct'] / 100.0 if ing['wastage_pct'] else 0
        gross = qty / (1 - wastage) if 0 < wastage < 1 else qty

        if name_lower in price_map:
            unit_price, _ = get_unit_price(name_lower, ing['uom'])
            total_cost += gross * unit_price
        elif name_lower in dish_cost_map:
            total_cost += gross * dish_cost_map[name_lower]
        else:
            missing.append(ing['ingredient'])
    return round(total_cost, 2), missing

# First pass
for r in recipes['finished_recipes']:
    cost, _ = compute_dish_cost(r)
    dish_cost_map[r['dish_name'].strip().lower()] = cost

# Second pass (resolve combo references)
for r in recipes['finished_recipes']:
    cost, _ = compute_dish_cost(r)
    dish_cost_map[r['dish_name'].strip().lower()] = cost

# Final output
print("=" * 80)
print(f"{'S.No.':<6s} {'Dish Name':<50s} {'Total Cost (AED)':>15s}")
print("=" * 80)

dish_costs = []
for idx, r in enumerate(recipes['finished_recipes'], 1):
    total_cost, missing = compute_dish_cost(r)
    dish_costs.append({
        'sno': idx,
        'dish_name': r['dish_name'],
        'total_cost': total_cost,
        'missing_ingredients': missing
    })
    warn = f"  [!] Missing: {', '.join(missing)}" if missing else ""
    print(f"  {idx:<4d}  {r['dish_name']:<50s} AED {total_cost:>8.2f}{warn}")

print("=" * 80)
main_dishes = [d for d in dish_costs if not any(x in d['dish_name'] for x in ['Set', 'Combo', 'Mineral'])]
avg = sum(d['total_cost'] for d in main_dishes) / len(main_dishes)
print(f"       {'Average (main dishes)':<50s} AED {avg:>8.2f}")
print(f"       {'Min':<50s} AED {min(d['total_cost'] for d in main_dishes):>8.2f}")
print(f"       {'Max':<50s} AED {max(d['total_cost'] for d in main_dishes):>8.2f}")

# Save
output = {
    'title': 'Korean Menu - Dish Costing',
    'method': 'Lowest canonical price per ingredient + SF recursive costing + wastage + UOM conversion',
    'generated_date': '2026-03-27',
    'notes': [
        'Chicken Wings Uncooked: 60g/wing, 15 AED/Kg = 0.90 AED/piece',
        'Crab Whole: 16 AED/Kg, ~400g/crab = 6.40 AED/piece',
        'Vermicelli Noodles: 28 AED/Kg raw, 1:2 cook ratio = 14 AED/Kg cooked',
        'Soondubu Jjigae: Spicy Chili Paste SF replaced with 60g Gochugaru',
        'Gyoza Wrapper: ~25 pieces per 140g pack = 0.26 AED/piece',
        'Tap Water: priced at AED 0',
    ],
    'sf_costs': {sf_by_name[k]['dish_name']: round(v, 4) for k, v in sf_costs.items()},
    'dishes': dish_costs
}
with open(r'E:\Cloud Kitchen\AI Teams\korean_dish_costing.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to korean_dish_costing.json")
