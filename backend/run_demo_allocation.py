"""
Day 6 Live Demo - Economics and Safety Allocation
"""
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management import call_command
from recovery.models import Transaction, Policy, CustomerState, Execution
from recovery.allocator import allocate_interventions
from recovery.safety import MAX_ATTEMPTS, MAX_CONTACTS, HIGH_VALUE_THRESHOLD

print("=== Setting up test portfolio ===")
# Clear old policies and experiments to avoid stale data
from recovery.models import Experiment
Policy.objects.all().delete()
Experiment.objects.all().delete()

# Generate a 3000 transaction portfolio to test allocation (needs enough data to train policy)
call_command('generate_transactions', count=3000, seed=99, clear=True)

# 1. Provide an active policy for one of the segments
target_segment = 'UPI | Insufficient Funds | MID_VALUE'

# Run an experiment to give us actual ExperimentResults and lift
from recovery.experiment_engine import ExperimentEngine
from recovery.lift_analyzer import analyze_experiment
from recovery.policy_engine import update_policy

print(f"\n=== Training policy for segment '{target_segment}' ===")
exp = ExperimentEngine.create_and_assign_experiment(
    target_segment=target_segment,
    arms=['NONE', 'DELAYED_RETRY'],
    random_seed=99
)
exp = ExperimentEngine.execute_experiment(exp)
results = analyze_experiment(exp)
update_policy(exp, results)

active_policy = Policy.objects.filter(segment=target_segment).first()
print(f"Policy established: {active_policy.action}")

# 2. Inject some artificial safety constraints into the pending transactions
print("\n=== Injecting safety constraints ===")
txs = list(Transaction.objects.filter(segment=target_segment))
if len(txs) >= 4:
    # Tx 0: Normal valid transaction (should allocate)
    
    # Tx 1: Exceeds MAX_ATTEMPTS
    txs[1].attempt_count = MAX_ATTEMPTS
    txs[1].save()
    print(f"Tx {txs[1].id} set to max attempts ({MAX_ATTEMPTS})")
    
    # Tx 2: Opted out customer
    CustomerState.objects.create(customer_id=txs[2].customer_id, opted_out=True)
    print(f"Tx {txs[2].id} customer opted out")
    
    # Tx 3: High value
    txs[3].amount = HIGH_VALUE_THRESHOLD + 5000.0
    txs[3].save()
    print(f"Tx {txs[3].id} set to high value ({txs[3].amount})")
    
# 3. Allocate with a limited budget
print("\n=== Running Allocator ===")
budget = 50.0  # arbitrary small budget
print(f"Budget Limit: {budget}")
executions = allocate_interventions(budget_limit=budget)

print("\n=== Allocation Results ===")
print(f"Total interventions allocated: {len(executions)}")
for ex in executions:
    print(f" -> Allocated {ex.action} to Tx {ex.transaction_id} (Expected net value: {ex.expected_net_value:.2f}, Cost: {ex.estimated_cost:.2f})")

print("\n=== Safety & Stopping Verification ===")
for i in range(min(4, len(txs))):
    txs[i].refresh_from_db()
    print(f"Tx {i} (Status: {txs[i].status})")
