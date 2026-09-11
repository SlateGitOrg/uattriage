"""The 60-second artefact: a readiness window, and a refusal.

Run: python -m src.demo
"""

from __future__ import annotations

from .generator import module_concentration, reopen_rate, simulate_project
from .growth import NotIdentifiable, constant_effort_violated, fit, readiness

THRESHOLDS = {"sev1": 2.0, "sev2": 15.0, "sev3": 60.0}


def main() -> None:
    project = simulate_project(total_defects=900, seed=20260911)

    print("\n  UATTRIAGE - 'are we ready to go live?'")
    print("  " + "=" * 74)
    print(f"  {len(project.defects)} defects raised over "
          f"{project.horizon:.0f} days of UAT.\n")

    print("  WHAT THE DEFECT COUNT SAYS")
    print("  " + "-" * 74)
    for severity in ("sev1", "sev2", "sev3"):
        print(f"    {severity}: {len(project.times(severity)):>4} raised")
    print("    ...and that is the whole of it. No basis for the decision.\n")

    print("  WHAT THE DISCOVERY CURVE SAYS")
    print("  " + "-" * 74)
    print(f"    {'severity':<10}{'found':>7}{'latent (95%)':>18}"
          f"{'days to threshold':>20}")
    for severity, threshold in THRESHOLDS.items():
        r = readiness(project.times(severity), project.horizon,
                      severity, threshold)
        latent = f"{r.latent_low:.0f}-{r.latent_high:.0f}"
        days = ("ready now" if r.ready_now
                else f"{r.days_low:.0f}-{r.days_high:.0f}")
        print(f"    {severity:<10}{r.found:>7}{latent:>18}{days:>20}")

    worst = max(
        (readiness(project.times(s), project.horizon, s, t)
         for s, t in THRESHOLDS.items()),
        key=lambda r: r.days_high,
    )
    print(f"\n    Binding constraint: {worst.describe()}\n")

    print("  ASSUMPTION CHECK")
    print("  " + "-" * 74)
    violated = constant_effort_violated(project.times("sev3"), project.horizon)
    print(f"    constant test effort: {'VIOLATED' if violated else 'holds'}")

    stepped = simulate_project(seed=20260911,
                               effort_step_at=project.horizon / 2)
    stepped_violated = constant_effort_violated(
        stepped.times("sev3"), stepped.horizon)
    print(f"    same project with the team doubled at the halfway point: "
          f"{'VIOLATED' if stepped_violated else 'holds'}")
    print("    Doubling the testers makes the curve flatten for a reason that")
    print("    has nothing to do with running out of defects. Projecting")
    print("    through it is wrong in the reassuring direction.\n")

    print("  THE REFUSAL")
    print("  " + "-" * 74)
    early = simulate_project(horizon=10.0, seed=3)
    print(f"    Same project, asked after only {early.horizon:.0f} days:")
    try:
        f = fit(early.times("sev3"), early.horizon)
        print(f"      estimate: {f.latent:,.0f} latent defects")
    except NotIdentifiable as exc:
        print(f"      REFUSED: {exc}")
    degenerate = fit(early.times("sev3"), early.horizon, strict=False)
    print(f"    Without the guard it would have answered: "
          f"{degenerate.latent:,.0f} latent defects.")
    print("    The runaway value is not the danger - it is obviously wrong.")
    print("    The danger is the merely-plausible wrong number, and the guard")
    print("    catches both.\n")

    print("  TRIAGE")
    print("  " + "-" * 74)
    print("    severity-1 concentration by module:")
    for module, count, share in module_concentration(project, "sev1")[:3]:
        print(f"      {module:<16}{count:>4}  ({share:.0%})")
    print(f"\n    sev1 reopen rate: {reopen_rate(project, 'sev1'):.0%}   "
          f"sev3: {reopen_rate(project, 'sev3'):.0%}")
    print("    'Closed' is not 'fixed'. A closure curve built on reopened")
    print("    defects measures administration, not progress.\n")


if __name__ == "__main__":
    main()
