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