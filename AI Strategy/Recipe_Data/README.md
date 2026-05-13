# ZwQ Recipe Data — Canonical Store

**Location:** `E:\Cloud Kitchen\AI Teams\AI Strategy\Recipe_Data`
**Consolidated:** 2026-04-24
**Files:** 15 JSONs covering 10 cuisines, 1037 recipes + 214 semi-finished components.

## Policy

This is the **single source of truth** for all recipe data across the ZwQ portfolio. All future edits go here. The xlsx files in original brand folders (`Brands Home\<Cuisine>\` and `Menu_Assessment\<brand>\`) are READ-ONLY source references.

## Schema

All files share the same canonical schema — see `_manifest.json` for details. Top-level: `schema_version`, `brand`/`dataset`, `source_file`, `extracted_at`, `last_updated`, `recipe_count`, `methodology`, `changelog`, `pending_decisions`, `semi_finished_components`, `recipes`. Per recipe: `recipe_number`, `recipe_name`, `brand`, `category`, `ingredients[]`, `packaging[]`, `allergens[]`, `calories_kcal`, `yield`, `portion_size`, `serves`, `method`, `plating`, `notes`.

## Allergen vocabulary (16 tags, essential-only)

`Celery, Gluten, Crustaceans, Fish, Eggs, Lupin, Molluscs, Mustard, Nuts, Peanuts, Sesame, Soya, Sulphites, Sugared drink, Dairy, Lentils`

Empty result → `["NO_ALLERGENS"]`. Speculative tagging avoided.

## File inventory

| File | Cuisine | Brand | Recipes |
|---|---|---|---|
| `breakfast_before_noon.json` | Breakfast | Before Noon | 63 |
| `breakfast_breakfast_counter.json` | Breakfast | Breakfast Counter | 48 |
| `breakfast_sunrise_and_co.json` | Breakfast | Sunrise & Co | 45 |
| `breakfast_toast_and_co.json` | Breakfast | Toast & Co | 47 |
| `american_wings_of_fury_v3.json` | American (V3) | Wings of Fury | 51 |
| `american_winging_it_v3.json` | American (V3) | Wingin' It | 51 |
| `american_legacy.json` | American (Legacy) | All American Brands (shared pool) | 144 |
| `indian.json` | Indian | All Indian Brands (shared pool) | 102 |
| `korean_seoul_food.json` | Korean | Seoul Food | 68 |
| `japanese_norii.json` | Japanese | Norii | 72 |
| `chinese.json` | Chinese | All Chinese Brands (shared pool) | 90 |
| `mexican.json` | Mexican | All Mexican Brands (shared pool) | 84 |
| `poke_big_kahuna.json` | Poke | The Big Kahuna | 45 |
| `poke_pokeman.json` | Poke | PokeMan | 52 |
| `healthy.json` | Healthy | Healthy Food | 75 |

**Total:** 1037 recipes + 214 semi-finished components across 15 files.

## Pending

- **Slavic Brands** — not yet created.
