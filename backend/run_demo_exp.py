import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management import call_command
from recovery.models import Transaction, Outcome, Assignment
from recovery.experiment_engine import ExperimentEngine

target_segment = 'UPI | Insufficient Funds | MID_VALUE'
print(f"Targeting segment: {target_segment}")

exp = ExperimentEngine.create_and_assign_experiment(
    target_segment=target_segment,
    arms=['NONE', 'DELAYED_RETRY'],
    random_seed=888
)

print(f"Executing experiment {exp.id}...")
exp = ExperimentEngine.execute_experiment(exp)

print("Results:")
for arm in ['NONE', 'DELAYED_RETRY']:
    assigned_tx_ids = Assignment.objects.filter(experiment=exp, arm=arm).values_list('transaction_id', flat=True)
    outcomes = Outcome.objects.filter(experiment=exp, transaction_id__in=assigned_tx_ids)
    
    total = outcomes.count()
    recovered = outcomes.filter(recovered=True).count()
    rate = recovered / total if total else 0
    print(f"Arm {arm}: {recovered}/{total} ({rate:.1%})")

