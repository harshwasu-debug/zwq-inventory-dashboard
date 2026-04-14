import json

with open(r'E:\Cloud Kitchen\AI Teams\canonical_price_list.json', 'r') as f:
    prices = json.load(f)
with open(r'E:\Cloud Kitchen\AI Teams\korean_recipes.json', 'r') as f:
    recipes = json.load(f)

# Build price lookup: ingredient name (lower) -> {price per unit, uom}
price_map = {}
for item in prices['items']:
    price_map[item['ingredient'].strip().lower()] = {
        'price': item['price_per_unit'],
        'uom': item['uom']
    }

# Manual prices for items missing from canonical list
manual_prices = {
    'tap water': {'price': 0.0, 'uom': 'L'},
    'arwa 500ml': {'price': 0.44, 'uom': 'Piece'},
    'coca cola': {'price': 2.04, 'uom': 'Piece'},
    'chunjang (korean black bean paste)': {'price': 15.0, 'uom': 'Kg'},
    'danmuji (pickled radish)': {'price': 8.0, 'uom': 'Kg'},
    'korean soybean paste': {'price': 12.0, 'uom': 'Kg'},
}
price_map.update(manual_prices)

# UOM conversion overrides for recipe ingredients where recipe UOM != price list UOM
# Chicken Wings: recipe uses Piece, price list has Kg. ~100g per wing piece
# Gyoza Wrapper: 140g pack = ~28 wrappers, price 6.5 per pack -> ~0.23 per piece
# Crab Whole: recipe uses Piece (~0.3kg per crab), price list has Kg at 16/Kg
uom_overrides = {
    'chicken wings uncooked': {'price_per_piece': 15.0 * 0.1, 'uom': 'Piece'},  # ~100g per wing = 1.50/pc
    'chicken wings (pre-cooked)': {'price_per_piece': 10.5 * 0.1, 'uom': 'Piece'},  # ~100g per wing
    'gyoza wrapper': {'price_per_piece': 6.5 / 28, 'uom': 'Piece'},  # 140g pack ~28 wrappers
    'crab whole': {'price_per_piece': 16.0 * 0.3, 'uom': 'Piece'},  # ~300g per crab
}


def get_ingredient_cost(ing):
    """Get cost for a single ingredient line, handling UOM mismatches."""
    name = ing['ingredient'].strip()
    name_lower = name.lower()
    qty = ing['ep_qty']
    uom = ing['uom'].strip() if ing['uom'] else ''
    wastage = ing['wastage_pct'] / 100.0 if ing['wastage_pct'] else 0

    # Actual quantity needed accounting for wastage
    if 0 < wastage < 1:
        actual_qty = qty / (1 - wastage)
    else:
        actual_qty = qty

    # Check UOM overrides first (recipe uses Piece but price list uses Kg)
    if name_lower in uom_overrides and uom in ('Piece', 'piece'):
        return actual_qty * uom_overrides[name_lower]['price_per_piece']

    if name_lower in price_map:
        return actual_qty * price_map[name_lower]['price']

    return None


# ============================================================
# Step 1: Cost semi-finished recipes, add to price_map
# ============================================================
sf_costs = {}
for r in recipes['semi_finished_recipes']:
    total = 0
    total_yield_kg = 0
    total_yield_l = 0

    for ing in r['ingredients']:
        cost = get_ingredient_cost(ing)
        if cost is not None:
            total += cost

        # Track yield by dominant UOM
        uom = ing['uom'].strip() if ing['uom'] else ''
        if uom in ('Kg', 'kg', 'g'):
            total_yield_kg += ing['ep_qty']
        elif uom in ('L', 'l', 'ml'):
            total_yield_l += ing['ep_qty']

    sf_costs[r['dish_name']] = total

    # Determine yield and price per unit
    total_yield = total_yield_kg if total_yield_kg > 0 else total_yield_l
    if total_yield <= 0:
        total_yield = sum(ing['ep_qty'] for ing in r['ingredients'])

    price_per_unit = total / total_yield if total_yield > 0 else total

    # Add to price_map for use in finished recipes
    price_map[r['dish_name'].strip().lower()] = {
        'price': price_per_unit,
        'uom': 'Kg'
    }

# ============================================================
# Step 2: Cost finished recipes (excluding combos first)
# ============================================================
dish_costs = {}

# First pass: cost all non-combo dishes
for r in recipes['finished_recipes']:
    is_combo = any(
        not ing['is_semi_finished_ref']
        and ing['uom'] in ('Portion', 'portion')
        for ing in r['ingredients']
    )
    if is_combo:
        continue

    total = 0
    for ing in r['ingredients']:
        cost = get_ingredient_cost(ing)
        if cost is not None:
            total += cost

    dish_costs[r['dish_name'].strip().lower()] = total

# Add finished dish costs to price_map for combo references
for name, cost in dish_costs.items():
    price_map[name] = {'price': cost, 'uom': 'Piece'}

# Also add banchan side dish costs from their finished recipe costs
# House Kimchi, Sigumchi Namul, Kongnamul Muchim, Danmuji

# Second pass: cost combo/set meals
for r in recipes['finished_recipes']:
    is_combo = any(
        not ing['is_semi_finished_ref']
        and ing['uom'] in ('Portion', 'portion')
        for ing in r['ingredients']
    )
    if not is_combo:
        continue

    total = 0
    for ing in r['ingredients']:
        name_lower = ing['ingredient'].strip().lower()
        uom = ing['uom'].strip() if ing['uom'] else ''
        qty = ing['ep_qty']

        if uom in ('Portion', 'portion'):
            # Reference to another finished dish
            if name_lower in dish_costs:
                total += dish_costs[name_lower] * qty
            else:
                # Try price_map fallback
                if name_lower in price_map:
                    total += price_map[name_lower]['price'] * qty
        else:
            cost = get_ingredient_cost(ing)
            if cost is not None:
                total += cost

    dish_costs[r['dish_name'].strip().lower()] = total

# ============================================================
# Step 3: Print final costing table
# ============================================================
print("=" * 70)
print(f"{'S.No.':<6} {'Dish Name':<45} {'Total Cost (AED)':>15}")
print("=" * 70)

sno = 1
output = []
for r in recipes['finished_recipes']:
    name = r['dish_name']
    cost = dish_costs.get(name.strip().lower(), 0)
    print(f"{sno:<6} {name:<45} {cost:>14.2f}")
    output.append({
        's_no': sno,
        'dish_name': name,
        'recipe_code': r['recipe_code'],
        'total_cost_aed': round(cost, 2)
    })
    sno += 1

print("=" * 70)

with open(r'E:\Cloud Kitchen\AI Teams\korean_dish_costing.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to korean_dish_costing.json")
