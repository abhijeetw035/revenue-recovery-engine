"""
Day 5 live demo — show a before→after policy update using real experiment data.
"""
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management import call_command
from recovery.models import Policy
from recovery.experiment_engine import ExperimentEngine
from recovery.lift_analyzer import analyze_experiment, get_result_report
from recovery.policy_engine import update_policy, get_policy_for_segment

# ── Setup: clean 10k dataset ────────────────────────────────────────────────
call_command('generate_transactions', count=10000, seed=42, clear=True)
segment = 'UPI | Insufficient Funds | MID_VALUE'

# Also clear policies and experiments for this demo segment to ensure a clean state
from recovery.models import Experiment
Policy.objects.filter(segment=segment).delete()
Experiment.objects.filter(target_segment=segment).delete()

# ── BEFORE: no policy exists ─────────────────────────────────────────────────
before_action = get_policy_for_segment(segment)
print(f"\n{'='*60}")
print(f"Segment: {segment}")
if Policy.objects.filter(segment=segment).exists():
    print(f"Policy BEFORE experiment: action='{before_action}'")
else:
    print(f"Policy BEFORE experiment: NONE / no existing policy")

# ── Run experiment ────────────────────────────────────────────────────────────
exp = ExperimentEngine.create_and_assign_experiment(
    target_segment=segment,
    arms=['NONE', 'IMMEDIATE_RETRY', 'DELAYED_RETRY', 'SMS', 'WHATSAPP'],
    random_seed=888
)
exp = ExperimentEngine.execute_experiment(exp)
results = analyze_experiment(exp)

# Print lift report
report = get_result_report(exp)
print(f"\nExperiment result (control n={report['control']['n']}, rate={report['control']['recovery_rate']:.1%}):")
print(f"{'Treatment':<18} {'n':>5}  {'Rate':>7}  {'Lift':>8}  {'95% CI':>20}  Status")
print("-" * 75)
for t in report['treatments']:
    ci_str = f"[{t['ci_lower']:+.3f}, {t['ci_upper']:+.3f}]"
    flag = " ✅" if t['evidence_status'] == 'POSITIVE' else ""
    print(f"{t['arm']:<18} {t['treatment_n']:>5}  {t['treatment_rate']:>7.1%}  "
          f"{t['lift']:>+8.3f}  {ci_str:>20}  {t['evidence_status']}{flag}")

# ── Update policy ─────────────────────────────────────────────────────────────
new_policy = update_policy(exp, results)

# ── AFTER ─────────────────────────────────────────────────────────────────────
after_action = get_policy_for_segment(segment)
print(f"\nPolicy AFTER experiment:  action='{after_action}' (v{new_policy.version})")
print(f"\nReason: {new_policy.reason}")
print(f"\nAll policy versions for this segment:")
for p in Policy.objects.filter(segment=segment).order_by('version'):
    print(f"  v{p.version}: {p.action}")
