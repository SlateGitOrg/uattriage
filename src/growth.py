"""Reliability-growth fitting for UAT readiness.

THE DIFFERENTIATOR LIVES HERE.

"We have 600 open defects" cannot answer "are we ready to go live?", so the
decision gets made on confidence instead. What the project manager actually
needs is: how many defects are still in there, and when does the severity-1
count fall below the agreed threshold?

A defect-discovery curve answers both. The part that matters - and the part
that is almost always skipped - is CALIBRATION: a model that produces a
confident interval which contains the truth only 60% of the time is worse than
no model, because the false precision gets acted on. So the test suite checks
coverage across hundreds of simulated projects, not the fit on one.

Goel-Okumoto NHPP: expected cumulative defects m(t) = a(1 - exp(-b*t)), where
`a` is the total defect content and `b` the discovery rate. Latent defects are
a - n.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


class NotIdentifiable(Exception):
    """The curve has not flattened enough to estimate total defect content.

    This is the Goel-Okumoto degeneracy and it is the single most important
    failure mode to handle. When discovery is still roughly linear, the
    likelihood is almost flat in `b`: the fit drifts toward b -> 0, and since
    a = n / (1 - exp(-b*T)), the estimated total defect content runs away to
    absurd values. The arithmetic never complains.

    A model that returns "we estimate 7.8 billion latent defects" is obviously
    broken. A model that returns 4,200 when the truth is 180 is NOT obviously
    broken, and that is the one that reaches a steering committee. Refusing is
    the correct answer: the data does not yet contain the information.
    """


@dataclass(frozen=True)
class Fit:
    a: float          # total defect content
    b: float          # discovery rate
    n: int            # defects found so far
    horizon: float    # observation window
    se_a: float

    @property
    def latent(self) -> float:
        return max(0.0, self.a - self.n)

    def latent_interval(self, z: float = 1.96) -> tuple[float, float]:
        return (max(0.0, self.a - self.n - z * self.se_a),
                max(0.0, self.a - self.n + z * self.se_a))

    def expected_by(self, t: float) -> float:
        return self.a * (1 - math.exp(-self.b * t))

    def time_to_find(self, fraction: float) -> float:
        """When will `fraction` of all defects have been discovered?"""
        if fraction >= 1.0:
            return math.inf
        return -math.log(1 - fraction) / self.b

    def days_until_latent_below(self, threshold: float) -> float:
        """Days from now until the expected remaining count drops below
        `threshold`, assuming test effort continues at the same intensity."""
        if self.latent <= threshold:
            return 0.0
        target_found = self.a - threshold
        if target_found >= self.a:
            return math.inf
        t = -math.log(1 - target_found / self.a) / self.b
        return max(0.0, t - self.horizon)


def _log_likelihood(a: float, b: float, times: list[float], horizon: float) -> float:
    n = len(times)
    if a <= 0 or b <= 0:
        return -math.inf
    return (
        n * math.log(a) + n * math.log(b)
        - b * sum(times)
        - a * (1 - math.exp(-b * horizon))
    )


def _solve_b(times: list[float], horizon: float) -> float:
    """Root of the profile-likelihood score for b, by bisection.

    Bisection rather than Newton on purpose: the score function is flat when
    discovery has barely slowed, and Newton walks off to a negative b and
    produces a confident, meaningless answer.
    """
    n = len(times)
    total = sum(times)

    def score(b: float) -> float:
        e = math.exp(-b * horizon)
        return n / b - (n * horizon * e) / (1 - e) - total

    lo, hi = 1e-9, 1.0
    while score(hi) > 0 and hi < 1e6:
        hi *= 2
    if score(lo) < 0:
        return lo
    for _ in range(300):
        mid = (lo + hi) / 2
        if score(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


#: Below this, the discovery curve has not flattened enough for the total to
#: be identifiable. b*T = 0.7 corresponds to roughly half the defect content
#: having been found.
MIN_BT = 0.7
#: And a fit claiming the team has found less than this share of the total is
#: extrapolating far beyond its data.
MAX_A_OVER_N = 3.0


def fit(times: list[float], horizon: float, strict: bool = True) -> Fit:
    """Fit Goel-Okumoto to defect discovery times over [0, horizon].

    Raises NotIdentifiable when the curve has not flattened enough to support
    an estimate. Pass strict=False only to inspect the degenerate fit.
    """
    n = len(times)
    if n < 5:
        raise ValueError("too few defects to fit a growth curve")

    b = _solve_b(times, horizon)
    e = math.exp(-b * horizon)
    a = n / (1 - e) if e < 1 else float(n)

    if strict:
        if b * horizon < MIN_BT:
            raise NotIdentifiable(
                f"discovery has not flattened (b*T = {b * horizon:.2f} < "
                f"{MIN_BT}); keep testing before projecting")
        if a > n * MAX_A_OVER_N:
            raise NotIdentifiable(
                f"the fit implies only {n / a:.0%} of defects have been found; "
                f"that is extrapolation, not estimation")

    # Observed information, by finite differences on the log-likelihood.
    # Reporting an interval from an analytic approximation the reader cannot
    # check is how false precision gets into a readiness paper.
    ha = max(a * 1e-4, 1e-6)
    hb = max(b * 1e-4, 1e-9)
    ll = lambda x, y: _log_likelihood(x, y, times, horizon)  # noqa: E731

    daa = (ll(a + ha, b) - 2 * ll(a, b) + ll(a - ha, b)) / (ha * ha)
    dbb = (ll(a, b + hb) - 2 * ll(a, b) + ll(a, b - hb)) / (hb * hb)
    dab = (
        ll(a + ha, b + hb) - ll(a + ha, b - hb)
        - ll(a - ha, b + hb) + ll(a - ha, b - hb)
    ) / (4 * ha * hb)

    # Covariance = inverse of the negative Hessian.
    faa, fbb, fab = -daa, -dbb, -dab
    det = faa * fbb - fab * fab
    var_a = (fbb / det) if det > 0 else float("inf")
    se_a = math.sqrt(var_a) if var_a > 0 and math.isfinite(var_a) else float("inf")

    return Fit(a=a, b=b, n=n, horizon=horizon, se_a=se_a)


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Readiness:
    severity: str
    found: int
    latent_estimate: float
    latent_low: float
    latent_high: float
    days_low: float
    days_high: float
    threshold: float

    @property
    def ready_now(self) -> bool:
        return self.latent_high <= self.threshold

    def describe(self) -> str:
        if self.ready_now:
            return (f"{self.severity}: ready now "
                    f"({self.latent_low:.0f}-{self.latent_high:.0f} remaining, "
                    f"threshold {self.threshold:.0f})")
        return (
            f"{self.severity}: {self.latent_low:.0f}-{self.latent_high:.0f} "
            f"undiscovered defects remain; "
            f"{self.days_low:.0f}-{self.days_high:.0f} days to threshold "
            f"{self.threshold:.0f}"
        )


def readiness(
    times: list[float], horizon: float, severity: str, threshold: float,
) -> Readiness:
    f = fit(times, horizon)
    low, high = f.latent_interval()

    # The optimistic case (few latent defects) reaches the threshold sooner.
    optimistic = Fit(a=f.n + low, b=f.b, n=f.n, horizon=horizon, se_a=f.se_a)
    pessimistic = Fit(a=f.n + high, b=f.b, n=f.n, horizon=horizon, se_a=f.se_a)

    return Readiness(
        severity=severity, found=f.n,
        latent_estimate=f.latent, latent_low=low, latent_high=high,
        days_low=optimistic.days_until_latent_below(threshold),
        days_high=pessimistic.days_until_latent_below(threshold),
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# Assumption checks
# ---------------------------------------------------------------------------

def constant_effort_violated(
    times: list[float], horizon: float, tolerance: float = 0.25,
) -> bool:
    """Goel-Okumoto assumes test effort is roughly constant.

    If the team doubled the number of testers half way through, the curve
    flattening is an effort artefact rather than defect exhaustion, and the
    projection is wrong in the REASSURING direction - the worst direction for
    a go-live decision.

    Comparing raw half-counts does not work: under constant effort the second
    half always finds fewer, so a step change can still leave it lower. The
    check that does work is to fit the FIRST half and compare the second
    half's actual discovery against what that fit predicts.
    """
    mid = horizon / 2
    first = [t for t in times if t <= mid]
    second_count = len(times) - len(first)
    if len(first) < 5:
        return True

    try:
        f = fit(first, mid, strict=False)
    except ValueError:
        return True

    predicted = f.expected_by(horizon) - f.expected_by(mid)
    if predicted <= 0:
        return second_count > 0
    return (second_count - predicted) / predicted > tolerance
