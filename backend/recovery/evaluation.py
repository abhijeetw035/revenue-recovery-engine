import hashlib
from django.db import transaction
from recovery.models import Transaction
from recovery.simulator import simulate_outcome
from recovery.allocator import allocate_interventions

def get_deterministic_seed(transaction_id: str, action: str) -> int:
    """
    Generates a deterministic integer seed based on the transaction ID and action.
    This guarantees reproducible stochastic outcomes for fair strategy comparisons.
    """
    # Use sha256 to create a stable hash
    hash_input = f"{transaction_id}:{action}".encode('utf-8')
    digest = hashlib.sha256(hash_input).hexdigest()
    # Convert first 8 hex characters into an integer seed
    return int(digest[:8], 16)

def evaluate_decisions(decisions: list[tuple[Transaction, str]]) -> dict:
    """
    Evaluates a list of (Transaction, action) decisions using the common simulator.
    Returns calculated business metrics.
    """
    total_transactions = len(decisions)
    recovered_count = 0
    gross_recovery = 0.0
    total_cost = 0.0

    for tx, action in decisions:
        seed = get_deterministic_seed(str(tx.id), action)
        
        # We assume the simulator takes (amount, method, reason, band, action, seed)
        # Note: the simulator takes 'band', which might just be risk_level or we need to map amount to band.
        # Wait! The current simulator in Day 1 takes:
        # simulate_outcome(transaction_amount, payment_method, failure_reason, band, action, seed)
        # Let's map amount to band identical to generate_transactions
        band = 'LOW_VALUE'
        if tx.amount > 5000:
            band = 'HIGH_VALUE'
        elif tx.amount > 1000:
            band = 'MID_VALUE'
            
        result = simulate_outcome(
            transaction_amount=float(tx.amount),
            payment_method=tx.payment_method,
            failure_reason=tx.failure_reason,
            band=band,
            action=action,
            seed=seed
        )
        
        if result['recovered']:
            recovered_count += 1
            gross_recovery += result['recovered_amount']
            
        total_cost += result['cost']
        
    recovery_rate = recovered_count / total_transactions if total_transactions > 0 else 0.0
    net_recovery = gross_recovery - total_cost
    
    return {
        'total_transactions': total_transactions,
        'recovered_transactions': recovered_count,
        'recovery_rate': recovery_rate,
        'gross_recovery': gross_recovery,
        'intervention_cost': total_cost,
        'net_recovery': net_recovery
    }

def run_naive_baseline(transactions: list[Transaction]) -> list[tuple[Transaction, str]]:
    """
    Naive baseline: IMMEDIATE_RETRY for every transaction.
    """
    return [(tx, 'IMMEDIATE_RETRY') for tx in transactions]

def run_static_baseline(transactions: list[Transaction]) -> list[tuple[Transaction, str]]:
    """
    Static baseline: A fixed, non-learning heuristic based on observable transaction characteristics.
    
    Heuristic Rationale:
    A common industry practice is to use high-touch, slightly more expensive engagement (WHATSAPP) 
    for high-value transactions (> 5000) to ensure the customer sees it, and a cheap automated 
    approach (IMMEDIATE_RETRY) for everything else. This rule is defined completely independently 
    of the hidden simulator's causal effects.
    """
    decisions = []
    for tx in transactions:
        if float(tx.amount) > 5000:
            action = 'WHATSAPP'
        else:
            action = 'IMMEDIATE_RETRY'
        decisions.append((tx, action))
    return decisions

def run_learned_strategy(budget_limit: float) -> list[tuple[Transaction, str]]:
    """
    Learned strategy: Uses the Day 6 allocator. 
    State mutations are rolled back to isolate the evaluation.
    """
    decisions = []
    
    # Fetch pending transactions before allocation modifies them
    initial_pending = list(Transaction.objects.filter(status='PENDING'))
    
    # Run inside an atomic block to isolate state changes
    with transaction.atomic():
        executions = allocate_interventions(budget_limit)
        
        # Map executions to decisions
        allocated_tx_ids = set()
        for ex in executions:
            decisions.append((ex.transaction, ex.action))
            allocated_tx_ids.add(ex.transaction.id)
            
        # Any initially pending transactions that were NOT allocated default to NONE
        for tx in initial_pending:
            if tx.id not in allocated_tx_ids:
                decisions.append((tx, 'NONE'))
                
        # Rollback all database mutations (Execution records, attempt_count, status changes)
        transaction.set_rollback(True)
        
    return decisions

def compare_strategies(budget_limit: float) -> dict:
    """
    Runs all three strategies on the same portfolio and computes impact metrics.
    """
    # Fetch all current pending transactions to use as the base portfolio for baselines
    transactions = list(Transaction.objects.filter(status='PENDING'))
    
    # 1. Generate decisions
    naive_decisions = run_naive_baseline(transactions)
    static_decisions = run_static_baseline(transactions)
    learned_decisions = run_learned_strategy(budget_limit)
    
    # 2. Evaluate decisions using the common deterministic simulator
    naive_metrics = evaluate_decisions(naive_decisions)
    static_metrics = evaluate_decisions(static_decisions)
    learned_metrics = evaluate_decisions(learned_decisions)
    
    # 3. Calculate incremental metrics
    # We choose Naive as the base baseline for incremental metrics, or report both
    naive_metrics['incremental_recovery_vs_naive'] = 0.0
    static_metrics['incremental_recovery_vs_naive'] = static_metrics['net_recovery'] - naive_metrics['net_recovery']
    learned_metrics['incremental_recovery_vs_naive'] = learned_metrics['net_recovery'] - naive_metrics['net_recovery']
    
    learned_metrics['incremental_recovery_vs_static'] = learned_metrics['net_recovery'] - static_metrics['net_recovery']
    
    return {
        'Naive': naive_metrics,
        'Static': static_metrics,
        'Learned': learned_metrics
    }
