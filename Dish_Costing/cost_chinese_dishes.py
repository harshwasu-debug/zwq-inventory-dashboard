import csv, json, sys, io, openpyxl
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

with open(r"E:\Cloud Kitchen\AI Teams\canonical_price_list.json", "r") as f:
    prices_data = json.load(f)

price_map = {}
for item in prices_data["items"]:
    price_map[item["ingredient"].strip().lower()] = {
        "price": item["price_per_unit"], "uom": item["uom"]
    }

# User corrections
price_map["beef tenderloin (india)"] = {"price": 37.50, "uom": "Kg"}
price_map["chicken breast (aurora)"] = {"price": 13.00, "uom": "Kg"}
price_map["chicken thigh boneless"] = {"price": 13.00, "uom": "Kg"}
price_map["chicken wings uncooked"] = {"price": 13.00, "uom": "Kg"}
price_map["beef mince"] = {"price": 43.00, "uom": "Kg"}
price_map["tap water"] = {"price": 0, "uom": "L"}

alias = {
    "cooking oil": "oil vegetable",
    "chilli whole dry": "chilli whole",
    "salt / msg": "salt",
    "salt / msg / pepper": "salt",
    "salt / pepper / msg": "salt",
    "salt / white pepper": "salt",
    "soy sauce (light)": "soy sauce",
    "soy sauce (light/red)": "soy sauce",
    "curry powder (chicken masala)": "chicken masala",
    "fried noodles": "vermicelli noodles",
    "broccoli/baby corn/carrot": "broccoli",
    "veg petals-sf (shredded)": "veg petals-sf",
    "beef strips-sf": "beef tenderloin (india)",  # pre-cut beef strips ~same price
    "fried shrimp base-sf": "shrimp",  # breaded shrimp base
}

# Piece-weight items (Kg per piece for items priced per Kg but used as pieces)
piece_weights = {
    "spring roll chicken": 0.030,    # ~30g per roll
    "spring roll vegetable": 0.030,  # ~30g per roll
    "chicken lollipop": 0.050,       # ~50g per lollipop
    "gyoza wrapper": None,           # special: 0.232 AED/piece (pack of ~28)
    "veg manchurian balls-sf": 0.030,  # ~30g per ball
    "momo filling chicken-sf": 0.020,  # portion used per momo (handled in SF)
    "momo filling veg-sf": 0.020,
    "momo filling prawn-sf": 0.020,
}

def gprice(name, uom="Kg", qty=1):
    n = name.strip().lower()

    # Piece weight conversion
    if uom == "Piece" and n in piece_weights:
        if piece_weights[n] is None:
            # Fixed price per piece
            if n == "gyoza wrapper":
                return 0.232 * qty
        else:
            pw = piece_weights[n]
            if n in price_map:
                return price_map[n]["price"] * pw * qty
            if n in alias and alias[n] in price_map:
                return price_map[alias[n]]["price"] * pw * qty

    if n in price_map:
        return price_map[n]["price"] * qty
    if n in alias and alias[n] in price_map:
        return price_map[alias[n]]["price"] * qty
    return None

# Read CSV
with open(r"C:\Users\harsh\Desktop\Cloud Kitchen\Brands Home\Chinese Brands\Chinese Recipes.csv",
          "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    next(reader)
    rows = list(reader)

sf = {}
current = ""
for r in rows:
    if r[0].strip():
        current = r[0].strip()
    if not current or not r[1].strip():
        continue
    w_str = r[4].strip().replace("%", "") if r[4] else "0"
    try:
        w_val = float(w_str)
    except:
        w_val = 0
    sf.setdefault(current, []).append({
        "i": r[1].strip(),
        "q": float(r[2]) if r[2] else 0,
        "u": r[3].strip(),
        "w": w_val,
    })

# Compute SF costs
sf_cost = {}
for _ in range(10):
    changed = False
    for name, ings in sf.items():
        if name in sf_cost:
            continue
        cost = 0; yld = 0; ok = True
        for ig in ings:
            q = ig["q"]; w = ig["w"] / 100
            g = q / (1 - w) if 0 < w < 1 else q
            sf_match = None
            for sn in sf_cost:
                if sn.lower() == ig["i"].lower():
                    sf_match = sn; break
            if sf_match:
                cost += g * sf_cost[sf_match]["ppu"]
            else:
                unresolved = any(sn.lower() == ig["i"].lower() and sn not in sf_cost for sn in sf)
                if unresolved:
                    ok = False; break
                p = gprice(ig["i"])
                if p is not None:
                    cost += g * p
                else:
                    cost += 0  # missing
            yld += q
        if ok:
            sf_cost[name] = {
                "total": round(cost, 4), "yield": round(yld, 4),
                "ppu": round(cost / yld, 4) if yld > 0 else cost,
            }
            changed = True
    if not changed:
        break

print("SF Costs:")
for k, v in sorted(sf_cost.items()):
    print(f"  {k:<35s} total={v['total']:>8.2f} yield={v['yield']:>6.2f} ppu={v['ppu']:>8.2f}/Kg")

# ============================================================
# Read finished recipes CSV
# ============================================================
with open(r"C:\Users\harsh\Desktop\Cloud Kitchen\Brands Home\Chinese Brands\Chinese Recipes - Finished Recipe.csv",
          "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    next(reader)
    fin_rows = list(reader)

fin = {}; fin_order = []
cur_cat = ""; cur_dish = ""
for r in fin_rows:
    cat = r[0].strip(); dish = r[1].strip(); ing = r[2].strip()
    qty_s = r[3].strip(); uom = r[4].strip()
    w_s = r[5].strip().replace("%", "") if r[5] else "0"
    if cat: cur_cat = cat
    if dish: cur_dish = dish
    if not cur_dish or not ing: continue
    try: qty = float(qty_s)
    except: qty = 0
    try: w = float(w_s)
    except: w = 0
    # Convert g->Kg, ml->L, normalize piece
    if uom.lower() in ("g", "gm", "gms"):
        qty /= 1000; uom = "Kg"
    elif uom.lower() == "ml":
        qty /= 1000; uom = "L"
    elif uom.lower() in ("piece", "pc", "pcs"):
        uom = "Piece"
    if cur_dish not in fin:
        fin[cur_dish] = {"cat": cur_cat, "ings": []}
        fin_order.append(cur_dish)
    fin[cur_dish]["ings"].append({"i": ing, "q": qty, "u": uom, "w": w})

# Cost finished dishes
fin_results = []; fin_missing = set()
for dn in fin_order:
    data = fin[dn]; cost = 0; miss = []
    for ig in data["ings"]:
        q = ig["q"]; w = ig["w"] / 100
        g = q / (1 - w) if 0 < w < 1 else q
        il = ig["i"].lower()
        sf_match = None
        for sn in sf_cost:
            if sn.lower() == il or sn.lower().rstrip() == il.rstrip():
                sf_match = sn; break
        # Also try with -SF suffix
        if not sf_match:
            for sn in sf_cost:
                sn_base = sn.lower().replace("-sf", "").strip()
                il_base = il.replace("-sf", "").strip()
                if sn_base == il_base:
                    sf_match = sn; break
        if sf_match:
            # If UOM is Piece and it's a batch SF, use ppu * estimated portion weight
            if ig["u"] == "Piece":
                # For momo fillings etc used as portions: 1 piece ~ portion in Kg
                # Use ppu (per Kg) * assumed portion weight
                # Veg Manchurian Balls: ~30g per ball
                portion_kg = 0.030  # default momo/ball portion
                cost += g * sf_cost[sf_match]["ppu"] * portion_kg
            else:
                cost += g * sf_cost[sf_match]["ppu"]
        else:
            p = gprice(ig["i"], ig["u"], g)
            if p is not None:
                cost += p
            else:
                miss.append(ig["i"]); fin_missing.add(ig["i"])
    fin_results.append({"dish": dn, "cat": data["cat"], "cost": round(cost, 2), "miss": miss})

print(f"\nFinished dishes: {len(fin_results)}")
if fin_missing:
    print(f"Missing ingredients: {sorted(fin_missing)}")

for i, r in enumerate(fin_results, 1):
    m = " [!" + ",".join(set(r["miss"])) + "]" if r["miss"] else ""
    print(f'  {i:>3d}. [{r["cat"]:<25s}] {r["dish"]:<45s} AED {r["cost"]:>8.2f}{m}')

# ============================================================
# Read menu and build dish list with prices
wb = openpyxl.load_workbook(
    r"C:\Users\harsh\Desktop\Cloud Kitchen\Brands Home\Chinese Brands\New Base menu.xlsx",
    data_only=True
)
ws = wb["Sheet1"]

menu_items = []
for r in range(3, ws.max_row + 1):
    cat = ws.cell(row=r, column=3).value
    dish = ws.cell(row=r, column=4).value
    veg = ws.cell(row=r, column=5).value
    chk = ws.cell(row=r, column=6).value
    shrimp = ws.cell(row=r, column=7).value
    if not dish:
        continue

    def parse_price(val):
        if val is None:
            return None
        s = str(val).strip()
        if s in ("—", "", "-"):
            return None
        try:
            return float(s)
        except:
            return None

    vp = parse_price(veg)
    cp = parse_price(chk)
    sp = parse_price(shrimp)

    # Add base item
    if vp is not None:
        menu_items.append({"cat": str(cat or ""), "dish": str(dish).strip(), "sell": vp, "variant": "Veg"})
    # Chicken variant (base price + surcharge)
    if cp is not None:
        if vp is not None and cp < 20:
            # cp is a surcharge
            menu_items.append({"cat": str(cat or ""), "dish": str(dish).strip().replace("(Veg)", "").replace("Veg ", "") + " (Chicken)",
                              "sell": vp + cp, "variant": "Chicken"})
        else:
            menu_items.append({"cat": str(cat or ""), "dish": str(dish).strip(), "sell": cp, "variant": "Chicken"})
    # Shrimp variant
    if sp is not None:
        if vp is not None and sp < 20:
            menu_items.append({"cat": str(cat or ""), "dish": str(dish).strip().replace("(Veg)", "").replace("Veg ", "") + " (Shrimp)",
                              "sell": vp + sp, "variant": "Shrimp"})
        else:
            menu_items.append({"cat": str(cat or ""), "dish": str(dish).strip(), "sell": sp, "variant": "Shrimp"})

# Now use finished recipe costs
# Build cost lookup from finished recipes
fin_cost_map = {}
for r in fin_results:
    fin_cost_map[r["dish"].lower().strip()] = r["cost"]

print(f"\nMenu items: {len(menu_items)}")

# Save with actual costs where available
output_dishes = []
for m in menu_items:
    # Try to match menu dish to a finished recipe
    cost = fin_cost_map.get(m["dish"].lower().strip(), 0)
    output_dishes.append({
        "dish": m["dish"], "cat": m["cat"], "cost": cost, "sell": m["sell"], "variant": m["variant"]
    })

output = {"dishes": output_dishes, "sf_costs": sf_cost, "finished_costs": fin_results}
with open(r"E:\Cloud Kitchen\AI Teams\chinese_dish_costing.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\n{'#':<4s} {'Category':<20s} {'Dish':<45s} {'Sell':>5s} {'Cost':>8s}")
print("=" * 85)
for i, d in enumerate(output_dishes, 1):
    cost_str = f"{d['cost']:>7.2f}" if d["cost"] > 0 else "    TBD"
    print(f"{i:<4d} {d['cat']:<20s} {d['dish']:<45s} {d['sell']:>5.0f} {cost_str}")

# Also print the standalone finished recipe costing
print(f"\n\nFINISHED RECIPE COSTS (all {len(fin_results)} dishes):")
for i, r in enumerate(fin_results, 1):
    print(f"  {i:>3d}. {r['dish']:<45s} AED {r['cost']:>8.2f}")

print(f"\nSaved to chinese_dish_costing.json")
