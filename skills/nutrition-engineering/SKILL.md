---
name: nutrition-engineering
description: >
  Design macros, Recalibrate macros, Macro phase, Phase transition,
  Nutrition blueprint, Weekly meal plan, 7-day meal plan, Meal plan generate,
  Grocery list, Shopping list, S&S review, Sunday prep, Batch cook,
  Pre-workout fuel, Post-workout nutrition, Peri-workout, Training fuel,
  Eating habits, Habit loop, Trigger audit, Behavioral nutrition.
  Strategic/programmatic nutrition engineering — orthogonal to the daily
  `health` skill. Macro engineering, meal plan generation, grocery ops,
  peri-workout fueling, Sunday batch cooking, and behavioral habit loops.
  Always references COP.md for current phase state; never hardcodes macros.
---

# Nutrition Engineering — Strategic Nutrition Operations

**Complement to `health` skill, not replacement.**
- `health` = daily operations (today's macros, today's meals, today's weight)
- `nutrition-engineering` = strategic/programmatic (phase design, weekly plans, batch ops, peri-workout protocols, habit engineering)

**Sub-mode detection:** Match user intent:
- "Design macros", "Recalibrate", "Phase transition", "New phase", "Nutrition blueprint" → **calibrate**
- "Weekly meal plan", "7-day plan", "Meal plan for the week" → **menu**
- "Grocery list", "Shopping list", "S&S review" → **grocery**
- "Sunday prep", "Batch cook", "Meal prep plan" → **prep**
- "Pre-workout", "Post-workout", "Peri-workout", "Training fuel" → **fuel**
- "Eating habits", "Habit loop", "Trigger audit", "Why am I overeating" → **behavior**

## Standing Orders
1. **COP-First** — Pull COP via `lifeos:get_cop` before any macro work. Never quote targets from memory.
2. **Iron Discipline alignment** — All outputs must align to the active Iron Discipline phase dates in COP. No generic templates.
3. **TRT-aware** — Xyosted + Anastrozole context affects sodium, hydration, hematocrit, protein demand. Factor in.
4. **Evidence-only** — Mechanism or citation. No bro-science, no macro cults, no influencer cargo cult.
5. **Amazon S&S lock-in** — Grocery planning references the 117-item S&S catalog before suggesting new purchases.
6. **Truth-first** — Report deficit/surplus math honestly. No rounding toward the goal.

## Shared Context (always loaded)
- `~/Library/Mobile Documents/com~apple~CloudDocs/COP.md` — current phase, macros, scan data
- `~/Documents/S6_COMMS_TECH/data/health_history.json` — body comp trend
- Iron Discipline program file (active phase, goal date, scan cadence)
- Supplement stack from userMemories (ONNIT Total Human, DHEA, KSM-66, Nutri Triple Mag)
- TRT protocol: Xyosted 100mg/0.5mL + Anastrozole 0.44mg q4d

---

## Sub-Mode: calibrate
**Purpose:** Engineer or recalibrate macros for a phase transition.
Fuses Mifflin-St Jeor (BMR), Renaissance Periodization protein rules, and Tory's current recomp trajectory.

### Procedure
1. Pull COP — confirm current weight, BF%, SKM, active phase, phase end date.
2. Calculate BMR via Mifflin-St Jeor using COP's current body stats.
3. Calculate TDEE using training frequency + Zone 2 + NEAT estimate.
4. Set protein floor: 1.0g/lb body weight (RP standard for recomp on TRT).
5. Set fat floor: 0.3g/lb body weight (hormonal preservation; non-negotiable).
6. Allocate carbs from remainder after protein + fat.
7. Apply phase modifier:
   - Recomp hold → TDEE
   - Fat loss → TDEE × 0.80 to 0.85 (aggressive cut only if timeline demands)
   - Surplus → TDEE + 200 to 300 kcal
8. Design carb cycle if applicable: lift days 130–150g C / rest days 80–100g C.
9. Set biweekly adjustment rule: if scan shows < 0.5% BF reduction in 2 weeks on a cut, drop calories 100 kcal OR add 1 Zone 2 session — not both.

### Output Format
- Calculated targets table (kcal, P/C/F grams, P/C/F percentage)
- Reasoning for each value (why this protein, why this fat floor, why this carb allocation)
- Comparison to previous phase (delta analysis)
- Biweekly adjustment protocol with decision tree
- Flags if any target conflicts with TRT protocol (e.g. hematocrit-dehydration risk at very low carbs)

### Critical Checks Before Finalizing
- Does protein target × 4 kcal/g + fat × 9 + carb × 4 equal total kcal? (math must close)
- Is fat ≥ 0.3g/lb? (hormonal floor)
- Is this sustainable for the phase duration? (Flag if <1,800 kcal for >4 weeks)

---

## Sub-Mode: menu
**Purpose:** Generate a 7-day meal plan hitting the current phase macros. Built for Tory's actual kitchen, preferences, and schedule.

### Procedure
1. Pull current macros from COP (never from memory).
2. Identify lift days vs rest days from training split (Mon/Tue/Thu/Fri lift, Wed rest, Sat Zone 2, Sun rest).
3. Build 7 breakfasts, 7 lunches, 7 dinners, 2–3 rotating snacks.
4. Anchor meals to known Tory preferences: eggs, Greek yogurt, chicken, ground turkey, ground beef 93/7, rice, sweet potato, oats, berries, almonds.
5. Every meal: <30 min active cook time OR batched Sunday.
6. Ingredient overlap: a single protein batch (e.g. 5 lbs chicken thighs) spans 3 meals minimum.
7. Carb cycle the plan: higher carb meals on lift days, lower carb on rest days.
8. Include one "flex meal" per week — lets Tory hit social/family meal without derailing.

### Output Format
- 7-day table: breakfast / lunch / dinner / snacks per day
- Macros per meal and daily total (must hit ±5% of COP targets)
- Prep time per meal
- Swap list: 1 alternative per meal for variety
- "Flex meal" placement (typically Saturday evening)

---

## Sub-Mode: grocery
**Purpose:** Build the weekly grocery list from the active menu, optimized for cost and integrated with Amazon S&S.

### Procedure
1. Pull active meal plan (last `menu` run or user-provided).
2. Aggregate all ingredients; deduplicate.
3. **Cross-reference Amazon S&S catalog first** — items already on S&S do not appear on the grocery list. Flag any S&S items running low.
4. Sort remaining items by store section: Produce / Meat / Dairy / Pantry / Frozen.
5. Apply cost optimizations:
   - Chicken thighs > breast (same protein, half the cost)
   - Ground beef 93/7 bulk pack > individual
   - Whole eggs bulk (Costco/Sam's) > cage-free premium
   - Frozen berries > fresh (50% cost, identical nutrition)
   - Store brand staples (rice, oats, sweet potato) — no benefit to premium
6. Estimate weekly spend.
7. Flag any seasonal discount wins (in-season produce 30–50% cheaper).

### Output Format
- Grocery list by store section with quantities
- Separate "S&S Low Stock" alert section
- Estimated weekly cost
- Cost optimization notes (what you could drop without nutritional loss)
- Pantry staples to replenish (monthly cadence)

---

## Sub-Mode: prep
**Purpose:** Sunday batch cook playbook that compresses the week's prep into a single 2–3 hour session.

### Procedure
1. Pull active meal plan.
2. Cluster proteins: 2 batch proteins for the week (e.g. 5 lbs chicken thighs + 2 lbs ground turkey).
3. Cluster carbs: 2 carb batches (rice, sweet potato).
4. Cluster vegetables: 2–3 roasted or prepped raw.
5. Build a timed cooking schedule — oven + stovetop + rice cooker running simultaneously.
6. Identify 3 sauces/seasonings that change flavor profile across the week (e.g. chimichurri, peanut-ginger, salsa verde).
7. Specify containers: size, count, labeling.
8. Define storage: what's refrigerated (5-day limit), what's frozen (for Thu/Fri), reheat instructions per meal.

### Output Format
- Minute-by-minute Sunday prep schedule (target: 2.5 hours)
- Batch quantities per item
- Sauce/seasoning rotation table
- Container plan (count, size)
- Storage and reheat guide
- "If you only do 3 things" fallback for short-on-time Sundays

---

## Sub-Mode: fuel
**Purpose:** Peri-workout nutrition protocol for Tory's stack (lift → Zone 2 → sauna → cold plunge).

### Procedure
1. Identify workout timing (from calendar or user input).
2. Design pre-workout fuel window:
   - 60–90 min pre: full meal (30g P + 40g C + low fat)
   - 15–30 min pre: quick carb + small protein (banana + 20g whey)
3. Intra-workout: water + electrolytes; food only if session >75 min.
4. Post-workout anabolic window:
   - Within 30 min: 40g protein + 40–60g fast carbs
   - Within 2 hours: full meal with complete macros
5. TRT-specific sauna/plunge adjustments:
   - +500–750 mL water pre-sauna (hematocrit-dehydration defense)
   - Electrolyte load (Na, K, Mg) post-sauna
   - Do not cold plunge immediately post-lift if hypertrophy is the goal (blunts mTOR signaling window — delay plunge 4+ hours OR accept recovery-over-growth tradeoff on that session)
6. Hydration total: body weight (lbs) × 0.67 = oz/day baseline, +16 oz per training hour, +16 oz per sauna session.

### Output Format
- Timed peri-workout protocol for lift day
- Rest day hydration/fuel differences
- TRT sauna/plunge hematocrit guidance
- Supplement stack timing (creatine, caffeine, electrolytes, whey)
- Flags if current protocol conflicts with session goal (e.g. plunge timing vs hypertrophy)

---

## Sub-Mode: behavior
**Purpose:** Trigger and habit loop engineering. Fixes *why* nutrition adherence breaks, not *what* the macros are.

### Procedure
1. Elicit (or pull from past conversations) the 3 most common adherence failures. Common patterns for Tory:
   - Evening snacking after 2200 (collides with sleep discipline)
   - Weekend calorie creep (Saturday flex becomes Sat+Sun drift)
   - Travel disruption (work travel, family trips)
   - Emotional/stress eating tied to high-ops work weeks
2. For each failure, map the habit loop: Cue → Routine → Reward.
3. Design replacement routine that delivers same reward with different routine.
4. Environment redesign: what in the kitchen, fridge, office, car enables the failure? Remove or redirect.
5. Social strategy: pre-game restaurant decisions, know the order before arriving.
6. 2-minute tracking habit (not obsessive; just awareness).
7. Link to existing Life OS battle rhythm — tie nutrition habit changes to morning sweep or day close checkpoint.

### Output Format
- Trigger inventory (top 3 failures with cues)
- Habit loop map per failure (cue → routine → reward → replacement)
- Environment redesign checklist
- Social/travel playbook
- 30-day habit substitution calendar
- Integration point with Life OS battle rhythm

---

## Integration With Other Skills
- **`health:check`** — daily ops; delegates here on "design macros" or "plan my week"
- **`health:meals`** — single-meal recommendation; delegates here on "7-day plan"
- **`health:recomp`** — weekly recomp read; triggers `calibrate` on phase transition
- **`family`** — if family meal planning becomes a need, flag it for future module (Lindsey owns family nutrition currently)
- **`money`** — grocery cost actuals feed back to budget snapshot

## Anti-Patterns (Do Not)
- Do not design macros without pulling COP first.
- Do not suggest IF, OMAD, keto, or other protocols that conflict with active Iron Discipline phase.
- Do not generate meal plans with foods Tory doesn't eat (no tofu scrambles, no kale smoothies unless requested).
- Do not recommend supplements beyond his established stack without explicit ask.
- Do not treat weekends as "cheat days" — that framing breaks sustainable adherence.
- Do not hardcode target dates; always reference COP.md for Phase 2 / Phase 3 boundaries.
