#!/usr/bin/env python3
"""
rgpuf_lab_v4.py
================

Next-level RGPUF demo using rgpuf_core.py.

RGPUF Lab v4 -- Micro-World Forge

Runs campaign experiments:
- baseline vs adaptive
- per-mode audit
- law contribution analysis
- stress/failure envelope
- optimizer search
- micro-world recipe extraction

This file should stay thin. All reusable mechanics live in rgpuf_core.py.

Run:
    python rgpuf_lab_v4.py --campaign compare --steps 240 --seed 42
    python rgpuf_lab_v4.py --campaign audit --mode colony --steps 240
    python rgpuf_lab_v4.py --campaign stress --mode pressure --max-steps 2000
    python rgpuf_lab_v4.py --campaign optimize --mode colony --episodes 30
    python rgpuf_lab_v4.py --campaign baseline --steps 240 --csv telemetry.csv
    python rgpuf_lab_v4.py --campaign compare --report report.md
"""

from __future__ import annotations

import argparse
import sys
import time

from rgpuf_core import (
    BASE_MODES,
    LAW_REGISTRY,
    SimConfig,
    Telemetry,
    audit_mode,
    optimize_mode,
    print_telemetry,
    run_campaign_adaptive,
    run_campaign_audit,
    run_campaign_baseline,
    run_campaign_compare,
    run_campaign_optimize,
    run_campaign_stress,
    run_sim,
    stress_mode,
    write_csv,
    write_json,
    write_markdown_report,
    final_pr,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Result Printers
# ═══════════════════════════════════════════════════════════════════════════════


def print_comparison_table(comparison: dict) -> None:
    """Print the v4 comparison table to terminal."""
    print()
    print("RGPUF Lab v4 -- Micro-World Forge")
    print("core: rgpuf_core.py | demo: rgpuf_lab_v4.py")
    print()
    header = (
        f"{'MODE':<12} {'PR_BASE':>8} {'PR_ADAPT':>8} {'PR_OPT':>8} "
        f"{'DELTA':>7} {'AGENCY':>7} {'COVER':>6} {'LAW_COST':>8} {'LAWS':>5}"
    )
    print(header)
    print("-" * len(header))

    for mode, info in comparison.items():
        pr_base = info.get("pr_base", 0)
        pr_adapt = info.get("pr_adapt", 0)
        pr_opt = info.get("pr_opt", 0)
        delta = info.get("delta_opt", 0)
        agency = info.get("agency_adapt", 0)
        cover = info.get("coverage_adapt", 0)
        cost = info.get("law_cost_adapt", 0)

        print(
            f"{mode:<12} {pr_base:8.3f} {pr_adapt:8.3f} {pr_opt:8.3f} "
            f"{delta:+7.3f} {agency:7.2f} {cover:6.2f} {cost:8.1f} "
            f"{'N/A':>5}"
        )


def print_audit_results(audit: dict) -> None:
    """Print audit results for a mode."""
    print()
    print(f"AUDIT -- {audit['mode']}")
    print(f"  Final PR_norm:  {audit['final_pr_norm']:.4f}")
    print(f"  Law Cost:       {audit['law_cost']:.2f}")
    print(f"  Law Count:      {audit['law_count']}")
    print(f"  Coverage:       {audit['coverage']:.4f}")
    print(f"  Goal Agency:    {audit['goal_agency']:.4f}")
    print(f"  Active Laws:    {', '.join(audit['active_laws'])}")
    print()
    print(f"  LAW CONTRIBUTION -- {audit['mode']}")
    print(f"  {'law':<30} {'contribution':>12} {'executed':>9} {'verdict':>8}")
    print(f"  {'-'*61}")

    for law, info in audit["contributions"].items():
        contrib = info["contribution"]
        executed = "yes" if info["executed"] else "no"
        verdict = info["verdict"]
        print(f"  {law:<30} {contrib:+12.4f} {executed:>9} {verdict:>8}")

    if audit["dead_laws"]:
        print(f"\n  Dead laws (recommended removal): {', '.join(audit['dead_laws'])}")
    else:
        print(f"\n  No dead laws detected.")


def print_stress_results(results: dict) -> None:
    """Print stress test results."""
    print()
    print("STRESS TEST RESULTS")
    print(f"  {'Seed':>8} {'TTF':>6} {'Failed':>7} {'Reason':>10} {'PR':>8} {'Agency':>7}")
    print(f"  {'-'*52}")

    for seed_key, info in results.items():
        print(
            f"  {seed_key:>8} {info['ttf']:6d} "
            f"{'yes' if info['failed'] else 'no':>7} "
            f"{info['failure_reason']:>10} "
            f"{info['final_pr']:8.4f} {info['final_agency']:7.4f}"
        )


def print_optimize_results(opt: dict) -> None:
    """Print optimization results."""
    print()
    print(f"OPTIMIZER -- {opt['mode']}")
    print(f"  Episodes: {opt['episodes']}")
    print(f"  Best PR: {opt['best_pr']:.4f}")
    bp = opt["best_params"]
    print(f"  Best Params:")
    print(f"    wall_density: {bp.get('wall_density', '?')}")
    print(f"    policy:       {bp.get('policy', '?')}")
    print(f"    seed:         {bp.get('seed', '?')}")
    print()
    print(f"  TOP 5 CONFIGURATIONS:")
    print(f"  {'#':>3} {'seed':>6} {'wall_d':>7} {'policy':>12} {'PR':>8} {'agency':>7} {'cover':>6}")
    print(f"  {'-'*54}")
    for i, r in enumerate(opt.get("top_5", [])):
        print(
            f"  {i+1:>3} {r['seed']:6d} {r['wall_density']:7.2f} "
            f"{r['policy']:>12} {r['pr']:8.4f} {r['agency']:7.4f} {r['coverage']:6.4f}"
        )


def print_baseline_results(results: dict) -> None:
    """Print baseline campaign results."""
    print()
    print("BASELINE CAMPAIGN RESULTS")
    print(f"  {'MODE':<12} {'PR_norm':>8} {'PR_raw':>8} {'Agency':>7} "
          f"{'Coverage':>8} {'LawCost':>8} {'Laws':>5}")
    print(f"  {'-'*60}")

    for mode in BASE_MODES:
        tel = results.get(mode, [])
        if tel:
            last = tel[-1]
            print(
                f"  {mode:<12} {last.pr_norm:8.4f} {last.pr:8.4f} "
                f"{last.goal_agency:7.4f} {last.coverage:8.4f} "
                f"{last.law_cost:8.2f} {last.law_count:5d}"
            )


def print_adaptive_results(results: dict) -> None:
    """Print adaptive campaign results."""
    print()
    print("ADAPTIVE CAMPAIGN RESULTS (DLASc + HDC)")
    print(f"  {'MODE':<12} {'PR_norm':>8} {'PR_raw':>8} {'Agency':>7} "
          f"{'Coverage':>8} {'LawCost':>8} {'Godel':>6}")
    print(f"  {'-'*60}")

    for mode in BASE_MODES:
        tel = results.get(mode, [])
        if tel:
            last = tel[-1]
            print(
                f"  {mode:<12} {last.pr_norm:8.4f} {last.pr:8.4f} "
                f"{last.goal_agency:7.4f} {last.coverage:8.4f} "
                f"{last.law_cost:8.2f} {last.godel_tokens:6d}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Micro-World Recipe Extraction
# ═══════════════════════════════════════════════════════════════════════════════


def extract_recipe(
    mode: str, seed: int, steps: int, config: SimConfig,
) -> dict:
    """Extract a micro-world recipe from an optimized run."""
    from rgpuf_core import run_sim, DLASc, make_state, step_sim

    # Run with adaptive to discover laws
    dlas = DLASc(LAW_REGISTRY)
    tel = run_sim(mode, seed, steps, config, dlas=dlas)

    last = tel[-1] if tel else None
    if not last:
        return {"mode": mode, "error": "no telemetry"}

    # Find failure boundary
    failure_step = -1
    failure_reason = "none"
    for t in tel:
        if t.failure_state != "active":
            failure_step = t.step
            failure_reason = t.failure_state
            break

    # Build recipe
    recipe = {
        "name": f"{mode.title()} Escape",
        "mode": mode,
        "seed": seed,
        "law_stack": last.active_laws.split(","),
        "agent_policy": config.agent_policy if config.adaptive else "naive",
        "goal": "maximize_coverage" if mode == "colony" else "maximize_pr",
        "failure": failure_reason if failure_step >= 0 else "none",
        "failure_step": failure_step,
        "topology": "cell_torus" if mode == "colony" else "continuous",
        "results": {
            "laws": len(last.active_laws.split(",")),
            "law_cost": round(last.law_cost, 2),
            "pr_norm": round(last.pr_norm, 4),
            "pr_raw": round(last.pr, 4),
            "coverage": round(last.coverage, 4),
            "goal_agency": round(last.goal_agency, 4),
            "godel_tokens": last.godel_tokens,
        },
    }

    # Count dead laws (from DLASc contribution tracking)
    dead = []
    for law in last.active_laws.split(","):
        if dlas.execution_counts.get(law, 0) == 0:
            dead.append(law)
        elif dlas.contribution_scores.get(law, 0) < -0.05:
            dead.append(law)
    recipe["dead_laws_removed"] = dead
    recipe["results"]["dead_count"] = len(dead)

    return recipe


def print_recipe(recipe: dict) -> None:
    """Print a micro-world recipe."""
    print()
    print("BEST MICRO-WORLD RECIPE")
    print(f"  Name:            {recipe['name']}")
    print(f"  Mode:            {recipe['mode']}")
    print(f"  Seed:            {recipe['seed']}")
    r = recipe["results"]
    print(f"  Laws:            {r['laws']}")
    print(f"  LawCost:         {r['law_cost']}")
    print(f"  PR_norm:         {r['pr_norm']}")
    print(f"  Coverage:        {r['coverage']}")
    print(f"  Failure:         {recipe['failure']} at T={recipe['failure_step']}")
    if recipe["dead_laws_removed"]:
        print(f"  Dead Laws:       {', '.join(recipe['dead_laws_removed'])}")
    print(f"  Law Stack:       {', '.join(recipe['law_stack'])}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Automatic Diagnosis
# ═══════════════════════════════════════════════════════════════════════════════


def print_diagnosis(mode: str, baseline_pr: float, adaptive_pr: float,
                    adaptive_tel: list[Telemetry]) -> None:
    """Print automatic diagnosis of mode improvements."""
    last = adaptive_tel[-1] if adaptive_tel else None
    if not last:
        return

    print()
    print(f"DIAGNOSIS -- {mode}")
    print(f"  Problem in v3:")
    print(f"    - PR was crushed by global registry law cost.")
    print(f"    - Agency was inflated by action success instead of goal success.")
    if mode == "colony":
        print(f"    - Cell movement improved but coverage remained low.")
        print(f"    - Teleport law was present but rarely executed.")
    elif mode == "pressure":
        print(f"    - Agency was false-perfect because actions counted even when pressure rose.")
        print(f"    - Hysteresis excess never decayed.")
    elif mode == "freescape":
        print(f"    - Zone changes were on timer, not position.")
    elif mode == "semantic":
        print(f"    - Metrics computed once then repeated -- no live data.")

    print(f"\n  v4 repair:")
    print(f"    - LawStack now counts only executed mode laws (cost: {last.law_cost:.1f}).")
    print(f"    - Goal agency uses mode-specific useful action criteria.")
    print(f"    - HDC anomalies buy repair trials via Gödel tokens.")
    print(f"    - State density measured from unique signatures.")
    print(f"    - Prediction error from transition-based predictor.")

    delta = adaptive_pr - baseline_pr
    print(f"\n  Result:")
    print(f"    PR_norm: {baseline_pr:.3f} -> {adaptive_pr:.3f} ({delta:+.3f})")
    print(f"    LawCost: N/A -> {last.law_cost:.1f}")
    print(f"    Coverage: N/A -> {last.coverage:.2f}")
    print(f"    Goal Agency: N/A -> {last.goal_agency:.2f}")
    print(f"    Gödel Tokens: {last.godel_tokens}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="RGPUF Lab v4 -- Micro-World Forge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Campaigns:
  baseline   Run all modes with minimal static stacks
  adaptive   Run all modes with DLASc + HDC enabled
  stress     Run until failure or max steps
  audit      Compute law contribution and dead laws
  optimize   Grid search over parameters
  compare    Run baseline vs adaptive vs optimized

Examples:
  python rgpuf_lab_v4.py --campaign compare --steps 240 --seed 42
  python rgpuf_lab_v4.py --campaign audit --mode colony --steps 240
  python rgpuf_lab_v4.py --campaign stress --mode pressure --max-steps 2000
  python rgpuf_lab_v4.py --campaign optimize --mode colony --episodes 30
  python rgpuf_lab_v4.py --campaign baseline --steps 240 --csv telemetry.csv
  python rgpuf_lab_v4.py --campaign compare --report report.md
        """,
    )
    parser.add_argument(
        "--campaign", default="compare",
        choices=["baseline", "adaptive", "stress", "audit", "optimize", "compare"],
        help="Which campaign to run (default: compare)",
    )
    parser.add_argument(
        "--mode", default="colony",
        choices=BASE_MODES,
        help="Target mode for audit/stress/optimize (default: colony)",
    )
    parser.add_argument(
        "--steps", type=int, default=240,
        help="Number of simulation steps (default: 240)",
    )
    parser.add_argument(
        "--max-steps", type=int, default=2000,
        help="Max steps for stress testing (default: 2000)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--episodes", type=int, default=30,
        help="Number of optimization episodes (default: 30)",
    )
    parser.add_argument(
        "--csv", default=None,
        help="Output CSV file path",
    )
    parser.add_argument(
        "--json", default=None,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--report", default=None,
        help="Output Markdown report path",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress terminal output (except final results)",
    )
    args = parser.parse_args()

    config = SimConfig(
        max_steps=args.steps,
        wall_density=0.45,
        hdc_dim=1024,
    )

    t0 = time.time()

    # ---- BASELINE ----
    if args.campaign == "baseline":
        print(f"Running baseline campaign: {args.steps} steps, seed={args.seed}")
        results = run_campaign_baseline(args.seed, args.steps, config)

        # Print live telemetry (sampled)
        if not args.quiet:
            for mode in BASE_MODES:
                for t in results[mode]:
                    print_telemetry(t, interval=48)

        print_baseline_results(results)

        # Export
        all_tel = []
        for mode in BASE_MODES:
            all_tel.extend(results[mode])
        if args.csv:
            write_csv(all_tel, args.csv)
            print(f"\n  CSV written to {args.csv}")
        if args.json:
            summary = {
                mode: {
                    "pr_norm": results[mode][-1].pr_norm if results[mode] else 0,
                    "pr_raw": results[mode][-1].pr if results[mode] else 0,
                    "goal_agency": results[mode][-1].goal_agency if results[mode] else 0,
                    "coverage": results[mode][-1].coverage if results[mode] else 0,
                    "law_cost": results[mode][-1].law_cost if results[mode] else 0,
                    "active_laws": results[mode][-1].active_laws if results[mode] else "",
                }
                for mode in BASE_MODES
            }
            write_json(summary, args.json)
            print(f"  JSON written to {args.json}")

    # ---- ADAPTIVE ----
    elif args.campaign == "adaptive":
        print(f"Running adaptive campaign: {args.steps} steps, seed={args.seed}")
        results = run_campaign_adaptive(args.seed, args.steps, config)

        if not args.quiet:
            for mode in BASE_MODES:
                for t in results[mode]:
                    print_telemetry(t, interval=48)

        print_adaptive_results(results)

        all_tel = []
        for mode in BASE_MODES:
            all_tel.extend(results[mode])
        if args.csv:
            write_csv(all_tel, args.csv)
            print(f"\n  CSV written to {args.csv}")
        if args.json:
            summary = {
                mode: {
                    "pr_norm": results[mode][-1].pr_norm if results[mode] else 0,
                    "godel_tokens": results[mode][-1].godel_tokens if results[mode] else 0,
                    "active_laws": results[mode][-1].active_laws if results[mode] else "",
                }
                for mode in BASE_MODES
            }
            write_json(summary, args.json)
            print(f"  JSON written to {args.json}")

    # ---- STRESS ----
    elif args.campaign == "stress":
        print(f"Running stress test: mode={args.mode}, max_steps={args.max_steps}, seed={args.seed}")
        results = run_campaign_stress(args.mode, args.seed, args.max_steps, config)
        print_stress_results(results)

        if args.json:
            write_json(results, args.json)
            print(f"\n  JSON written to {args.json}")

    # ---- AUDIT ----
    elif args.campaign == "audit":
        print(f"Running audit: mode={args.mode}, steps={args.steps}, seed={args.seed}")
        audit = run_campaign_audit(args.mode, args.seed, args.steps, config)
        print_audit_results(audit)

        if args.json:
            write_json(audit, args.json)
            print(f"\n  JSON written to {args.json}")

    # ---- OPTIMIZE ----
    elif args.campaign == "optimize":
        print(f"Running optimizer: mode={args.mode}, episodes={args.episodes}, seed={args.seed}")
        opt = run_campaign_optimize(args.mode, args.seed, args.episodes, config)
        print_optimize_results(opt)

        # Also extract best recipe
        if opt["best_params"]:
            bp = opt["best_params"]
            best_cfg = SimConfig(
                adaptive=(bp.get("policy", "naive") != "naive"),
                agent_policy=bp.get("policy", "naive"),
                wall_density=bp.get("wall_density", 0.45),
                max_steps=args.steps,
                hdc_dim=config.hdc_dim,
            )
            recipe = extract_recipe(
                args.mode, bp.get("seed", args.seed),
                args.steps, best_cfg,
            )
            print_recipe(recipe)

        if args.json:
            write_json(opt, args.json)
            print(f"\n  JSON written to {args.json}")

    # ---- COMPARE ----
    elif args.campaign == "compare":
        print(f"Running comparison campaign: {args.steps} steps, seed={args.seed}")
        data = run_campaign_compare(args.seed, args.steps, config)

        comparison = data["comparison"]
        print_comparison_table(comparison)

        # Diagnosis for each mode
        baseline = data["baseline"]
        adaptive = data["adaptive"]
        for mode in BASE_MODES:
            bl_tel = baseline.get(mode, [])
            ad_tel = adaptive.get(mode, [])
            if bl_tel and ad_tel:
                bl_pr = final_pr(bl_tel)
                ad_pr = final_pr(ad_tel)
                if not args.quiet:
                    print_diagnosis(mode, bl_pr, ad_pr, ad_tel)

        # Best recipes
        if not args.quiet:
            print("\n" + "=" * 60)
            print("MICRO-WORLD RECIPES")
            print("=" * 60)
            for mode in BASE_MODES:
                opt = optimize_mode(mode, args.seed, episodes=5,
                                   config=SimConfig(
                                       dt=config.dt, max_steps=args.steps,
                                       wall_density=config.wall_density,
                                       hdc_dim=config.hdc_dim,
                                   ))
                bp = opt.get("best_params", {})
                if bp:
                    recipe_cfg = SimConfig(
                        adaptive=(bp.get("policy", "naive") != "naive"),
                        agent_policy=bp.get("policy", "naive"),
                        wall_density=bp.get("wall_density", 0.45),
                        max_steps=args.steps,
                        hdc_dim=config.hdc_dim,
                    )
                    recipe = extract_recipe(
                        mode, bp.get("seed", args.seed),
                        args.steps, recipe_cfg,
                    )
                    print_recipe(recipe)

        # Exports
        all_tel = []
        for mode in BASE_MODES:
            all_tel.extend(data["baseline"].get(mode, []))
            all_tel.extend(data["adaptive"].get(mode, []))

        if args.csv:
            write_csv(all_tel, args.csv)
            print(f"\n  CSV written to {args.csv}")
        if args.json:
            summary = {
                "comparison": comparison,
                "campaign": "compare",
                "steps": args.steps,
                "seed": args.seed,
            }
            write_json(summary, args.json)
            print(f"  JSON written to {args.json}")
        if args.report:
            write_markdown_report(data, args.report)
            print(f"  Report written to {args.report}")

    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
