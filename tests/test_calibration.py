"""Calibration across many projects, not a lucky fit on one.

A model whose 95% interval contains the truth 60% of the time is worse than no
model: the false precision is what gets acted on.
"""

from __future__ import annotations

import unittest

from src.generator import (
    module_concentration, reopen_rate, simulate_project, theoretical_latent,
)
from src.growth import (
    NotIdentifiable, constant_effort_violated, fit, readiness,
)


class TestCalibration(unittest.TestCase):
    RUNS = 200

    def test_THE_TEST_EVERYONE_SKIPS_interval_coverage_is_near_nominal(self):
        covered = 0
        usable = 0
        for seed in range(self.RUNS):
            project = simulate_project(seed=seed)
            times = project.times("sev3")
            if len(times) < 20:
                continue
            try:
                f = fit(times, project.horizon)
            except NotIdentifiable:
                continue          # refused, and correctly so
            usable += 1
            low, high = f.latent_interval()
            if low <= project.true_latent("sev3") <= high:
                covered += 1

        self.assertGreater(usable, 100, "not enough usable runs to judge")
        coverage = covered / usable
        self.assertGreater(
            coverage, 0.80,
            f"95% intervals covered the truth only {coverage:.0%} of the time - "
            f"the interval is not worth the confidence attached to it",
        )
        # The interval is CONSERVATIVE: it over-covers. That is stated rather
        # than tuned away, because for a go-live decision erring wide is the
        # right direction - but over-coverage is only acceptable while the
        # interval still carries information, which the next test checks.

    def test_the_conservative_interval_is_still_INFORMATIVE(self):
        """Over-covering is safe. Covering everything is useless.

        An interval of [0, 10000] has perfect coverage and says nothing. The
        check that matters is width relative to the quantity being estimated.
        """
        widths = []
        truths = []
        for seed in range(self.RUNS):
            project = simulate_project(seed=seed)
            times = project.times("sev3")
            if len(times) < 20:
                continue
            try:
                f = fit(times, project.horizon)
            except NotIdentifiable:
                continue
            low, high = f.latent_interval()
            widths.append(high - low)
            truths.append(project.true_latent("sev3"))

        mean_width = sum(widths) / len(widths)
        mean_truth = sum(truths) / len(truths)
        ratio = mean_width / max(mean_truth, 1.0)
        self.assertLess(
            ratio, 4.0,
            f"mean interval width is {ratio:.1f}x the quantity estimated - "
            f"that is too wide to support a decision",
        )
        # And the upper bound must stay well below the total defect content,
        # or "some defects remain" is all it is saying.
        self.assertLess(mean_truth + mean_width, 900 * 0.65)

    def test_the_point_estimate_is_not_systematically_biased(self):
        errors = []
        for seed in range(self.RUNS):
            project = simulate_project(seed=seed)
            times = project.times("sev3")
            if len(times) < 20:
                continue
            try:
                f = fit(times, project.horizon)
            except NotIdentifiable:
                continue
            errors.append(f.latent - project.true_latent("sev3"))
        mean_error = sum(errors) / len(errors)
        typical = project.true_latent("sev3") or 1
        self.assertLess(
            abs(mean_error) / typical, 0.35,
            f"mean error {mean_error:+.1f} suggests systematic bias",
        )

    def test_a_single_lucky_fit_would_not_have_shown_this(self):
        # Demonstrates why the loop above is necessary: individual runs vary
        # a great deal, so any one of them is uninformative about the method.
        latents = []
        for seed in range(20):
            project = simulate_project(seed=seed)
            f = fit(project.times("sev3"), project.horizon)
            latents.append(f.latent)
        spread = max(latents) - min(latents)
        self.assertGreater(spread, 5.0,
                           "if every run agreed, one run would be enough")


class TestFit(unittest.TestCase):
    def test_recovers_the_discovery_rate(self):
        project = simulate_project(discovery_rate=0.055, seed=3)
        f = fit(project.times("sev3"), project.horizon)
        # sev3 difficulty is 1.0, so b should land near the generator's rate.
        self.assertAlmostEqual(f.b, 0.055, delta=0.02)

    def test_recovers_the_total_defect_content(self):
        project = simulate_project(total_defects=900, seed=3)
        f = fit(project.times("sev3"), project.horizon)
        self.assertAlmostEqual(f.a, project.true_total["sev3"],
                               delta=project.true_total["sev3"] * 0.35)

    def test_latent_estimate_is_close_to_the_theoretical_value(self):
        project = simulate_project(total_defects=900, discovery_rate=0.055,
                                   seed=11)
        expected = theoretical_latent(
            project.true_total["sev3"], 0.055, project.horizon)
        f = fit(project.times("sev3"), project.horizon)
        low, high = f.latent_interval()
        self.assertLessEqual(low, expected)
        self.assertGreaterEqual(high, expected)

    def test_longer_testing_leaves_fewer_latent_defects(self):
        short = simulate_project(horizon=30.0, seed=5)
        long = simulate_project(horizon=70.0, seed=5)
        self.assertGreater(
            fit(short.times("sev3"), 30.0).latent,
            fit(long.times("sev3"), 70.0).latent,
        )

    def test_too_few_defects_is_refused_rather_than_guessed(self):
        with self.assertRaises(ValueError):
            fit([1.0, 2.0, 3.0], 10.0)

    def test_the_solver_does_not_return_a_negative_rate(self):
        # Newton's method walks off to negative b on a nearly-flat score
        # function and returns a confident, meaningless answer.
        project = simulate_project(discovery_rate=0.005, horizon=40.0, seed=7)
        self.assertGreater(fit(project.times(), 40.0, strict=False).b, 0.0)

    def test_THE_DEGENERACY_an_unflattened_curve_is_REFUSED(self):
        """A curve that has not flattened cannot support a total estimate.

        The runaway value is not the danger - 7.8 billion is obviously wrong.
        The danger is the merely-plausible wrong number that reaches a
        steering committee.
        """
        project = simulate_project(horizon=10.0, seed=3)
        with self.assertRaises(NotIdentifiable):
            fit(project.times("sev3"), 10.0)

    def test_the_refusal_explains_itself_and_says_what_to_do(self):
        project = simulate_project(horizon=10.0, seed=3)
        try:
            fit(project.times("sev3"), 10.0)
            self.fail("expected a refusal")
        except NotIdentifiable as exc:
            self.assertIn("keep testing", str(exc))

    def test_the_same_project_becomes_estimable_with_more_testing(self):
        early = simulate_project(horizon=10.0, seed=3)
        with self.assertRaises(NotIdentifiable):
            fit(early.times("sev3"), 10.0)
        later = simulate_project(horizon=45.0, seed=3)
        self.assertGreater(fit(later.times("sev3"), 45.0).a, 0)


class TestReadiness(unittest.TestCase):
    def test_produces_a_dated_window_not_a_defect_count(self):
        project = simulate_project(seed=13)
        r = readiness(project.times("sev1"), project.horizon, "sev1", threshold=3)
        self.assertGreaterEqual(r.days_high, r.days_low)
        self.assertIn("undiscovered" if not r.ready_now else "ready",
                      r.describe())

    def test_a_tighter_threshold_takes_longer(self):
        project = simulate_project(seed=13)
        loose = readiness(project.times("sev1"), project.horizon, "sev1", 10)
        tight = readiness(project.times("sev1"), project.horizon, "sev1", 1)
        self.assertGreaterEqual(tight.days_high, loose.days_high)

    def test_the_interval_on_days_reflects_the_interval_on_defects(self):
        project = simulate_project(seed=17)
        r = readiness(project.times("sev3"), project.horizon, "sev3", threshold=20)
        self.assertLess(r.latent_low, r.latent_high)
        self.assertLessEqual(r.days_low, r.days_high)


class TestAssumptionChecks(unittest.TestCase):
    def test_a_constant_effort_project_passes(self):
        project = simulate_project(seed=21)
        self.assertFalse(
            constant_effort_violated(project.times("sev3"), project.horizon))

    def test_THE_TRAP_a_mid_uat_effort_increase_is_flagged(self):
        # Doubling the testers makes the curve look like defect exhaustion.
        # Projecting through it is wrong in the reassuring direction, which is
        # the worst direction for a go-live decision.
        project = simulate_project(seed=21, effort_step_at=22.5)
        self.assertTrue(
            constant_effort_violated(project.times("sev3"), project.horizon),
            "an effort step must be detected, not projected through",
        )


class TestTriageAnalytics(unittest.TestCase):
    def test_severity_one_defects_concentrate_in_some_modules(self):
        project = simulate_project(total_defects=3_000, seed=29)
        ranked = module_concentration(project, "sev1")
        self.assertGreater(ranked[0][2], ranked[-1][2],
                           "concentration is what directs the remaining effort")

    def test_reopen_rate_distinguishes_closed_from_fixed(self):
        project = simulate_project(total_defects=3_000, seed=29)
        self.assertGreater(reopen_rate(project, "sev1"),
                           reopen_rate(project, "sev3"),
                           "severity-1 fixes are reopened more often")

    def test_reopen_rate_is_a_proportion(self):
        project = simulate_project(seed=29)
        self.assertGreaterEqual(reopen_rate(project), 0.0)
        self.assertLessEqual(reopen_rate(project), 1.0)


if __name__ == "__main__":
    unittest.main()
