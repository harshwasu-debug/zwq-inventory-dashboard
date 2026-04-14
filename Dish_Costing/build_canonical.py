import json, re

with open(r'E:\Cloud Kitchen\AI Teams\product_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def parse_buying_unit(bu_str, base_unit, price, item_name):
    bu = str(bu_str).strip()
    base = str(base_unit).strip()

    if base in ('Kg', 'kg', 'KG'):
        target = 'Kg'
    elif base in ('L', 'l', 'Ltr', 'ltr'):
        target = 'L'
    elif base in ('Piece', 'piece', 'pcs', 'PCS', 'Pcs'):
        target = 'Piece'
    else:
        target = 'Kg'

    bu_lower = bu.lower().strip()

    # Multi-pack: 6x 3 Kg, 4x500g, 10x1KG, 5x200 Gm, 16x400gm
    multi_match = re.match(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(kg|kgs|g|gm|gms|ltr|lt|l|ml|pcs|piece|roll)?\s*$', bu_lower)
    if multi_match:
        count = float(multi_match.group(1))
        per_unit = float(multi_match.group(2))
        unit = multi_match.group(3) or ''
        qty = count * per_unit
        if unit in ('g', 'gm', 'gms'):
            qty = qty / 1000.0
        elif unit in ('ml',):
            qty = qty / 1000.0
        elif unit in ('roll',):
            return count * per_unit, 'Piece'
        return qty, target

    if bu_lower in ('kg', 'kgs'):
        return 1.0, 'Kg'
    if bu_lower in ('pcs',):
        return 1.0, 'Piece'
    if bu_lower == 'carton':
        return 1.0, 'Piece'

    if 'bnh' in bu_lower:
        num = re.match(r'(\d+\.?\d*)', bu_lower)
        return float(num.group(1)) if num else 1.0, target

    if 'box' in bu_lower and 'pcs' not in bu_lower:
        if 'egg' in item_name.lower():
            return 360.0, 'Piece'
        return 1.0, target

    if 'ctn' in bu_lower:
        num = re.match(r'(\d+\.?\d*)', bu_lower)
        return float(num.group(1)) if num else 1.0, target

    if 'set' in bu_lower:
        return 1.0, 'Piece'

    if 'tray' in bu_lower:
        if 'egg' in item_name.lower():
            return 30.0, 'Piece'
        return 1.0, target

    if 'pkt' in bu_lower:
        num = re.match(r'(\d+\.?\d*)', bu_lower)
        return float(num.group(1)) if num else 1.0, target

    # 100pcs Box
    pcs_box = re.match(r'(\d+\.?\d*)\s*pcs\s*box', bu_lower)
    if pcs_box:
        return float(pcs_box.group(1)), 'Piece'

    # 3Ltr Pack
    ltr_pack = re.match(r'(\d+\.?\d*)\s*ltr\s*pack', bu_lower)
    if ltr_pack:
        return float(ltr_pack.group(1)), 'L'

    # 52 Slices
    if 'slice' in bu_lower:
        num = re.match(r'(\d+\.?\d*)', bu_lower)
        if num:
            if target == 'Kg':
                return float(num.group(1)), 'Kg'
            return float(num.group(1)), 'Piece'

    # 6 Piece
    piece_match = re.match(r'(\d+\.?\d*)\s*piece', bu_lower)
    if piece_match:
        return float(piece_match.group(1)), 'Piece'

    # Standard: number + unit
    match = re.match(r'(\d+\.?\d*)\s*(kg|kgs|g|gm|gms|gram|grams|ltr|ltrs|lt|l|ml|pcs|piece|pieces|pc)\s*$', bu_lower)
    if match:
        qty = float(match.group(1))
        unit = match.group(2)
        if unit in ('g', 'gm', 'gms', 'gram', 'grams'):
            return qty / 1000.0, 'Kg' if target == 'Kg' else target
        elif unit in ('ml',):
            return qty / 1000.0, 'L' if target == 'L' else target
        elif unit in ('kg', 'kgs'):
            return qty, 'Kg'
        elif unit in ('ltr', 'ltrs', 'lt', 'l'):
            return qty, 'L'
        elif unit in ('pcs', 'piece', 'pieces', 'pc'):
            return qty, 'Piece'

    # Case-insensitive for Gm, ML etc
    match2 = re.match(r'(\d+\.?\d*)\s*(Kg|KG|Kgs|Gm|GM|Gms|GMS|Ltr|LTR|Lt|ML|Pcs|PCS|Piece)\s*$', bu.strip(), re.IGNORECASE)
    if match2:
        qty = float(match2.group(1))
        unit = match2.group(2).lower()
        if unit in ('gm', 'gms'):
            return qty / 1000.0, 'Kg' if target == 'Kg' else target
        elif unit == 'ml':
            return qty / 1000.0, 'L' if target == 'L' else target
        elif unit in ('kg', 'kgs'):
            return qty, 'Kg'
        elif unit in ('ltr',):
            return qty, 'L'
        elif unit in ('pcs', 'piece'):
            return qty, 'Piece'

    # Plain number (like '3.78')
    plain_num = re.match(r'^(\d+\.?\d*)\s*$', bu.strip())
    if plain_num:
        return float(plain_num.group(1)), target

    # 800 ML
    ml_match = re.match(r'(\d+\.?\d*)\s*ml', bu_lower)
    if ml_match:
        return float(ml_match.group(1)) / 1000.0, 'L'

    # Fallback: extract number
    num = re.match(r'(\d+\.?\d*)', bu_lower)
    if num:
        return float(num.group(1)), target

    return 1.0, target


# Process all products
items = {}

for p in data['products']:
    name = p.get('Base_Item_Ingredient_Name', '')
    if not name:
        continue

    bu = p.get('Buying_Unit', '')
    base_unit = p.get('Base_Unit', 'Kg')
    price = p.get('Price_Per_Buying_Unit', 0)
    supplier = p.get('Supplier_Name', '')
    supplier_item = p.get('Supplier_Item_Name', '')
    supplier_code = p.get('Supplier_Item_Code', '')
    category = p.get('Main_Category', '')
    sub_cat = p.get('Sub_Category', '')
    taxable = p.get('Is_this_item_taxable?', '')
    cogs = p.get('Does_this_item_affect_COGS_Optional:_yes_no', '')

    try:
        qty, uom = parse_buying_unit(bu, base_unit, price, name)
        price_per_unit = round(price / qty, 4) if qty > 0 else price
    except:
        continue

    key = name.strip()

    entry = {
        'supplier': supplier,
        'supplier_item': supplier_item,
        'supplier_code': str(supplier_code),
        'buying_unit': str(bu),
        'buying_price': price,
        'qty_in_base': round(qty, 4),
        'price_per_unit': price_per_unit
    }

    if key not in items:
        items[key] = {
            'ingredient': key,
            'category': category,
            'sub_category': sub_cat,
            'uom': uom,
            'taxable': taxable,
            'affects_cogs': cogs,
            'suppliers': []
        }
    items[key]['suppliers'].append(entry)

# Build canonical list
canonical = []
for key, item in sorted(items.items()):
    suppliers_sorted = sorted(item['suppliers'], key=lambda x: x['price_per_unit'])
    best = suppliers_sorted[0]
    canonical.append({
        'ingredient': item['ingredient'],
        'category': item['category'],
        'sub_category': item['sub_category'],
        'uom': item['uom'],
        'taxable': item['taxable'],
        'affects_cogs': item['affects_cogs'],
        'lowest_price_per_unit': best['price_per_unit'],
        'best_supplier': best['supplier'],
        'best_supplier_item': best['supplier_item'],
        'best_supplier_code': best['supplier_code'],
        'best_buying_unit': best['buying_unit'],
        'best_buying_price': best['buying_price'],
        'supplier_count': len(suppliers_sorted),
        'all_suppliers': [{
            'supplier': s['supplier'],
            'supplier_item': s['supplier_item'],
            'supplier_code': s['supplier_code'],
            'buying_unit': s['buying_unit'],
            'buying_price': s['buying_price'],
            'qty_in_base': s['qty_in_base'],
            'price_per_unit': s['price_per_unit']
        } for s in suppliers_sorted]
    })

output = {
    'title': 'Canonical Price List - Cloud Kitchen Ingredients',
    'description': 'Lowest price per standardized unit (Kg/L/Piece) for each ingredient across all suppliers',
    'generated_date': '2026-03-27',
    'total_unique_ingredients': len(canonical),
    'uom_legend': {
        'Kg': 'Price per Kilogram (AED)',
        'L': 'Price per Litre (AED)',
        'Piece': 'Price per piece/unit (AED)'
    },
    'items': canonical
}

out_path = r'E:\Cloud Kitchen\AI Teams\canonical_price_list.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False, default=str)

print(f"Created canonical price list: {len(canonical)} unique ingredients")
print()

cats = {}
for c in canonical:
    cats[c['category']] = cats.get(c['category'], 0) + 1
print("By category:")
for k, v in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

uoms = {}
for c in canonical:
    uoms[c['uom']] = uoms.get(c['uom'], 0) + 1
print("\nBy UOM:")
for k, v in sorted(uoms.items()):
    print(f"  {k}: {v}")

multi = [c for c in canonical if c['supplier_count'] > 1]
print(f"\nItems with multiple suppliers ({len(multi)}):")
print(f"{'Ingredient':<40s} | {'UOM':<5s} | {'Best':>10s} | {'Worst':>10s} | {'Saving':>10s}")
print("-" * 85)
for m in multi[:20]:
    prices = [s['price_per_unit'] for s in m['all_suppliers']]
    saving = max(prices) - min(prices)
    print(f"  {m['ingredient']:<38s} | {m['uom']:<5s} | AED {min(prices):>6.2f} | AED {max(prices):>6.2f} | AED {saving:>6.2f}")
