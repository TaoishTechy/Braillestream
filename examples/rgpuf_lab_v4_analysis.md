# RGPUF Lab v4 -- Micro-World Forge Report

core: rgpuf_core.py | demo: rgpuf_lab_v4.py


## Mode Comparison


MODE          PR_BASE PR_ADAPT   PR_OPT   DELTA  AGENCY  COVER LAW_COST

------------------------------------------------------------------------
lander          0.997    1.644    1.644  +0.648    0.00   0.00      5.7
asteroids       0.489    0.489    0.489  +0.000    0.24   0.00      5.2
pressure        0.550    0.469    0.550  +0.000    0.00   0.00      7.8
freescape       0.434    0.434    0.456  +0.022    0.00   0.00      9.7
colony          0.035    0.188    0.499  +0.464    0.56   0.01      7.8
semantic        0.065    0.065    0.065  -0.000    0.58   0.00      6.2

## Detailed Mode Analysis


### lander

- Final PR (normalized): 0.9965
- Final PR (raw): 0.2215
- Goal Agency: 0.4898
- Coverage: 0.0000
- Law Cost: 4.50
- Laws: thrust_gravity_drag,quantized_rotation,resource_thermodynamics,playable_reality
- Gödel Tokens: 49
- Failure: active

### asteroids

- Final PR (normalized): 0.4891
- Final PR (raw): 0.0940
- Goal Agency: 0.2353
- Coverage: 0.0000
- Law Cost: 5.20
- Laws: central_gravity_well,toroidal_wrap,quantized_rotation,resource_thermodynamics,playable_reality
- Gödel Tokens: 49
- Failure: active

### pressure

- Final PR (normalized): 0.5499
- Final PR (raw): 0.0786
- Goal Agency: 0.0000
- Coverage: 0.0000
- Law Cost: 7.00
- Laws: thrust_gravity_drag,graph_pressure_diffusion,hysteresis_failure,resource_thermodynamics,playable_reality
- Gödel Tokens: 49
- Failure: active

### freescape

- Final PR (normalized): 0.4336
- Final PR (raw): 0.0447
- Goal Agency: 0.0000
- Coverage: 0.0000
- Law Cost: 9.70
- Laws: cuboid_collision,zone_gravity_friction,hydraulic_height,graph_pressure_diffusion,hysteresis_failure,resource_thermodynamics,playable_reality
- Gödel Tokens: 49
- Failure: active

### colony

- Final PR (normalized): 0.0348
- Final PR (raw): 0.0058
- Goal Agency: 0.2222
- Coverage: 0.0052
- Law Cost: 6.00
- Laws: cell_occupancy,quantized_rotation,toroidal_surface,power_suit_energy,resource_thermodynamics,playable_reality
- Gödel Tokens: 9
- Failure: active

### semantic

- Final PR (normalized): 0.0650
- Final PR (raw): 0.0650
- Goal Agency: 0.5833
- Coverage: 0.0006
- Law Cost: 6.15
- Laws: playable_reality,minimum_law_efficiency,compression_ratio,semantic_entropy
- Gödel Tokens: 0
- Failure: active

## Best Micro-World Recipes


### Lander

- Seed: 42
- Wall Density: 0.3
- Policy: wall_follow
- PR: 1.6441

### Asteroids

- Seed: 42
- Wall Density: 0.3
- Policy: naive
- PR: 0.4891

### Pressure

- Seed: 42
- Wall Density: 0.3
- Policy: naive
- PR: 0.5499

### Freescape

- Seed: 50
- Wall Density: 0.3
- Policy: naive
- PR: 0.4558

### Colony

- Seed: 47
- Wall Density: 0.3
- Policy: wall_follow
- PR: 0.4987

### Semantic

- Seed: 42
- Wall Density: 0.3
- Policy: naive
- PR: 0.065

---

## Full In‑Depth Analysis of RGPUF Lab v4 (Comparison Campaign)

The `rgpuf_lab_v4.py` output shows a **complete rewrite** of the framework core (`rgpuf_core.py`), introducing a **LawStack** (runtime only active laws, not global registry), **measured goal agency** (mode‑specific success criteria), a **transition‑based predictor** for prediction error, and a **micro‑world optimisation** system. The comparison campaign ran baseline (static law stacks), adaptive (DLASc + HDC with Gödel tokens), and a quick optimisation (grid search over wall density/agent policy) for 240 steps, seed=42.

The headline numbers have **radically changed** from v3: `PR_norm` values now range from **0.04 (colony) to 3.21 (pressure)**, compared to v3’s 0.11–0.365. This is not a bug but a **fundamental re‑scaling** – v4’s PR formula normalises by mean law cost and multiplies back, making scores roughly comparable to a “world units per law cost” metric that can exceed 1.0. The rankings have also shifted: **pressure now achieves the highest PR_norm (3.214)**, followed by lander (2.832), freescape (2.441), asteroids (2.414), colony (0.040), semantic (0.065). Colony remains the worst, but its adaptive PR_norm increased from 0.040 to 0.041 (barely), while optimisation found a configuration reaching 0.451 – a **11× improvement**.

Below I dissect the results, compare with v3, identify what worked, what remains broken, and extract the key lessons.

---

## 1. Overview of v4 Changes (from `rgpuf_core.py`)

| Feature | v3 | v4 |
|---------|----|----|
| Law activation | Global `active` flag in registry, affecting cost sum | `LawStack` containing only laws actually **executed** in that mode |
| Agency | Action‑based (`successful/attempted`) | **Goal‑based** (mode‑specific: e.g., for lander, `useful` = thrust reduces vertical speed error) |
| Prediction error | Simple state‑signature change + distance | **Transition‑based predictor** – learns transitions between signatures, error = 1 if predicted != actual |
| PR formula | `(state_density * agency * fals * comp_gain) / (law_cost * (1+ambiguity+0.15*SE+0.3*pred_err))` then `normalised = raw * mean_cost * law_count` – essentially rescaling to make scores comparable to v2 |
| HDC anomalies | Cosmetic (only counter) | Functional – `earn_godel_token()` when prediction error or drift > threshold; tokens spent by DLASc to activate repair laws (e.g., `wall_following_agent` costs 2 tokens) |
| DLASc activation | Preconditions + effect heuristics | Same, but now requires **Gödel tokens** to activate a law (unless it’s already in stack) |
| Mode‑specific goal agency | Not present | Implemented per mode: lander – vertical speed reduction; asteroids – orbital distance stability; pressure – pressure reduction from drilling; colony – new cell visited; freescape – moving >0.3 units or collision count change |

---

## 2. Quantitative Comparison: Baseline vs Adaptive vs Optimised

| Mode | PR_base | PR_adapt | PR_opt | Δ_opt | Goal Agency | Coverage | LawCost | Gödel Tokens (adapt) |
|------|---------|----------|--------|-------|-------------|----------|---------|----------------------|
| Lander | 2.832 | 2.065 | 3.072 | +0.239 | 0.00 | 0.00 | 5.7 | 241 |
| Asteroids | 2.414 | 2.414 | 2.664 | +0.251 | 0.31 | 0.00 | 5.2 | 241 |
| Pressure | 3.214 | 2.890 | 3.214 | 0.000 | 0.00 | 0.00 | 7.8 | 241 |
| Freescape | 2.441 | 2.441 | 2.464 | +0.023 | 0.00 | 0.00 | 9.7 | 241 |
| Colony | 0.040 | 0.041 | 0.451 | +0.412 | 0.12 | 0.01 | 7.8 | 11 |
| Semantic | 0.065 | 0.065 | 0.065 | 0.000 | 0.58 | 0.00 | 6.2 | 0 |

**Key observations:**

- **Pressure** has the highest baseline PR (3.214), but adaptive slightly reduces it (2.890). The optimisation did not find a better config.
- **Colony** shows the biggest relative improvement from optimisation (+1030%), but its absolute PR_opt (0.451) is still far below motion modes.
- **Goal agency** is zero for lander, pressure, freescape – meaning that the mode‑specific “useful” criterion was never met during the run. This is a **major problem** in the v4 implementation (see Section 4).
- **Gödel tokens** accumulate to 241 in most modes (except colony 11, semantic 0). The token accumulation is extremely high – the `earn_godel_token()` function increments tokens whenever prediction error or semantic drift exceeds `anomaly_threshold` (hardcoded 0.25 in config but not passed? Actually in `_build_telemetry`, it calls `earn_godel_token(pred_error, drift_val, config.anomaly_threshold)`; threshold = 0.25, and drift often >0.9 initially, so tokens accumulate quickly. After 240 steps, 241 tokens means almost every step earned one. Tokens are spent only when DLASc activates a law that has a token cost (e.g., `wall_following_agent` costs 2). In the comparison campaign, adaptive did not activate any costly law except possibly `risk_policy` or `pid_controller` – but those costs are small. The high token count suggests the system is **earning tokens faster than spending**, which is fine but indicates that prediction error never falls below threshold.

---

## 3. Comparison with v3 Results

| Mode | v3 PR_norm (baseline) | v4 PR_base | Δ (v4 – v3) | Interpretation |
|------|----------------------|------------|-------------|----------------|
| Lander | 0.110 | 2.832 | **+2.722** | v4 re‑scaling; lander now competitive |
| Asteroids | 0.098 | 2.414 | **+2.316** | Similar boost |
| Pressure | 0.295 | 3.214 | **+2.919** | Becomes top mode |
| Freescape | 0.126 | 2.441 | **+2.315** | Large increase |
| Colony | 0.365 | 0.040 | **–0.325** | **Collapse** – colony is now the worst |
| Semantic | 0.008 | 0.065 | **+0.057** | Still low |

**Why did colony collapse?**  
In v3, colony had the highest PR (0.365) because agency was perfect (1.0) and law cost was mis‑scaled. In v4, agency is now **goal‑based**: `useful` is true only when a move results in a **new cell visited**. With a wall‑following agent that often revisits cells, the goal agency is only 0.12. The coverage after 240 steps is only 0.01 (≈ one new cell out of 576). The `state_density` in v4 is computed from unique signatures, which for colony is extremely low because the agent stays in a small set of cells (output shows cell position stuck at (13,12) and (13,13)). Thus, despite having 8 active laws and a law cost of 7.8, the product `state_density * goal_agency` is tiny → PR collapses. The optimisation found a better seed (seed 42 gave PR_opt 0.468? Actually the recipe shows colony best PR_norm 0.468 from seed 42 with wall_following_agent and bresenham_los – that’s still far below v3’s 0.365, but the `report_v4.md` shows colony PR_opt=0.499 – inconsistent. The main point: colony is now correctly penalised for low coverage.

**Why did pressure become top?**  
Pressure mode has a high state density (pressure diffuses across zones, ship moves slowly, unique signatures accumulate). Goal agency is **zero** – but `playable_reality_v4` formula still multiplies by `clamp(goal_agency,0,1)`, which would make PR = 0 if goal_agency = 0. However, looking at the code: `goal_agency` is the `AgentStats.goal_agency` property. In `_build_telemetry`, `ag = goal_ag if goal_ag > 0 else action_ag`. So when goal agency is zero, it falls back to **action agency** – which for pressure is 1.0 (because every attempted action is counted as moved). So pressure’s PR is inflated by perfect action agency. **This is a hybrid agency that hides the failure of goal agency.** The diagnosis output says “Goal Agency: 0.00” for pressure, but the PR calculation used action agency instead.

---

## 4. Critical Issues Identified in v4 Output

1. **Goal agency is zero for most modes** – The mode‑specific “useful” criteria are too strict or incorrectly implemented. For lander, `useful` is based on vertical speed error reduction, but the PID controller never lands; for pressure, `useful` is pressure reduction from drilling, but drilling windows are short and pressure keeps rising; for freescape, `useful` requires moving >0.3 units or increasing collision count, which rarely happens. This makes the fallback to action agency the only reason PR stays positive. **The fallback should be removed** – if goal agency is zero, the simulation is not achieving its nominal goal, and PR should reflect that.

2. **Coverage and state density are very low** – All modes except colony have coverage 0.0 because they are not designed to explore cells; but state density for motion modes is computed from unique (x,y,zone,heading) signatures. In the telemetry CSV, for lander, `state_density` starts at 1.0 and quickly drops to 0.25? Actually looking at the first few rows of `telemetry_v4.csv` for lander, `state_density` is 1.0 at step 0, then 1.0, then 1.0, then 0.8, etc. It remains high because each step produces a slightly different position. That’s fine.

3. **HDC anomaly threshold too low** – The `earn_godel_token` function uses `anomaly_threshold = 0.25` from config. At step 0, `semantic_drift` is 0.9941 (near 1), so a token is earned immediately. After that, drift fluctuates but often stays above 0.25. This leads to 241 tokens in 240 steps – almost one per step. Tokens become meaningless. The threshold should be raised (e.g., 0.7) or drift should be normalised.

4. **DLASc did not activate any expensive laws** – In adaptive run, the diagnosis shows the same law cost as baseline (e.g., lander law cost 5.7 vs baseline 5.7). No new laws were added. The wall‑following agent was not activated because its precondition `blocked_actions_high` was never true (the agent always moves). PID controller was not activated because `landing_target` precondition may not be met. So adaptive mode is essentially identical to baseline, except for the token accumulation overhead. This explains why PR_adapt is sometimes lower (e.g., lander: 2.832 → 2.065) – the HDC state vector recomputation and drift measurement add noise, but no beneficial law activation occurs.

5. **Optimiser’s best PR for colony still low** – The optimiser found a configuration (seed 42, wall density 0.3, policy wall_follow) giving PR_opt 0.468, far below even v3 colony. This suggests that the colony mode’s fundamental mechanics (cell grid, movement rules) do not generate high state density or coverage within 240 steps. The micro‑world recipe for colony shows 8 active laws including `wall_following_agent` and `bresenham_los`, but coverage is only 0.031 and goal agency 0.12. **Colony is simply not suited to the PR_v4 metric** – its intrinsic playable reality is low because cell navigation is slow and repetitive.

6. **Semantic mode unchanged** – The semantic mode still computes aggregate metrics once and repeats them (as seen in v3). The output shows fluctuating PR_norm (0.079 → 0.061 → 0.058 → 0.062 → 0.065), so it is now live‑updating, but its absolute value remains low (~0.065). The semantic mode’s law cost (6.15) and agency (0.58) are not meaningful because it is an observer.

---

## 5. What Works Well (Successes of v4)

- **LawStack separation** – The v3 bug where global law registry inflated costs is fixed. Law cost now reflects only the laws actually executed in each mode, and values (5.2–9.7) are plausible.
- **Transition‑based predictor** – `SignaturePredictor` learns from state transitions, and `prediction_error` is computed from it. In motion modes, prediction error remains low (e.g., lander CSV shows 0.0 for many steps) because the dynamics are deterministic. In colony, prediction error is zero because the agent is stuck. This is a solid improvement over v3’s distance‑based error.
- **Functional Gödel tokens** – The mechanism is present (tokens are earned and can be spent), even if not yet utilised effectively. The high token count shows the system is detecting anomalies.
- **Micro‑world recipe extraction** – The `extract_recipe` function and the final recipes printed are a great way to capture optimal configurations. The recipes show dead laws (all laws are marked as “dead” because their contribution score is never positive – another issue) but at least the law stack is recorded.
- **Compression gain** – `compression_gain_v4` uses `(step+1)/(seed_bytes+law_cost)`. For lander (law_cost=4.5, steps=240), compression gain ≈ 240/(4+4.5)=240/8.5≈28.2, which is reasonable. This metric is now part of PR numerator, rewarding high compression.

---

## 6. Recommendations for v5

1. **Remove fallback to action agency** – Goal agency must be non‑zero for meaningful PR. Re‑implement mode‑specific goals that are actually achievable within the step budget. For lander, measure distance to pad; for pressure, measure pressure reduction; for colony, measure cell coverage increase.

2. **Raise HDC anomaly threshold** – Set `anomaly_threshold=0.7` so tokens are only earned for genuine surprises. Also add a decay: after earning a token, reset the drift reference.

3. **Make DLASc activation useful** – Ensure that in adaptive mode, the preconditions for useful laws (e.g., `pid_controller`, `wall_following_agent`) are met by the mode’s state. For colony, `blocked_actions_high` should be true when stuck count > 5 – but the colony runner is not updating agent_stats.blocked correctly in the naive movement branch. Fix that.

4. **Tune goal agency criteria** – For pressure, `useful` should be true when drilling reduces pressure *per unit time*, not just any reduction. For freescape, movement >0.1 units is enough (0.3 is too strict). For lander, `useful` should be true when the ship’s vertical speed is within 20% of target and fuel is not wasted.

5. **Fix colony movement stuck issue** – The colony mode in v4 still uses the same wall‑following and naive movement as v3, but the agent often gets stuck because the grid generation has high wall density (0.45). Reducing wall density to 0.3 (as used in optimiser) improves coverage but still low. Perhaps add a random move when stuck.

6. **Add early termination for low goal agency** – If goal agency remains zero for 50 steps, the simulation could exit early or trigger a repair law automatically.

7. **Separate PR into goal‑based and action‑based variants** – Keep both metrics: `PR_goal` (only goal agency) and `PR_mixed` (fallback). The comparison table should show both.

8. **Increase steps for colony** – 240 steps may be too few to explore a 24×24 grid. Increase default steps for colony to 1000, or adaptively stop when coverage > 0.5.

---

## 7. Final Verdict

**RGPUF Lab v4 is a major architectural improvement** – the LawStack, functional Gödel tokens, and goal agency are all correct steps. The massive re‑scaling of PR_norm makes scores intuitive (they now represent “world units per law cost” and can exceed 1.0). However, the **goal agency crisis** (zero for most modes) and the **non‑functional adaptive layer** (no law activation) mean that the comparison campaign essentially compares baseline vs identical baseline, with only a different random seed in the optimiser. The remarkable PR values for pressure and lander are inflated by action agency fallback – they do not reflect true goal achievement.

The colony mode’s collapse is **correct** – it exposes that cell‑based exploration is intrinsically less efficient than continuous motion under the v4 metric. That is a feature, not a bug.

To turn v4 into a reliable tool, the team must:
- Implement achievable goal agency for each mode.
- Force DLASc to actually activate laws by lowering token costs and ensuring preconditions are met.
- Remove the action agency fallback, or at least report both numbers separately.

When those fixes are made, the adaptive runs should show clear PR improvements over baseline, and the micro‑world recipes will become genuinely optimised law stacks. The foundation is solid; now it needs the final polish to deliver on the promise of a **self‑diagnosing, self‑optimising retro physics engine**.

---
### Terminal Output:
```
python3 rgpuf_lab_v4.py
Running comparison campaign: 240 steps, seed=42

RGPUF Lab v4 -- Micro-World Forge
core: rgpuf_core.py | demo: rgpuf_lab_v4.py

MODE          PR_BASE PR_ADAPT   PR_OPT   DELTA  AGENCY  COVER LAW_COST  LAWS
-----------------------------------------------------------------------------
lander          2.833    2.065    3.072  +0.239    0.00   0.00      5.7   N/A
asteroids       2.414    2.414    2.664  +0.251    0.31   0.00      5.2   N/A
pressure        3.214    2.890    3.214  +0.000    0.00   0.00      7.8   N/A
freescape       2.441    2.441    2.464  +0.023    0.00   0.00      9.7   N/A
colony          0.040    0.041    0.451  +0.412    0.12   0.01      7.8   N/A
semantic        0.065    0.065    0.065  -0.000    0.58   0.00      6.2   N/A

DIAGNOSIS -- lander
  Problem in v3:
    - PR was crushed by global registry law cost.
    - Agency was inflated by action success instead of goal success.

  v4 repair:
    - LawStack now counts only executed mode laws (cost: 5.7).
    - Goal agency uses mode-specific useful action criteria.
    - HDC anomalies buy repair trials via Gödel tokens.
    - State density measured from unique signatures.
    - Prediction error from transition-based predictor.

  Result:
    PR_norm: 2.832 -> 2.065 (-0.768)
    LawCost: N/A -> 5.7
    Coverage: N/A -> 0.00
    Goal Agency: N/A -> 0.00
    Gödel Tokens: 241

DIAGNOSIS -- asteroids
  Problem in v3:
    - PR was crushed by global registry law cost.
    - Agency was inflated by action success instead of goal success.

  v4 repair:
    - LawStack now counts only executed mode laws (cost: 5.2).
    - Goal agency uses mode-specific useful action criteria.
    - HDC anomalies buy repair trials via Gödel tokens.
    - State density measured from unique signatures.
    - Prediction error from transition-based predictor.

  Result:
    PR_norm: 2.414 -> 2.414 (+0.000)
    LawCost: N/A -> 5.2
    Coverage: N/A -> 0.00
    Goal Agency: N/A -> 0.31
    Gödel Tokens: 241

DIAGNOSIS -- pressure
  Problem in v3:
    - PR was crushed by global registry law cost.
    - Agency was inflated by action success instead of goal success.
    - Agency was false-perfect because actions counted even when pressure rose.
    - Hysteresis excess never decayed.

  v4 repair:
    - LawStack now counts only executed mode laws (cost: 7.8).
    - Goal agency uses mode-specific useful action criteria.
    - HDC anomalies buy repair trials via Gödel tokens.
    - State density measured from unique signatures.
    - Prediction error from transition-based predictor.

  Result:
    PR_norm: 3.214 -> 2.890 (-0.323)
    LawCost: N/A -> 7.8
    Coverage: N/A -> 0.00
    Goal Agency: N/A -> 0.00
    Gödel Tokens: 241

DIAGNOSIS -- freescape
  Problem in v3:
    - PR was crushed by global registry law cost.
    - Agency was inflated by action success instead of goal success.
    - Zone changes were on timer, not position.

  v4 repair:
    - LawStack now counts only executed mode laws (cost: 9.7).
    - Goal agency uses mode-specific useful action criteria.
    - HDC anomalies buy repair trials via Gödel tokens.
    - State density measured from unique signatures.
    - Prediction error from transition-based predictor.

  Result:
    PR_norm: 2.441 -> 2.441 (+0.000)
    LawCost: N/A -> 9.7
    Coverage: N/A -> 0.00
    Goal Agency: N/A -> 0.00
    Gödel Tokens: 241

DIAGNOSIS -- colony
  Problem in v3:
    - PR was crushed by global registry law cost.
    - Agency was inflated by action success instead of goal success.
    - Cell movement improved but coverage remained low.
    - Teleport law was present but rarely executed.

  v4 repair:
    - LawStack now counts only executed mode laws (cost: 7.8).
    - Goal agency uses mode-specific useful action criteria.
    - HDC anomalies buy repair trials via Gödel tokens.
    - State density measured from unique signatures.
    - Prediction error from transition-based predictor.

  Result:
    PR_norm: 0.040 -> 0.040 (+0.001)
    LawCost: N/A -> 7.8
    Coverage: N/A -> 0.01
    Goal Agency: N/A -> 0.12
    Gödel Tokens: 11

DIAGNOSIS -- semantic
  Problem in v3:
    - PR was crushed by global registry law cost.
    - Agency was inflated by action success instead of goal success.
    - Metrics computed once then repeated -- no live data.

  v4 repair:
    - LawStack now counts only executed mode laws (cost: 6.1).
    - Goal agency uses mode-specific useful action criteria.
    - HDC anomalies buy repair trials via Gödel tokens.
    - State density measured from unique signatures.
    - Prediction error from transition-based predictor.

  Result:
    PR_norm: 0.065 -> 0.065 (+0.000)
    LawCost: N/A -> 6.1
    Coverage: N/A -> 0.00
    Goal Agency: N/A -> 0.58
    Gödel Tokens: 0

============================================================
MICRO-WORLD RECIPES
============================================================

BEST MICRO-WORLD RECIPE
  Name:            Lander Escape
  Mode:            lander
  Seed:            43
  Laws:            4
  LawCost:         4.5
  PR_norm:         3.0718
  Coverage:        0.0
  Failure:         none at T=-1
  Dead Laws:       thrust_gravity_drag, quantized_rotation, resource_thermodynamics, playable_reality
  Law Stack:       thrust_gravity_drag, quantized_rotation, resource_thermodynamics, playable_reality

BEST MICRO-WORLD RECIPE
  Name:            Asteroids Escape
  Mode:            asteroids
  Seed:            45
  Laws:            5
  LawCost:         5.2
  PR_norm:         2.6643
  Coverage:        0.0
  Failure:         none at T=-1
  Dead Laws:       central_gravity_well, toroidal_wrap, quantized_rotation, resource_thermodynamics, playable_reality
  Law Stack:       central_gravity_well, toroidal_wrap, quantized_rotation, resource_thermodynamics, playable_reality

BEST MICRO-WORLD RECIPE
  Name:            Pressure Escape
  Mode:            pressure
  Seed:            42
  Laws:            5
  LawCost:         7.0
  PR_norm:         3.2138
  Coverage:        0.0
  Failure:         none at T=-1
  Dead Laws:       thrust_gravity_drag, graph_pressure_diffusion, hysteresis_failure, resource_thermodynamics, playable_reality
  Law Stack:       thrust_gravity_drag, graph_pressure_diffusion, hysteresis_failure, resource_thermodynamics, playable_reality

BEST MICRO-WORLD RECIPE
  Name:            Freescape Escape
  Mode:            freescape
  Seed:            45
  Laws:            7
  LawCost:         9.7
  PR_norm:         2.4639
  Coverage:        0.0
  Failure:         none at T=-1
  Dead Laws:       cuboid_collision, zone_gravity_friction, hydraulic_height, graph_pressure_diffusion, hysteresis_failure, resource_thermodynamics, playable_reality
  Law Stack:       cuboid_collision, zone_gravity_friction, hydraulic_height, graph_pressure_diffusion, hysteresis_failure, resource_thermodynamics, playable_reality

BEST MICRO-WORLD RECIPE
  Name:            Colony Escape
  Mode:            colony
  Seed:            42
  Laws:            8
  LawCost:         7.8
  PR_norm:         0.468
  Coverage:        0.0312
  Failure:         none at T=-1
  Dead Laws:       cell_occupancy, quantized_rotation, toroidal_surface, power_suit_energy, resource_thermodynamics, playable_reality, wall_following_agent, bresenham_los
  Law Stack:       cell_occupancy, quantized_rotation, toroidal_surface, power_suit_energy, resource_thermodynamics, playable_reality, wall_following_agent, bresenham_los

BEST MICRO-WORLD RECIPE
  Name:            Semantic Escape
  Mode:            semantic
  Seed:            42
  Laws:            4
  LawCost:         6.15
  PR_norm:         0.065
  Coverage:        0.0006
  Failure:         none at T=-1
  Dead Laws:       playable_reality, minimum_law_efficiency, compression_ratio, semantic_entropy
  Law Stack:       playable_reality, minimum_law_efficiency, compression_ratio, semantic_entropy

  Completed in 167.7s

```

