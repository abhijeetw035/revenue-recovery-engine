"""
Policy Engine

Converts Day 4 experiment evidence into an explicit, versioned recovery policy.

Rules:
- Only POSITIVE evidence (CI entirely above 0) justifies choosing a treatment.
- Among POSITIVE results, choose the one with the highest observed lift.
- If no treatment has POSITIVE evidence, the policy defaults to / retains NONE.
- Insufficient evidence (INSUFFICIENT_SAMPLE, NEUTRAL, NEGATIVE) does NOT
  overwrite an existing policy.
- Every policy version is stored with a reason and a reference to the
  source experiment.
- The engine NEVER reads simulator ground truth.
"""
from recovery.models import Policy, ExperimentResult
from recovery.lift_analyzer import STATUS_POSITIVE


def get_current_policy(segment):
    """
    Returns the latest Policy for a segment, or None if none exists yet.
    """
    return Policy.objects.filter(segment=segment).first()   # ordering=[-version]


def select_action_from_results(results):
    """
    Given a list of ExperimentResult objects (from analyze_experiment),
    determine the best action purely from observed evidence.

    Returns: (action: str, winning_result: ExperimentResult | None, reason: str)

    Selection rules:
    1. Candidates are treatments with evidence_status == POSITIVE.
    2. Among candidates, pick the one with the highest observed lift.
    3. If no candidates: action is NONE.
    """
    candidates = [r for r in results if r.evidence_status == STATUS_POSITIVE]

    if not candidates:
        reason = (
            "No treatment arm produced statistically confident positive lift "
            "(evidence_status != POSITIVE for all treatments). Defaulting to NONE."
        )
        return 'NONE', None, reason

    # Pick the candidate with the largest observed lift
    best = max(candidates, key=lambda r: r.lift)
    reason = (
        f"Treatment '{best.treatment}' had the strongest POSITIVE evidence "
        f"(lift={best.lift:+.3f}, 95% CI [{best.ci_lower:+.3f}, {best.ci_upper:+.3f}], "
        f"n_treatment={best.treatment_n}, n_control={best.control_n})."
    )
    return best.treatment, best, reason


def update_policy(experiment, results):
    """
    Evaluates Day 4 ExperimentResult objects and, if warranted, creates a new
    Policy version for the experiment's target segment.

    Policy update rules:
    - A new version is written when the chosen action DIFFERS from the current policy.
    - If the chosen action matches the current policy, no new version is created
      (policy is already optimal; write is skipped to avoid noise).
    - If evidence is insufficient for all treatments (no POSITIVE results),
      the current policy (which may already be NONE) is retained.

    Returns the new Policy if one was created, otherwise the existing Policy
    (or None if no policy has ever been set and NONE is the implicit default).
    """
    segment = experiment.target_segment
    action, winning_result, reason = select_action_from_results(results)
    current = get_current_policy(segment)

    # If evidence is insufficient for any change AND there is already a policy,
    # leave it untouched.
    if winning_result is None and current is not None:
        # No POSITIVE evidence — retain existing policy
        return current

    # If there is no existing policy AND evidence is insufficient,
    # NONE is the implicit safe default — do not write a redundant record.
    if winning_result is None and current is None:
        return None

    current_action = current.action if current else None

    if action == current_action:
        # Chosen action matches current policy — no update needed
        return current

    # Compute the next version number
    next_version = (current.version + 1) if current else 1

    # Build the human-readable reason including previous policy info
    if current:
        full_reason = (
            f"Policy updated from '{current_action}' (v{current.version}) to '{action}' (v{next_version}). "
            f"Experiment {experiment.id} on segment '{segment}'. {reason}"
        )
    else:
        full_reason = (
            f"Initial policy set to '{action}' (v{next_version}) for segment '{segment}'. "
            f"Experiment {experiment.id}. {reason}"
        )

    new_policy = Policy.objects.create(
        segment=segment,
        action=action,
        version=next_version,
        source_experiment=experiment,
        reason=full_reason,
    )
    return new_policy


def get_policy_for_segment(segment):
    """
    Returns the recommended action for a segment from the current policy.
    Falls back to 'NONE' if no policy has been set.
    """
    policy = get_current_policy(segment)
    return policy.action if policy else 'NONE'
