import json

with open(r'E:\Cloud Kitchen\AI Teams\korean_dish_costing.json', 'r') as f:
    costing = json.load(f)

dc = {}
for d in costing['dishes']:
    dc[d['dish_name'].lower().strip()] = d['total_cost']

combos = [
    {
        'name': 'Iftar Korean Rice Bowl Solo',
        'price': 72,
        'modifiers': [
            ('Choose your Bap', 1, [
                'Beef Bibimbap', 'Chicken Bibimbap', 'Shrimp Bibimbap',
                'Bulgogi Deopbap', 'Dak Deopbap', 'Gochujang Shrimp Deopbap',
            ]),
            ('Choose your Kimbap', 1, [
                'Beef Kimbap', 'Chicken Kimbap', 'Tuna Kimbap', 'Japchae & Shrimp Kimbap',
            ]),
            ('Choose Your Beverage', 1, [
                'Mineral Tap Water', 'Coca Cola', 'Coca Cola Zero', 'Fanta', 'Sprite', 'Sprite Zero',
            ]),
        ]
    },
    {
        'name': 'Iftar Korean Rice Bowl Duo',
        'price': 122,
        'modifiers': [
            ('Choose your Bap', 2, [
                'Beef Bibimbap', 'Chicken Bibimbap', 'Shrimp Bibimbap',
                'Bulgogi Deopbap', 'Dak Deopbap', 'Gochujang Shrimp Deopbap',
            ]),
            ('Choose your Kimbap', 2, [
                'Beef Kimbap', 'Chicken Kimbap', 'Tuna Kimbap', 'Japchae & Shrimp Kimbap',
            ]),
            ('Choose your Chicken', 1, [
                'Soy and Garlic Chicken', 'Yangnyeom Chicken', 'Korean Style Chicken',
                'Spicy Chicken', 'Honey Garlic Chicken',
            ]),
            ('Choose Your Beverage', 2, [
                'Mineral Tap Water', 'Coca Cola', 'Coca Cola Zero', 'Fanta', 'Sprite', 'Sprite Zero',
            ]),
        ]
    },
    {
        'name': 'Iftar Korean Rice Bowl Family of 4',
        'price': 193,
        'modifiers': [
            ('Choose your Bap', 4, [
                'Beef Bibimbap', 'Chicken Bibimbap', 'Shrimp Bibimbap',
                'Bulgogi Deopbap', 'Dak Deopbap', 'Gochujang Shrimp Deopbap',
            ]),
            ('Choose your Kimbap', 2, [
                'Beef Kimbap', 'Chicken Kimbap', 'Tuna Kimbap', 'Japchae & Shrimp Kimbap',
            ]),
            ('Choose your Chicken', 1, [
                'Soy and Garlic Chicken', 'Yangnyeom Chicken', 'Korean Style Chicken',
                'Spicy Chicken', 'Honey Garlic Chicken',
            ]),
            ('Choose Your Beverage', 4, [
                'Mineral Tap Water', 'Coca Cola', 'Coca Cola Zero', 'Fanta', 'Sprite', 'Sprite Zero',
            ]),
        ]
    },
    {
        'name': 'Ramadan Korean Feast 6 Servings',
        'price': 329,
        'modifiers': [
            ('Choose your Bap', 4, [
                'Beef Bibimbap', 'Chicken Bibimbap', 'Shrimp Bibimbap',
                'Bulgogi Deopbap', 'Dak Deopbap', 'Gochujang Shrimp Deopbap',
            ]),
            ('Choose your Japchae', 1, [
                'Japchae Beef', 'Japchae Chicken', 'Shrimp Japchae', 'Japchae Veg',
            ]),
            ('Choose your Kimbap', 2, [
                'Beef Kimbap', 'Chicken Kimbap', 'Tuna Kimbap', 'Japchae & Shrimp Kimbap',
            ]),
            ('Choose your Chicken', 1, [
                'Soy and Garlic Chicken', 'Yangnyeom Chicken', 'Korean Style Chicken',
                'Spicy Chicken', 'Honey Garlic Chicken',
            ]),
            ('Choose Your Beverage', 6, [
                'Mineral Tap Water', 'Coca Cola', 'Coca Cola Zero', 'Fanta', 'Sprite', 'Sprite Zero',
            ]),
        ]
    },
    {
        'name': 'Iftar Vegetarian Korean Bowl Feast',
        'price': 139,
        'modifiers': [
            ('Choose your Bap', 1, [
                'Tofu Bibimbap', 'Veg Bibimbap', 'Crispy Tofu Deopbap', 'Japchae Veg',
            ]),
            ('Choose your Kimbap', 1, [
                'Cheese and Veg Kimbap', 'Kimchi Kimbap',
            ]),
            ('Choose Your Beverage', 1, [
                'Mineral Tap Water', 'Coca Cola', 'Coca Cola Zero', 'Fanta', 'Sprite', 'Sprite Zero',
            ]),
        ]
    },
]

results = []
for combo in combos:
    total_min = 0.0
    total_max = 0.0

    for group_name, pick, options in combo['modifiers']:
        costs = [(opt, dc.get(opt.lower().strip(), 0)) for opt in options]
        costs.sort(key=lambda x: x[1])
        total_min += costs[0][1] * pick
        total_max += costs[-1][1] * pick

    results.append({
        'name': combo['name'],
        'price': combo['price'],
        'min_cost': round(total_min, 2),
        'max_cost': round(total_max, 2),
    })

with open(r'E:\Cloud Kitchen\AI Teams\ramadan_combo_costing.json', 'w') as f:
    json.dump(results, f, indent=2)

for r in results:
    print(f"{r['name']:<45s} | Sell: AED {r['price']:>6.0f} | Min: AED {r['min_cost']:>6.2f} | Max: AED {r['max_cost']:>6.2f}")
