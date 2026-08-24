"""
Day 7 Live Demo - Strategy Evaluation
"""
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management import call_command
from recovery.models import Transaction, Policy, Experiment, CustomerState, Execution
from recovery.evaluation import compare_strategies
from recovery.experiment_engine import ExperimentEngine
from recovery.lift_analyzer import analyze_experiment
from recovery.policy_engine import update_policy

print("=== Setting up 10k test portfolio ===")
Policy.objects.all().delete()
Experiment.objects.all().delete()
Execution.objects.all().delete()
CustomerState.objects.all().delete()
Transaction.objects.all().delete()

call_command('generate_transactions', count=10000, seed=42, clear=True)

# Train the Learned strategy by running experiments on a few key segments
print("\n=== Training Learned Strategy ===")
segments_to_train = [
    'UPI | Insufficient Funds | MID_VALUE',
    'Credit Card | Technical Decline | HIGH_VALUE',
    'Netbanking | Risk Block | LOW_VALUE'
]

for seg in segments_to_train:
    exp = ExperimentEngine.create_and_assign_experiment(
        target_segment=seg,
        arms=['NONE', 'IMMEDIATE_RETRY', 'DELAYED_RETRY', 'SMS', 'WHATSAPP'],
        random_seed=42
    )
    exp = ExperimentEngine.execute_experiment(exp)
    results = analyze_experiment(exp)
    update_policy(exp, results)
    
    active_policy = Policy.objects.filter(segment=seg).first()
    if active_policy:
        print(f"Policy for '{seg}': {active_policy.action}")
    else:
        print(f"Policy for '{seg}': None (Insufficient evidence)")

# Inject a few safety constraints to test the Learned allocator
txs = list(Transaction.objects.all()[:100])
for tx in txs[:10]:
    tx.attempt_count = 3  # MAX_ATTEMPTS
    tx.save()
for tx in txs[10:20]:
    CustomerState.objects.create(customer_id=tx.customer_id, opted_out=True)

budget_limit = 50000.0  # Large budget to see full impact

def run_evaluation_pass(pass_number):
    print(f"\n=== Evaluation Pass {pass_number} ===")
    
    # Ensure database state is pristine for the evaluation
    # Since run_learned_strategy rolls back its mutations, this state should be identical across passes.
    initial_tx_count = Transaction.objects.filter(status='PENDING').count()
    initial_exec_count = Execution.objects.count()
    
    print(f"Initial State -> PENDING Txs: {initial_tx_count}, Executions: {initial_exec_count}")
    
    report = compare_strategies(budget_limit)
    
    print("\nStrategy         | Rec. Rate | Gross Rec. | Cost     | Net Rec.   | Incr. (vs Naive)")
    print("-" * 88)
    
    for strategy in ['Naive', 'Static', 'Learned']:
        metrics = report[strategy]
        rate = metrics['recovery_rate'] * 100
        gross = metrics['gross_recovery']
        cost = metrics['intervention_cost']
        net = metrics['net_recovery']
        incr = metrics.get('incremental_recovery_vs_naive', 0.0)
        
        print(f"{strategy:<16} | {rate:>8.2f}% | {gross:>10.2f} | {cost:>8.2f} | {net:>10.2f} | {incr:>12.2f}")

# Run twice to verify deterministic results
run_evaluation_pass(1)
run_evaluation_pass(2)
