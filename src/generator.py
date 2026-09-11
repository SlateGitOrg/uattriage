"""Simulated UAT projects with a KNOWN total defect content.

The calibration test needs hundreds of independent projects whose true latent
count is known, because calibration is a property of the ESTIMATOR across
projects, not of one fit. A single fit that happens to be close proves nothing.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

SEVERITIES = ("sev1", "sev2", "sev3")
#: Share of total defects, and how much harder each is to find.
SEVERITY_MIX: dict[str, tuple[float, float]] = {
    "sev1": (0.08, 0.7),    # rarer, and harder to trip over
    "sev2": (0.27, 0.9),
    "sev3": (0.65, 1.0),
}

MODULES = ("payments", "eligibility", "notifications", "reporting", "admin")


@dataclass(frozen=True)
class Defect:
    found_at: float       # days into UAT
    severity: str
    module: str
    reopened: bool


@dataclass(frozen=True)
class Project:
    defects: list[Defect]
    horizon: float
    #: GROUND TRUTH: total defect content by severity, most of it undiscovered.
    true_total: dict[str, int]

    def times(self, severity: str | None = None) -> list[float]:
        return sorted(
            d.found_at for d in self.defects
            if severity is None or d.severity == severity
        )

    def true_latent(self, severity: str) -> int:
        return self.true_total[severity] - len(self.times(severity))


def simulate_project(
    total_defects: int = 900,
    discovery_rate: float = 0.055,
    horizon: float = 45.0,
    seed: int = 1,
    #: Set to model a mid-UAT increase in test effort, which breaks the model's
    #: constant-effort assumption in a way that flatters the projection.
    effort_step_at: float | None = None,
) -> Project:
    rnd = random.Random(seed)
    defects: list[Defect] = []
    true_total: dict[str, int] = {}

    for severity, (share, difficulty) in SEVERITY_MIX.items():
        count = int(total_defects * share)
        true_total[severity] = count
        rate = discovery_rate * difficulty

        for _ in range(count):
            # Each defect's discovery time is exponential with rate `b`;
            # those beyond the horizon are simply never found, which is exactly
            # what "latent" means.
            t = rnd.expovariate(rate)
            if effort_step_at is not None and t > effort_step_at:
                # More testers after the step: everything still outstanding is
                # found sooner.
                t = effort_step_at + (t - effort_step_at) / 2.2
            if t > horizon:
                continue
            defects.append(Defect(
                found_at=t,
                severity=severity,
                module=rnd.choices(
                    MODULES, weights=[0.34, 0.24, 0.16, 0.14, 0.12])[0],
                reopened=rnd.random() < (0.18 if severity == "sev1" else 0.07),
            ))

    return Project(defects=defects, horizon=horizon, true_total=true_total)


def module_concentration(project: Project, severity: str = "sev1") -> list[
    tuple[str, int, float]
]:
    """Which modules hold the severity-1 defects, and by how much."""
    rows = [d for d in project.defects if d.severity == severity]
    total = len(rows) or 1
    counts: dict[str, int] = {}
    for d in rows:
        counts[d.module] = counts.get(d.module, 0) + 1
    return sorted(
        ((m, c, c / total) for m, c in counts.items()),
        key=lambda x: -x[1],
    )


def reopen_rate(project: Project, severity: str | None = None) -> float:
    """'Closed' is not 'fixed'. A high reopen rate means the closure curve is
    measuring administration rather than progress."""
    rows = [
        d for d in project.defects
        if severity is None or d.severity == severity
    ]
    if not rows:
        return 0.0
    return sum(1 for d in rows if d.reopened) / len(rows)


def theoretical_latent(
    total: int, rate: float, horizon: float, difficulty: float = 1.0,
) -> float:
    return total * math.exp(-rate * difficulty * horizon)
