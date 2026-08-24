from recovery.models import Transaction, Policy, CustomerState, Execution, ExperimentResult
from recovery.policy_engine import get_policy_for_segment
from recovery.economics import calculate_expected_net_value
from recovery.safety import check_safety

def allocate_interventions(budget_limit: float) -> list[Execution]:
    """
    Allocates budget to pending transactions based on policy and expected net value,
    subject to safety limits and available capacity.
    """
    pending_txs = Transaction.objects.filter(status='PENDING')
    
    candidates = []
    
    for tx in pending_txs:
        # Determine policy action
        action = get_policy_for_segment(tx.segment)
        if action == 'NONE':
            # Fast-track NONE: zero cost, always safe
            candidates.append({
                'tx': tx,
                'action': 'NONE',
                'net_value': 0.0,
                'cost': 0.0,
                'reason': 'Safe: NONE action'
            })
            continue
            
        # Get the policy object to find its source experiment
        policy = Policy.objects.filter(segment=tx.segment).first()
        exp_result = None
        if policy and policy.source_experiment:
            exp_result = ExperimentResult.objects.filter(
                experiment=policy.source_experiment,
                treatment=action,
                segment=tx.segment
            ).first()
            
        expected_net_value = calculate_expected_net_value(tx, exp_result)
        cost = exp_result.average_cost if exp_result else 0.0
        
        is_safe, reason = check_safety(tx, action, expected_net_value)
        
        if not is_safe:
            # Handle stopping logic & review
            if "human review" in reason.lower():
                tx.status = 'HUMAN_REVIEW'
            else:
                tx.status = 'STOPPED'
            tx.save()
            continue
            
        candidates.append({
            'tx': tx,
            'action': action,
            'net_value': expected_net_value,
            'cost': cost,
            'reason': reason
        })
        
    # Sort candidates by expected net value descending
    candidates.sort(key=lambda c: c['net_value'], reverse=True)
    
    allocated_executions = []
    current_spend = 0.0
    
    for c in candidates:
        tx = c['tx']
        action = c['action']
        cost = c['cost']
        
        if action == 'NONE':
            # Allocate NONE (no budget consumed)
            Execution.objects.create(
                transaction=tx,
                action='NONE',
                expected_net_value=0.0,
                estimated_cost=0.0
            )
            tx.status = 'STOPPED'  # Terminate automated intervention logic for this tx
            tx.save()
            continue
            
        if current_spend + cost <= budget_limit:
            # Allocate
            current_spend += cost
            execution = Execution.objects.create(
                transaction=tx,
                action=action,
                expected_net_value=c['net_value'],
                estimated_cost=cost
            )
            allocated_executions.append(execution)
            
            # Update tx attempt count
            tx.attempt_count += 1
            tx.save()
            
            # Update customer state
            customer_state, _ = CustomerState.objects.get_or_create(customer_id=tx.customer_id)
            customer_state.contact_count += 1
            customer_state.save()
        else:
            # Budget exceeded, we cannot afford this intervention
            # The transaction remains PENDING so it can be retried if budget increases
            pass
            
    return allocated_executions
