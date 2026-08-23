"""
Tests for Day 4 — Lift Analysis.

All statistical tests use only observable experiment outcomes.
The simulator ground truth (natural_prob, treatment_effect) is used
ONLY in validation tests to confirm the analyser can correctly
detect known effects from sufficiently large samples.
"""
from django.test import TestCase
from django.core.management import call_command
from recovery.models import Transaction, ExperimentResult
from recovery.experiment_engine import ExperimentEngine
from recovery.lift_analyzer import (
    analyze_experiment, get_result_report,
    _proportion_ci, _lift_ci, _classify_evidence,
    STATUS_INSUFFICIENT, STATUS_POSITIVE, STATUS_NEGATIVE, STATUS_NEUTRAL,
    MIN_SAMPLE_SIZE
)


class ProportionCITest(TestCase):
    """Unit tests for the Wilson CI helper."""

    def test_normal_case(self):
        lo, hi = _proportion_ci(50, 100)
        self.assertAlmostEqual(50 / 100, (lo + hi) / 2, delta=0.05)
        self.assertTrue(lo < 0.5 < hi)

    def test_zero_observations(self):
        lo, hi = _proportion_ci(0, 0)
        self.assertEqual(lo, 0.0)
        self.assertEqual(hi, 0.0)

    def test_zero_successes(self):
        lo, hi = _proportion_ci(0, 200)
        self.assertEqual(lo, 0.0)
        self.assertTrue(hi >= 0.0)

    def test_all_successes(self):
        lo, hi = _proportion_ci(100, 100)
        self.assertTrue(lo > 0.9)
        self.assertAlmostEqual(hi, 1.0, places=5)


class LiftCITest(TestCase):
    """Unit tests for the lift CI helper."""

    def test_positive_lift(self):
        # treatment=0.4, control=0.15  => lift ~ 0.25
        lo, hi = _lift_ci(0.40, 1000, 0.15, 1000)
        self.assertTrue(lo > 0.0)   # CI is entirely positive
        self.assertAlmostEqual((lo + hi) / 2, 0.25, delta=0.02)

    def test_negative_lift(self):
        lo, hi = _lift_ci(0.05, 1000, 0.10, 1000)
        self.assertTrue(hi < 0.0)   # CI is entirely negative

    def test_zero_sample(self):
        lo, hi = _lift_ci(0.0, 0, 0.15, 100)
        self.assertEqual(lo, 0.0)
        self.assertEqual(hi, 0.0)


class EvidenceClassificationTest(TestCase):
    """Unit tests for the evidence classifier."""

    def test_insufficient_sample(self):
        status = _classify_evidence(0.25, 0.15, 0.35, sufficient_sample=False)
        self.assertEqual(status, STATUS_INSUFFICIENT)

    def test_positive_evidence(self):
        # CI entirely above 0
        status = _classify_evidence(0.25, 0.10, 0.40, sufficient_sample=True)
        self.assertEqual(status, STATUS_POSITIVE)

    def test_negative_evidence(self):
        # CI entirely below 0
        status = _classify_evidence(-0.05, -0.12, -0.01, sufficient_sample=True)
        self.assertEqual(status, STATUS_NEGATIVE)

    def test_neutral_evidence(self):
        # CI straddles 0
        status = _classify_evidence(0.03, -0.02, 0.08, sufficient_sample=True)
        self.assertEqual(status, STATUS_NEUTRAL)


class AnalyzeExperimentTest(TestCase):
    """Integration tests for analyze_experiment on small synthetic data."""

    def setUp(self):
        call_command('generate_transactions', count=500, seed=42)
        self.target_segment = Transaction.objects.first().segment

    def test_analyze_produces_results_for_each_treatment(self):
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=self.target_segment,
            arms=['NONE', 'SMS', 'WHATSAPP'],
            random_seed=1
        )
        exp = ExperimentEngine.execute_experiment(exp)
        results = analyze_experiment(exp)

        # One result per treatment arm (not for control itself)
        self.assertEqual(len(results), 2)
        treatments = {r.treatment for r in results}
        self.assertIn('SMS', treatments)
        self.assertIn('WHATSAPP', treatments)

    def test_lift_is_treatment_minus_control(self):
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=self.target_segment,
            arms=['NONE', 'SMS'],
            random_seed=2
        )
        exp = ExperimentEngine.execute_experiment(exp)
        results = analyze_experiment(exp)
        result = results[0]

        expected_lift = result.treatment_rate - result.control_rate
        self.assertAlmostEqual(result.lift, expected_lift, places=6)

    def test_result_persisted_to_db(self):
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=self.target_segment,
            arms=['NONE', 'SMS'],
            random_seed=3
        )
        exp = ExperimentEngine.execute_experiment(exp)
        analyze_experiment(exp)

        db_results = ExperimentResult.objects.filter(experiment=exp)
        self.assertEqual(db_results.count(), 1)

    def test_insufficient_sample_flagged(self):
        """With only a few transactions, sample should be flagged insufficient."""
        call_command('generate_transactions', count=50, seed=99, clear=True)
        # Pick a segment that has very few transactions
        tiny_segment = Transaction.objects.first().segment

        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=tiny_segment,
            arms=['NONE', 'SMS'],
            random_seed=4
        )
        exp = ExperimentEngine.execute_experiment(exp)
        results = analyze_experiment(exp)

        # At least one result (may have very few per arm)
        for result in results:
            if result.control_n < MIN_SAMPLE_SIZE or result.treatment_n < MIN_SAMPLE_SIZE:
                self.assertFalse(result.sufficient_sample)
                self.assertEqual(result.evidence_status, STATUS_INSUFFICIENT)

    def test_get_result_report_structure(self):
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=self.target_segment,
            arms=['NONE', 'DELAYED_RETRY'],
            random_seed=5
        )
        exp = ExperimentEngine.execute_experiment(exp)
        analyze_experiment(exp)
        report = get_result_report(exp)

        self.assertEqual(report['experiment_id'], str(exp.id))
        self.assertIn('control', report)
        self.assertIn('treatments', report)
        self.assertEqual(report['control']['arm'], 'NONE')
        self.assertEqual(len(report['treatments']), 1)
        self.assertIn('lift', report['treatments'][0])
        self.assertIn('ci_lower', report['treatments'][0])
        self.assertIn('evidence_status', report['treatments'][0])

    def test_error_on_incomplete_experiment(self):
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=self.target_segment,
            arms=['NONE', 'SMS'],
            random_seed=6
        )
        # Do NOT execute — status is still CREATED
        with self.assertRaises(ValueError):
            analyze_experiment(exp)


class LiftValidationTest(TestCase):
    """
    Validation tests: verify that sufficiently large randomised experiments
    correctly detect known simulator effects in the expected direction.
    The simulator ground truth (effects) is used here ONLY for the assertion —
    not by the analyser itself.
    """

    def _run_experiment(self, segment, arms, seed, count=3000):
        call_command('generate_transactions', count=count, seed=seed, clear=True)
        # Find first transaction matching the target segment
        matching = Transaction.objects.filter(segment=segment).first()
        if not matching:
            self.skipTest(f"No transactions found for segment '{segment}'")
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=segment,
            arms=arms,
            random_seed=seed
        )
        exp = ExperimentEngine.execute_experiment(exp)
        results = analyze_experiment(exp)
        return {r.treatment: r for r in results}

    def test_strong_positive_effect_detected(self):
        """
        Hidden truth: DELAYED_RETRY on Insufficient Funds has +0.25 effect.
        A large experiment should detect this as POSITIVE evidence.
        """
        results = self._run_experiment(
            segment='UPI | Insufficient Funds | MID_VALUE',
            arms=['NONE', 'DELAYED_RETRY'],
            seed=42
        )
        self.assertIn('DELAYED_RETRY', results)
        r = results['DELAYED_RETRY']
        # Lift should be positive and CI should not straddle zero for large n
        self.assertTrue(r.lift > 0)
        self.assertEqual(r.evidence_status, STATUS_POSITIVE)

    def test_zero_effect_is_neutral(self):
        """
        Hidden truth: IMMEDIATE_RETRY on Insufficient Funds has 0.0 effect.
        Should be NEUTRAL or INSUFFICIENT — never confidently POSITIVE/NEGATIVE.
        """
        results = self._run_experiment(
            segment='UPI | Insufficient Funds | MID_VALUE',
            arms=['NONE', 'IMMEDIATE_RETRY'],
            seed=43
        )
        self.assertIn('IMMEDIATE_RETRY', results)
        r = results['IMMEDIATE_RETRY']
        self.assertIn(r.evidence_status, [STATUS_NEUTRAL, STATUS_INSUFFICIENT])

    def test_negative_effect_detected(self):
        """
        Hidden truth: IMMEDIATE_RETRY on Risk Block has -0.04 effect.
        A large experiment should detect this as NEGATIVE or NEUTRAL.
        """
        results = self._run_experiment(
            segment='UPI | Risk Block | MID_VALUE',
            arms=['NONE', 'IMMEDIATE_RETRY'],
            seed=44
        )
        self.assertIn('IMMEDIATE_RETRY', results)
        r = results['IMMEDIATE_RETRY']
        # Lift direction should be negative (even if CI straddles for small effect)
        self.assertTrue(r.lift <= 0.0)
