import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'E:\Cloud Kitchen\AI Teams\ramadan_snare_menus_structured.json', 'r', encoding='utf-8') as f:
    menus = json.load(f)

with open(r'E:\Cloud Kitchen\AI Teams\american_dish_costing.json', 'r') as f:
    costing = json.load(f)

dc = {}
for d in costing['dishes']:
    dc[d['dish'].lower().strip()] = d['cost']

# Add Veggie Sticks recipe from user
veg_cost = ((0.05/0.85)*3.75 + (0.06/0.90)*2.00 + (0.035/0.88)*9.50
            + (0.035/0.88)*9.50 + (0.025/0.88)*9.50 + 0.045*15.0)
dc['veggie sticks'] = round(veg_cost, 2)

# Sauce -> full dish name mapping
chicken_burger = {
    'classic burger': 'crispy chicken burger',
    'crunchy bbq burger': 'chicken crunchy slaw burger',
    'slaw burger': 'chicken house slaw (portion) burger',
    'buffalo burger': 'chicken buffalo burger',
    'texas burger': 'crispy chicken burger',
    'mushroom truffle burger': 'chicken truffle burger',
    'double cheese burger': 'beef double cheese burger',
    'bacon burger': 'bacon beef burger',
    'dynamite burger': 'chicken dynamite burger',
    'honey mustard burger': 'chicken honey mustard burger',
    'mexican crunch burger': 'mexican crunch chicken burger',
    'italian burger': 'italian chicken burger',
}
beef_burger = {
    'classic burger': 'classic beef burger',
    'crunchy bbq burger': 'cowboy beef burger',
    'slaw burger': 'beef slaw burger',
    'buffalo burger': 'buffalo beef burger',
    'texas burger': 'texas beef burger',
    'mushroom truffle burger': 'mushroom truffle beef burger',
    'double cheese burger': 'beef double cheese burger',
    'bacon burger': 'bacon beef burger',
    'dynamite burger': 'chicken dynamite burger',
    'honey mustard burger': 'chicken honey mustard burger',
    'mexican crunch burger': 'mexican crunch beef burger',
    'italian burger': 'italian chicken burger',
}
chicken_slider = {
    'classic sliders': 'crispy chicken sliders',
    'crunchy bbq sliders': 'chicken crunchy slaw sliders',
    'slaw sliders': 'chicken house slaw (portion) sliders',
    'buffalo sliders': 'chicken buffalo sliders',
    'texas sliders': 'crispy chicken sliders',
    'mushroom truffle sliders': 'chicken truffle sliders',
    'double cheese sliders': 'beef double cheese sliders',
    'bacon sliders': 'bacon beef sliders',
    'dynamite sliders': 'chicken dynamite sliders',
    'honey mustard sliders': 'chicken honey mustard sliders',
    'mexican crunch sliders': 'mexican crunch chicken sliders',
    'italian sliders': 'italian chicken sliders',
}
beef_slider = {
    'classic sliders': 'classic beef sliders',
    'crunchy bbq sliders': 'cowboy beef sliders',
    'slaw sliders': 'beef slaw sliders',
    'buffalo sliders': 'buffalo beef sliders',
    'texas sliders': 'texas beef sliders',
    'mushroom truffle sliders': 'mushroom truffle beef sliders',
    'double cheese sliders': 'beef double cheese sliders',
    'bacon sliders': 'bacon beef sliders',
    'dynamite sliders': 'chicken dynamite sliders',
    'honey mustard sliders': 'chicken honey mustard sliders',
    'mexican crunch sliders': 'mexican crunch beef sliders',
    'italian sliders': 'italian chicken sliders',
}
wing_map = {
    'plain': 'plain wings', 'smokey bbq': 'smokey bbq wings',
    'tangy buffalo': 'tangy buffalo wings', 'hot honey': 'hot honey wings',
    'sesame & sweet': 'sesame & sweet wings', 'chili hoisin': 'chili hoisin wings',
    'garlic parmesan': 'garlic parmesan wings', 'honey mustard': 'honey mustard wings',
    'dynamite': 'dynamite wings',
}

all_results = []

for brand_name, brand_data in menus.items():
    is_wing = 'wing' in brand_name.lower() or 'fury' in brand_name.lower()
    is_slider = 'slider' in brand_name.lower() or 'juicy' in brand_name.lower()

    for item in brand_data['items']:
        combo = item['item_name_en']
        sell = item['item_price_aed']
        min_c = 0
        max_c = 0
        sauce_picks = 1
        has_protein_group = False

        # First pass: find pick counts
        for mg in item['modifier_groups']:
            gn = mg['group_name'].lower()
            if 'sauce' in gn or 'filling' in gn:
                sauce_picks = mg['min_picks'] or 1

        for mg in item['modifier_groups']:
            gn = mg['group_name'].lower()
            picks = mg['min_picks'] or 1
            mandatory = mg['mandatory_optional'] == 'Mandatory'

            if 'drink' in gn:
                min_c += 0.44 * picks
                max_c += 2.04 * picks

            elif ('burger' in gn or 'slider' in gn) and not is_wing and 'sauce' not in gn:
                # Protein choice - skip here, handled in sauce group
                has_protein_group = True

            elif 'sauce' in gn or 'filling' in gn:
                # Combine protein x sauce
                ch_map = chicken_slider if is_slider else chicken_burger
                bf_map = beef_slider if is_slider else beef_burger
                all_costs = []
                for o in mg['options']:
                    on = o['option_en'].lower()
                    ch_dish = ch_map.get(on, '')
                    bf_dish = bf_map.get(on, '')
                    ch_cost = dc.get(ch_dish, 5.5)
                    bf_cost = dc.get(bf_dish, 11.0)
                    all_costs.append(ch_cost)
                    all_costs.append(bf_cost)
                min_c += min(all_costs) * sauce_picks
                max_c += max(all_costs) * sauce_picks

            elif 'wing' in gn and is_wing:
                # Scale by wing count
                import re
                nums = re.findall(r'(\d+)\s*Wing', combo)
                scale = int(nums[0]) / 5 if nums else 1
                w_costs = [dc.get(wing_map.get(o['option_en'].lower(), ''), 7.5) for o in mg['options']]
                min_c += min(w_costs) * scale
                max_c += max(w_costs) * scale

            elif 'add' in gn:
                # Optional add-ons: not mandatory in most cases
                # Include 0 for min (customer can skip)
                pass

        min_mgn = sell - max_c
        max_mgn = sell - min_c
        min_pct = (min_mgn / sell * 100) if sell else 0
        max_pct = (max_mgn / sell * 100) if sell else 0

        all_results.append({
            'brand': brand_name, 'combo': combo, 'sell': sell,
            'min_cost': round(min_c, 2), 'max_cost': round(max_c, 2),
            'min_margin': round(min_mgn, 2), 'max_margin': round(max_mgn, 2),
            'min_pct': round(min_pct, 1), 'max_pct': round(max_pct, 1),
        })

# Print
hdr = f"{'Brand':<25s} | {'Combo':<45s} | {'Sell':>5s} | {'Min Cost':>8s} | {'Max Cost':>8s} | {'Min Mgn':>7s} | {'Max Mgn':>7s} | {'Worst%':>6s} | {'Best%':>6s}"
print(hdr)
print('=' * len(hdr))

last = ''
for r in all_results:
    b = r['brand'] if r['brand'] != last else ''
    last = r['brand']
    print(f"{b:<25s} | {r['combo']:<45s} | {r['sell']:>5.0f} | {r['min_cost']:>8.2f} | {r['max_cost']:>8.2f} | {r['min_margin']:>7.2f} | {r['max_margin']:>7.2f} | {r['min_pct']:>5.1f}% | {r['max_pct']:>5.1f}%")

with open(r'E:\Cloud Kitchen\AI Teams\ramadan_combo_costing_all_brands.json', 'w') as f:
    json.dump(all_results, f, indent=2)
print("\nSaved to ramadan_combo_costing_all_brands.json")
