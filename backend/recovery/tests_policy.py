"""
Tests for Day 5 — Policy Engine.

Tests use ExperimentResult fixture objects built directly from known evidence
status values — NOT from simulator ground truth — to verify policy decisions.
"""
from django.test import TestCase
from django.core.management import call_command

from recovery.models import Transaction, Policy, ExperimentResult, Experiment
from recovery.experiment_engine import ExperimentEngine
from recovery.lift_analyzer import (
    analyze_experiment,
    STATUS_POSITIVE, STATUS_NEUTRAL, STATUS_INSUFFICIENT, STATUS_NEGATIVE,
)
from recovery.policy_engine import (
    select_action_from_results, update_policy,
    get_current_policy, get_policy_for_segment,
)

import uuid


def _make_result(experiment, segment, treatment, evidence_status, lift=0.10):
    """Helper: create an ExperimentResult with the given evidence status."""
    return ExperimentResult.objects.create(
        experiment=experiment,
        segment=segment,
        treatment=treatment,
        control_n=200,
        treatment_n=200,
        control_rate=0.15,
        treatment_rate=0.15 + lift,
        lift=lift,
        ci_lower=lift - 0.05,
        ci_upper=lift + 0.05,
        evidence_status=evidence_status,
        sufficient_sample=(evidence_status != STATUS_INSUFFICIENT),
    )


class SelectActionTest(TestCase):
    """Unit tests for select_action_from_results."""

    def setUp(self):
        # Need a minimal Experiment to satisfy FK
        call_command('generate_transactions', count=50, seed=1)
        self.segment = Transaction.objects.first().segment
        self.exp = Experiment.objects.create(
            target_segment=self.segment,
            arms=['NONE', 'SMS'],
            random_seed=1,
            status='COMPLETED'
        )

    def test_positive_evidence_selects_treatment(self):
        _make_result(self.exp, self.segment, 'SMS', STATUS_POSITIVE, lift=0.15)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        action, winner, reason = select_action_from_results(results)
        self.assertEqual(action, 'SMS')
        self.assertIsNotNone(winner)

    def test_best_lift_wins_when_multiple_positive(self):
        _make_result(self.exp, self.segment, 'SMS', STATUS_POSITIVE, lift=0.08)
        _make_result(self.exp, self.segment, 'WHATSAPP', STATUS_POSITIVE, lift=0.20)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        action, winner, _ = select_action_from_results(results)
        self.assertEqual(action, 'WHATSAPP')

    def test_neutral_evidence_returns_none(self):
        _make_result(self.exp, self.segment, 'SMS', STATUS_NEUTRAL, lift=0.03)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        action, winner, reason = select_action_from_results(results)
        self.assertEqual(action, 'NONE')
        self.assertIsNone(winner)
        self.assertIn('NONE', reason)

    def test_insufficient_sample_returns_none(self):
        _make_result(self.exp, self.segment, 'SMS', STATUS_INSUFFICIENT, lift=0.10)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        action, winner, _ = select_action_from_results(results)
        self.assertEqual(action, 'NONE')

    def test_negative_evidence_returns_none(self):
        _make_result(self.exp, self.segment, 'IMMEDIATE_RETRY', STATUS_NEGATIVE, lift=-0.04)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        action, winner, _ = select_action_from_results(results)
        self.assertEqual(action, 'NONE')

    def test_empty_results_returns_none(self):
        action, winner, _ = select_action_from_results([])
        self.assertEqual(action, 'NONE')
        self.assertIsNone(winner)


class UpdatePolicyTest(TestCase):
    """Integration tests for update_policy."""

    def setUp(self):
        call_command('generate_transactions', count=50, seed=2)
        self.segment = Transaction.objects.first().segment
        self.exp = Experiment.objects.create(
            target_segment=self.segment,
            arms=['NONE', 'DELAYED_RETRY'],
            random_seed=2,
            status='COMPLETED'
        )

    def test_initial_policy_created_on_positive_evidence(self):
        _make_result(self.exp, self.segment, 'DELAYED_RETRY', STATUS_POSITIVE, lift=0.20)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        policy = update_policy(self.exp, results)

        self.assertIsNotNone(policy)
        self.assertEqual(policy.action, 'DELAYED_RETRY')
        self.assertEqual(policy.version, 1)
        self.assertEqual(policy.source_experiment, self.exp)
        self.assertIn('DELAYED_RETRY', policy.reason)

    def test_initial_policy_is_none_on_neutral_evidence(self):
        """No POSITIVE results → no policy created for a brand-new segment."""
        _make_result(self.exp, self.segment, 'DELAYED_RETRY', STATUS_NEUTRAL, lift=0.03)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        policy = update_policy(self.exp, results)
        # Returns None because there was no pre-existing policy to retain
        self.assertIsNone(policy)

    def test_policy_updates_to_better_treatment(self):
        # Seed a v1 policy at NONE
        Policy.objects.create(
            segment=self.segment, action='NONE', version=1,
            source_experiment=self.exp, reason='initial'
        )
        _make_result(self.exp, self.segment, 'DELAYED_RETRY', STATUS_POSITIVE, lift=0.20)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        policy = update_policy(self.exp, results)

        self.assertEqual(policy.action, 'DELAYED_RETRY')
        self.assertEqual(policy.version, 2)
        self.assertIn('NONE', policy.reason)  # previous action referenced

    def test_insufficient_evidence_does_not_overwrite_existing_policy(self):
        """When evidence is insufficient, the existing policy must be preserved."""
        existing = Policy.objects.create(
            segment=self.segment, action='SMS', version=1,
            source_experiment=self.exp, reason='was positive'
        )
        _make_result(self.exp, self.segment, 'DELAYED_RETRY', STATUS_INSUFFICIENT, lift=0.05)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        policy = update_policy(self.exp, results)

        # Must return the existing policy, unchanged
        self.assertEqual(policy.action, 'SMS')
        self.assertEqual(policy.version, 1)
        # No new version was created
        self.assertEqual(Policy.objects.filter(segment=self.segment).count(), 1)

    def test_same_action_does_not_create_new_version(self):
        """If new evidence points to the same action, don't write a duplicate version."""
        Policy.objects.create(
            segment=self.segment, action='DELAYED_RETRY', version=1,
            source_experiment=self.exp, reason='already set'
        )
        _make_result(self.exp, self.segment, 'DELAYED_RETRY', STATUS_POSITIVE, lift=0.22)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        policy = update_policy(self.exp, results)

        self.assertEqual(policy.version, 1)   # no new version
        self.assertEqual(Policy.objects.filter(segment=self.segment).count(), 1)

    def test_versioning_increments(self):
        """Multiple successive policy updates increment the version number."""
        Policy.objects.create(
            segment=self.segment, action='NONE', version=1,
            source_experiment=self.exp, reason='start'
        )
        _make_result(self.exp, self.segment, 'SMS', STATUS_POSITIVE, lift=0.10)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        p2 = update_policy(self.exp, results)
        self.assertEqual(p2.version, 2)

        # Second experiment moves to a different treatment
        exp2 = Experiment.objects.create(
            target_segment=self.segment, arms=['NONE', 'WHATSAPP'],
            random_seed=3, status='COMPLETED'
        )
        _make_result(exp2, self.segment, 'WHATSAPP', STATUS_POSITIVE, lift=0.25)
        results2 = list(ExperimentResult.objects.filter(experiment=exp2))
        p3 = update_policy(exp2, results2)
        self.assertEqual(p3.version, 3)

    def test_policy_reason_is_human_readable(self):
        _make_result(self.exp, self.segment, 'DELAYED_RETRY', STATUS_POSITIVE, lift=0.20)
        results = list(ExperimentResult.objects.filter(experiment=self.exp))
        policy = update_policy(self.exp, results)
        # Reason should be a non-empty, human-readable string
        self.assertIsInstance(policy.reason, str)
        self.assertGreater(len(policy.reason), 20)


class GetPolicyForSegmentTest(TestCase):
    """Tests for the get_policy_for_segment helper."""

    def setUp(self):
        call_command('generate_transactions', count=50, seed=3)
        self.segment = Transaction.objects.first().segment
        self.exp = Experiment.objects.create(
            target_segment=self.segment,
            arms=['NONE', 'SMS'],
            random_seed=3, status='COMPLETED'
        )

    def test_returns_none_when_no_policy(self):
        action = get_policy_for_segment(self.segment)
        self.assertEqual(action, 'NONE')

    def test_returns_current_action(self):
        Policy.objects.create(
            segment=self.segment, action='SMS', version=1,
            source_experiment=self.exp, reason='test'
        )
        action = get_policy_for_segment(self.segment)
        self.assertEqual(action, 'SMS')


class EndToEndPolicyTest(TestCase):
    """
    End-to-end: run a real experiment on the 10k dataset, analyze it,
    and verify the policy engine makes the correct update.
    """

    def test_real_experiment_updates_policy(self):
        call_command('generate_transactions', count=3000, seed=42)
        segment = 'UPI | Insufficient Funds | MID_VALUE'

        # Confirm no existing policy
        self.assertIsNone(get_current_policy(segment))

        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=segment,
            arms=['NONE', 'DELAYED_RETRY'],
            random_seed=888
        )
        exp = ExperimentEngine.execute_experiment(exp)
        results = analyze_experiment(exp)
        policy = update_policy(exp, results)

        # DELAYED_RETRY has +0.25 hidden effect → should be detected as POSITIVE
        self.assertIsNotNone(policy)
        self.assertEqual(policy.action, 'DELAYED_RETRY')
        self.assertEqual(policy.version, 1)
        self.assertIsNotNone(policy.source_experiment)
        self.assertIn('DELAYED_RETRY', policy.reason)


class DemoScenarioTest(TestCase):
    """
    Tests specific to the demo script's requirements:
    Ensuring clean state, accurate evidence logging, and no stale state.
    """

    def test_clean_demo_state_and_accurate_evidence(self):
        segment = 'UPI | Insufficient Funds | MID_VALUE'
        
        # 1. Setup mock pre-existing state to simulate a previous demo run
        call_command('generate_transactions', count=50, seed=10)
        old_exp = Experiment.objects.create(target_segment=segment, arms=['NONE'], random_seed=10)
        Policy.objects.create(
            segment=segment, action='DELAYED_RETRY', version=1,
            source_experiment=old_exp, reason="stale evidence lift=+0.999"
        )
        
        # 2. Perform the demo's reset
        Policy.objects.filter(segment=segment).delete()
        Experiment.objects.filter(target_segment=segment).delete()
        
        # Verify clean state
        self.assertIsNone(get_current_policy(segment))
        self.assertEqual(get_policy_for_segment(segment), 'NONE')

        # 3. Run the new demo experiment
        call_command('generate_transactions', count=3000, seed=42, clear=True)
        exp = ExperimentEngine.create_and_assign_experiment(
            target_segment=segment,
            arms=['NONE', 'DELAYED_RETRY'],
            random_seed=888
        )
        exp = ExperimentEngine.execute_experiment(exp)
        results = analyze_experiment(exp)
        
        # 4. Update policy
        new_policy = update_policy(exp, results)
        
        # 5. Verify the new policy reflects ONLY the current experiment's exact evidence
        self.assertIsNotNone(new_policy)
        self.assertEqual(new_policy.version, 1) # Must be v1 because we cleared!
        self.assertEqual(new_policy.source_experiment, exp)
        
        # Find the actual result for DELAYED_RETRY to verify the reason string
        dr_result = next(r for r in results if r.treatment == 'DELAYED_RETRY')
        self.assertNotIn("+0.999", new_policy.reason) # Stale evidence must not appear
        self.assertIn(f"lift={dr_result.lift:+.3f}", new_policy.reason)
        self.assertIn(f"[{dr_result.ci_lower:+.3f}, {dr_result.ci_upper:+.3f}]", new_policy.reason)
        self.assertIn(f"n_treatment={dr_result.treatment_n}", new_policy.reason)
        self.assertIn(f"n_control={dr_result.control_n}", new_policy.reason)
        self.assertIn(str(exp.id), new_policy.reason)
