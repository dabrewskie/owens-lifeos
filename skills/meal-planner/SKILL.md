---
name: meal-planner
description: >
  Nutrition planning and meal prep for Tory Owens. Bridges the gap between
  knowing macros are off and actually hitting them. Generates daily/weekly
  meal plans targeting P 210g / C 130g / F 71g / 2,000 kcal. Creates grocery
  lists. Adapts to real life constraints (busy weekdays, family dinners, meal prep).
  Triggers on: "Meal plan", "What should I eat", "Macro plan", "Grocery list",
  "Meal prep", "Hit my macros", "What's for dinner", "Plan my meals",
  "High protein meals", "Meal ideas", "Food plan", "Nutrition plan",
  "Help me eat right". The plan that sits in a spreadsheet loses. The plan
  that's simple enough to follow wins.
---

# Meal Planner — Medical (Nutrition Operations)

**Mission:** Turn macro targets into actual food on actual plates. Health-pull tells Tory his macros are off. Health-recommendations says what to change. This skill says what to eat tomorrow, and makes it easy enough that he actually does it.

---

## Macro Targets

| Macro | Daily Target | Priority |
|-------|-------------|----------|
| Protein | 210g | #1 — non-negotiable |
| Carbs | 130g | Low-carb approach |
| Fat | 71g | Moderate |
| Calories | 2,000 | Slight deficit for recomp |

**Context:** Tory is 42, military background, body recomp goal. Protein is king — 210g is aggressive but appropriate for muscle preservation on a mild deficit. The challenge isn't knowing the target — it's consistently hitting it across 7 busy days.

---

## Procedure

### When Invoked — Meal Plan

1. **Check current health data** (if available):
   - Run: `python3 ~/Documents/S6_COMMS_TECH/scripts/health_auto_export_reader.py`
   - What were yesterday's actual macros? Where was the gap?

2. **Ask constraints** (or use defaults):
   - How many days to plan? (default: 7)
   - Meal prep day? (default: Sunday)
   - Family dinners? (default: yes, 5x/week — adapt the family meal to fit macros)
   - Dietary restrictions? (default: none known)
   - Budget consideration? (default: moderate)

3. **Generate plan in this format:**

```
━━ MEAL PLAN — [DATE RANGE] ━━

DAILY TARGETS: P 210g | C 130g | F 71g | 2,000 kcal

MEAL PREP (Sunday):
  Prep these for the week:
  - [Item 1]: [quantity, macros]
  - [Item 2]: [quantity, macros]
  - [Item 3]: [quantity, macros]
  Prep time: ~X hours

─── MONDAY ───
  Breakfast: [meal] — P Xg | C Xg | F Xg | XXX cal
  Snack:     [meal] — P Xg | C Xg | F Xg | XXX cal
  Lunch:     [meal] — P Xg | C Xg | F Xg | XXX cal
  Snack:     [meal] — P Xg | C Xg | F Xg | XXX cal
  Dinner:    [meal] — P Xg | C Xg | F Xg | XXX cal
  ────────
  TOTAL:     P XXXg | C XXXg | F XXXg | X,XXX cal

[Repeat for each day]

GROCERY LIST:
  Proteins:
  - [ ] Chicken breast: X lbs
  - [ ] Ground turkey: X lbs
  - [ ] Eggs: X dozen
  - [ ] Greek yogurt: X containers
  - [ ] Protein powder: [if needed]

  Produce:
  - [ ] [items]

  Pantry:
  - [ ] [items]

  Estimated cost: $XXX

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Protein Strategy (The Hard Part)

210g of protein is the hardest macro to hit. Here's the playbook:

### High-Protein Staples (aim for 30-40g per meal, 5 eating occasions)
| Food | Serving | Protein | Calories |
|------|---------|---------|----------|
| Chicken breast | 8 oz | 50g | 280 |
| Ground turkey 93% | 8 oz | 46g | 320 |
| Salmon fillet | 6 oz | 40g | 280 |
| Sirloin steak | 6 oz | 42g | 300 |
| Eggs (4 whole) | 4 large | 24g | 280 |
| Greek yogurt (0%) | 1 cup | 20g | 100 |
| Cottage cheese | 1 cup | 28g | 180 |
| Protein powder | 1 scoop | 25-30g | 120 |
| Shrimp | 8 oz | 40g | 200 |
| Turkey deli meat | 6 oz | 30g | 180 |

### Daily Protein Distribution Template
```
Breakfast:  40g (eggs + turkey sausage, or Greek yogurt + protein)
Snack 1:    25g (protein shake or cottage cheese)
Lunch:      50g (chicken/turkey + vegetables)
Snack 2:    25g (jerky, protein bar, or cheese)
Dinner:     50g (meat/fish + family-compatible sides)
Evening:    20g (casein shake or Greek yogurt if needed)
Total:      210g
```

---

## Family Dinner Compatibility

Tory eats with the family ~5 nights/week. The plan must work for everyone:

**Strategy:** Build family dinners around a shared protein, then adjust sides.
- Family has: chicken + rice + broccoli
- Tory has: larger chicken portion, skip rice, add extra broccoli, add side salad
- Nobody eats differently — Tory just adjusts portions

### Family-Friendly High-Protein Dinners
1. Grilled chicken with roasted vegetables
2. Taco night (turkey, lettuce wraps for Tory, shells for kids)
3. Stir-fry with chicken/shrimp (rice for family, cauliflower rice for Tory)
4. Baked salmon with sweet potatoes
5. Turkey meatballs with marinara (zucchini noodles for Tory, pasta for kids)
6. Sheet pan fajitas (tortillas for family, bowl style for Tory)
7. Grilled steak with loaded baked potatoes (Tory skips potato, adds salad)

---

## Meal Prep Protocol (Sunday)

**Time budget:** 2-3 hours
**Output:** 4-5 days of lunches + prepped proteins for dinners

### Standard Prep List
1. **Cook 4 lbs chicken breast** — season 2 ways (garlic herb + cajun)
2. **Cook 2 lbs ground turkey** — taco seasoned
3. **Hard boil 12 eggs**
4. **Prep vegetables** — wash and chop broccoli, bell peppers, spinach
5. **Portion containers** — 5 lunch containers with protein + veg + small carb

### Grab-and-Go Emergency Meals
For days when the plan falls apart (and it will):
- Rotisserie chicken from grocery store (70g protein for half a chicken)
- Protein shake + banana (30g protein, 2 minutes)
- Greek yogurt + handful of almonds (25g protein)
- Canned tuna on rice cakes (30g protein)
- Deli turkey roll-ups with cheese (25g protein)

---

## Supplement Stack (Nutrition-Adjacent)

| Supplement | Purpose | Timing |
|------------|---------|--------|
| Whey protein | Hit protein target | Post-workout or as snack |
| Creatine monohydrate | 5g/day | Any time, consistency matters |
| Multivitamin | Baseline coverage | Morning with food |
| Fish oil | Omega-3, inflammation | With meal |
| Vitamin D | If deficient (check labs) | Morning |
| Magnesium | Sleep, recovery | Before bed |

*Note: Coordinate with health-recommendations for full supplement protocol based on lab results.*

---

## Tracking Integration

- **health-pull:** Reports actual macro compliance — meal-planner adjusts based on patterns
- **If consistently under on protein:** Add a protein snack to the plan
- **If consistently over on calories:** Reduce fat sources (cooking oils, nuts, cheese)
- **If consistently over on carbs:** Swap starchy sides for vegetables

---

## The Standard

The best meal plan is the one you actually follow. This isn't about perfection — it's about making the default choice the right choice. Meal prep on Sunday means Monday through Friday are on autopilot. The protein target is non-negotiable because muscle preservation on a deficit requires it. Everything else can flex.

"Eat like you're building something. Because you are."
