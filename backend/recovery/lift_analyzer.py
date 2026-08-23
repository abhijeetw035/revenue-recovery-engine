"""
Lift Analysis Module

Calculates incremental lift, confidence intervals, and evidence status
for each treatment arm vs the control arm (NONE) in a completed experiment.

Uses only observed experiment outcomes — never accesses simulator ground truth.
"""
import math
from recovery.models import Assignment, Outcome, ExperimentResult

# Minimum sample size per arm to consider results trustworthy
MIN_SAMPLE_SIZE = 100

# Evidence status labels
STATUS_INSUFFICIENT = 'INSUFFICIENT_SAMPLE'
STATUS_POSITIVE = 'POSITIVE'
STATUS_NEGATIVE = 'NEGATIVE'
STATUS_NEUTRAL = 'NEUTRAL'


def _proportion_ci(successes, n, z=1.96):
    """
    Wilson score confidence interval for a proportion.
    More reliable than the normal approximation for small samples and
    extreme proportions (near 0% or 100%).
    Returns (lower, upper).
    """
    if n == 0:
        return (0.0, 0.0)

    p_hat = successes / n
    denom = 1 + z ** 2 / n
    centre = (p_hat + z ** 2 / (2 * n)) / denom
    spread = z * math.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2)) / denom

    return (max(0.0, centre - spread), min(1.0, centre + spread))


def _lift_ci(p_t, n_t, p_c, n_c, z=1.96):
    """
    Approximate 95% CI for the difference between two independent proportions
    (treatment - control).
    Uses the standard error of the difference.
    """
    if n_t == 0 or n_c == 0:
        return (0.0, 0.0)

    se_diff = math.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    lift = p_t - p_c
    return (lift - z * se_diff, lift + z * se_diff)


def _classify_evidence(lift, ci_lower, ci_upper, sufficient_sample):
    """
    Classify the evidence status based on the observed lift and its CI.
    - If sample is insufficient: INSUFFICIENT_SAMPLE
    - If entire CI is above 0: POSITIVE
    - If entire CI is below 0: NEGATIVE
    - Otherwise: NEUTRAL (CI straddles 0, cannot confidently determine direction)
    """
    if not sufficient_sample:
        return STATUS_INSUFFICIENT
    if ci_lower > 0:
        return STATUS_POSITIVE
    if ci_upper < 0:
        return STATUS_NEGATIVE
    return STATUS_NEUTRAL


def analyze_experiment(experiment):
    """
    Analyse a completed experiment.
    Calculates recovery rates, lift, CI, and evidence status for each
    treatment arm vs control (NONE). Persists ExperimentResult records.

    Returns: list of ExperimentResult instances (not yet committed if they exist).
    """
    if experiment.status != 'COMPLETED':
        raise ValueError(f"Experiment {experiment.id} is not yet COMPLETED.")

    arms = experiment.arms
    control_arm = 'NONE'

    if control_arm not in arms:
        raise ValueError("Experiment must include 'NONE' as the control arm.")

    treatment_arms = [a for a in arms if a != control_arm]
    segment = experiment.target_segment

    # --- Fetch control group outcomes ---
    control_tx_ids = Assignment.objects.filter(
        experiment=experiment, arm=control_arm
    ).values_list('transaction_id', flat=True)
    control_outcomes = Outcome.objects.filter(
        experiment=experiment, transaction_id__in=control_tx_ids
    )
    control_n = control_outcomes.count()
    control_recovered = control_outcomes.filter(recovered=True).count()
    control_rate = control_recovered / control_n if control_n > 0 else 0.0

    results = []

    for treatment in treatment_arms:
        # --- Fetch treatment group outcomes ---
        treatment_tx_ids = Assignment.objects.filter(
            experiment=experiment, arm=treatment
        ).values_list('transaction_id', flat=True)
        treatment_outcomes = Outcome.objects.filter(
            experiment=experiment, transaction_id__in=treatment_tx_ids
        )
        treatment_n = treatment_outcomes.count()
        treatment_recovered = treatment_outcomes.filter(recovered=True).count()
        treatment_rate = treatment_recovered / treatment_n if treatment_n > 0 else 0.0

        # --- Statistical calculations ---
        lift = treatment_rate - control_rate
        ci_lower, ci_upper = _lift_ci(treatment_rate, treatment_n, control_rate, control_n)
        sufficient_sample = (treatment_n >= MIN_SAMPLE_SIZE and control_n >= MIN_SAMPLE_SIZE)
        evidence_status = _classify_evidence(lift, ci_lower, ci_upper, sufficient_sample)

        # --- Persist result ---
        result, _ = ExperimentResult.objects.update_or_create(
            experiment=experiment,
            treatment=treatment,
            segment=segment,
            defaults={
                'control_n': control_n,
                'treatment_n': treatment_n,
                'control_rate': control_rate,
                'treatment_rate': treatment_rate,
                'lift': lift,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'evidence_status': evidence_status,
                'sufficient_sample': sufficient_sample,
            }
        )
        results.append(result)

    return results


def get_result_report(experiment):
    """
    Returns a structured dict report for all results of a completed experiment.
    Suitable for API serialization or display.
    """
    results = ExperimentResult.objects.filter(experiment=experiment)

    # Include the control arm baseline summary too
    control_tx_ids = Assignment.objects.filter(
        experiment=experiment, arm='NONE'
    ).values_list('transaction_id', flat=True)
    control_outcomes = Outcome.objects.filter(
        experiment=experiment, transaction_id__in=control_tx_ids
    )
    control_n = control_outcomes.count()
    control_rate = control_outcomes.filter(recovered=True).count() / control_n if control_n > 0 else 0.0

    return {
        'experiment_id': str(experiment.id),
        'segment': experiment.target_segment,
        'status': experiment.status,
        'control': {
            'arm': 'NONE',
            'n': control_n,
            'recovery_rate': round(control_rate, 4),
        },
        'treatments': [
            {
                'arm': r.treatment,
                'control_n': r.control_n,
                'treatment_n': r.treatment_n,
                'control_rate': round(r.control_rate, 4),
                'treatment_rate': round(r.treatment_rate, 4),
                'lift': round(r.lift, 4),
                'ci_lower': round(r.ci_lower, 4),
                'ci_upper': round(r.ci_upper, 4),
                'evidence_status': r.evidence_status,
                'sufficient_sample': r.sufficient_sample,
            }
            for r in results
        ]
    }
