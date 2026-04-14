import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'E:\Cloud Kitchen\AI Teams\indian_dish_costing.json', 'r') as f:
    ind = json.load(f)

dc = {}
for d in ind['dishes']:
    dc[d['dish'].lower().strip()] = d

combos_all = {
    'Tandoori Tribe': [
        {'name': 'Ramadan Solo Tandoori Iftar', 'sell': 98, 'items': [
            ('Tandoori Chicken (Half)', 1), ('Butter Chicken', 0.5), ('Jeera Rice', 0.67),
            ('Butter Naan', 2), ('Boondi Raita', 1),
        ]},
        {'name': 'Ramadan Couple Tandoori Iftar', 'sell': 165, 'items': [
            ('Tandoori Chicken (Half)', 1), ('Malai Chicken Tikka', 1), ('Butter Chicken', 0.83),
            ('Dal Makhani', 0.5), ('Ghee Rice', 1), ('Butter Naan', 4), ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Family Tandoori Iftar', 'sell': 255, 'items': [
            ('Tandoori Chicken (Half)', 1), ('Afghani Chicken (Half)', 1), ('Chicken Tikka', 1.33),
            ('Butter Chicken', 1.17), ('Dal Makhani', 0.67), ('Palak Paneer', 0.67),
            ('Kashmiri Pulao', 1), ('Garlic Naan', 6), ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Grand Tandoori Iftar', 'sell': 380, 'items': [
            ('Tandoori Chicken (Full)', 1), ('Chicken Tikka', 2), ('Malai Chicken Tikka', 1.33),
            ('Butter Chicken', 1.83), ('Chicken Tikka Masala', 1), ('Paneer Butter Masala', 1),
            ('Dal Makhani', 0.67), ('Kashmiri Pulao', 1.5), ('Garlic Naan', 8),
            ('Boondi Raita', 3), ('Green Salad', 2),
        ]},
        {'name': 'Ramadan Vegetarian Tandoori Iftar', 'sell': 90, 'items': [
            ('Paneer Tikka', 1), ('Dal Makhani', 0.4), ('Jeera Rice', 0.67),
            ('Butter Naan', 2), ('Boondi Raita', 1),
        ]},
    ],
    'Zaika Punjab': [
        {'name': 'Ramadan Solo Punjab Iftar', 'sell': 96, 'items': [
            ('Butter Chicken', 0.6), ('Paneer Butter Masala', 0.4), ('Ghee Rice', 0.67),
            ('Butter Naan', 2), ('Boondi Raita', 1),
        ]},
        {'name': 'Ramadan Couple Punjab Iftar', 'sell': 158, 'items': [
            ('Tandoori Chicken (Half)', 1), ('Butter Chicken', 0.83), ('Palak Paneer', 0.67),
            ('Kashmiri Pulao', 1), ('Butter Naan', 4), ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Family Punjab Iftar', 'sell': 268, 'items': [
            ('Chicken Tikka', 1), ('Paneer Tikka', 1), ('Mutton Rogan Josh', 1),
            ('Butter Chicken', 1.17), ('Shahi Paneer', 0.67), ('Dal Makhani', 0.67),
            ('Kashmiri Pulao', 1), ('Garlic Naan', 6), ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Grand Punjab Iftar', 'sell': 390, 'items': [
            ('Paneer Malai Tikka', 1.33), ('Chicken Tikka', 2), ('Mutton Rogan Josh', 1.5),
            ('Butter Chicken', 1.67), ('Paneer Butter Masala', 1), ('Dal Makhani', 1),
            ('Kashmiri Pulao', 1.5), ('Garlic Naan', 8), ('Boondi Raita', 3), ('Green Salad', 2),
        ]},
    ],
    'The Curry Club': [
        {'name': 'Ramadan Solo Curry Iftar', 'sell': 92, 'items': [
            ('Chicken Tikka Masala', 0.6), ('Dal Makhani', 0.4), ('Jeera Rice', 0.67),
            ('Garlic Naan', 2), ('Boondi Raita', 1),
        ]},
        {'name': 'Ramadan Couple Curry Iftar', 'sell': 148, 'items': [
            ('Butter Chicken', 0.83), ('Paneer Butter Masala', 0.67), ('Dal Tadka', 0.5),
            ('Kashmiri Pulao', 1), ('Garlic Naan', 4), ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Family Curry Iftar', 'sell': 235, 'items': [
            ('Mutton Rogan Josh', 1), ('Butter Chicken', 1.17), ('Paneer Butter Masala', 1),
            ('Dal Makhani', 0.67), ('Kashmiri Pulao', 1), ('Garlic Naan', 6),
            ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Grand Curry Iftar', 'sell': 355, 'items': [
            ('Chicken Tikka', 1), ('Mutton Rogan Josh', 1.5), ('Butter Chicken', 1.67),
            ('Paneer Butter Masala', 1), ('Dal Makhani', 1), ('Kadhai Paneer', 0.67),
            ('Kashmiri Pulao', 1.5), ('Garlic Naan', 8), ('Boondi Raita', 3), ('Green Salad', 2),
        ]},
    ],
    'Smoky Tandoor': [
        {'name': 'Ramadan Solo Smoky Iftar', 'sell': 95, 'items': [
            ('Chicken Tikka', 1), ('Butter Chicken', 0.6), ('Jeera Rice', 0.67),
            ('Garlic Naan', 2), ('Boondi Raita', 1),
        ]},
        {'name': 'Ramadan Couple Smoky Iftar', 'sell': 155, 'items': [
            ('Malai Chicken Tikka', 1), ('Paneer Tikka', 1), ('Butter Chicken', 0.83),
            ('Dal Makhani', 0.5), ('Veg Pulao', 1), ('Garlic Naan', 4), ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Family Smoky Iftar', 'sell': 245, 'items': [
            ('Chicken Tikka', 1), ('Malai Chicken Tikka', 1), ('Paneer Tikka', 1),
            ('Butter Chicken', 1.17), ('Mutton Rogan Josh', 1), ('Paneer Butter Masala', 1),
            ('Dal Makhani', 0.67), ('Kashmiri Pulao', 1), ('Garlic Naan', 6),
            ('Boondi Raita', 2), ('Green Salad', 1),
        ]},
        {'name': 'Ramadan Grand Smoky Iftar', 'sell': 365, 'items': [
            ('Paneer Malai Tikka', 1.33), ('Chicken Tikka', 1.5), ('Malai Chicken Tikka', 1),
            ('Chicken Seekh Kebab', 1), ('Butter Chicken', 1.67), ('Mutton Rogan Josh', 1.5),
            ('Paneer Butter Masala', 1), ('Dal Makhani', 1),
            ('Kashmiri Pulao', 1.5), ('Garlic Naan', 8), ('Boondi Raita', 3), ('Green Salad', 2),
        ]},
    ],
}

results = []
for brand, combos in combos_all.items():
    print(f"=== {brand} ===")
    for combo in combos:
        total = 0
        missing = []
        for dish_name, qty in combo['items']:
            dl = dish_name.lower().strip()
            if dl in dc:
                total += dc[dl]['food_cost'] * qty
            else:
                missing.append(dish_name)
        total += 1.50  # combo packaging
        sell = combo['sell']
        mgn = sell - total
        mgn_pct = (mgn / sell * 100) if sell > 0 else 0
        miss_str = f" [!{','.join(missing)}]" if missing else ""
        print(f"  {combo['name']:<50s} Sell:{sell:>5.0f} | Cost:{total:>7.2f} | Margin:{mgn:>7.2f} ({mgn_pct:.1f}%){miss_str}")
        results.append({
            'brand': brand, 'name': combo['name'], 'sell': sell,
            'cost': round(total, 2),
        })
    print()

with open(r'E:\Cloud Kitchen\AI Teams\indian_ramadan_combo_costing.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved to indian_ramadan_combo_costing.json")
