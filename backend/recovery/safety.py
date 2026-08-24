from recovery.models import Transaction, CustomerState

MAX_ATTEMPTS = 3
MAX_CONTACTS = 5
HIGH_VALUE_THRESHOLD = 10000.0

def check_safety(transaction: Transaction, action: str, expected_net_value: float) -> tuple[bool, str]:
    """
    Checks if an intervention is safe and economically sound to execute.
    Returns (is_safe, reason).
    """
    # 1. NONE is always safe and skips all other checks
    if action == 'NONE':
        return True, "Safe: NONE action"
        
    # 2. Economic check: stop if not worthwhile
    if expected_net_value <= 0:
        return False, "Unsafe: Zero or negative expected net value"
        
    # 3. Maximum attempts per transaction
    if transaction.attempt_count >= MAX_ATTEMPTS:
        return False, f"Unsafe: Reached maximum attempts per transaction ({MAX_ATTEMPTS})"
        
    # 4. Customer-level constraints (opt-out and contact limits)
    try:
        customer_state = CustomerState.objects.get(customer_id=transaction.customer_id)
    except CustomerState.DoesNotExist:
        # If no record exists, customer has no contacts and hasn't opted out
        customer_state = None
        
    if customer_state:
        if customer_state.opted_out:
            return False, "Unsafe: Customer opted out"
            
        if customer_state.contact_count >= MAX_CONTACTS:
            return False, f"Unsafe: Reached maximum customer contacts ({MAX_CONTACTS})"
            
    # 5. Risk / High-value cases require human review
    is_high_value = float(transaction.amount) > HIGH_VALUE_THRESHOLD
    is_high_risk = transaction.risk_level == 'HIGH'
    if is_high_value or is_high_risk:
        # Note: the allocator will mark this as HUMAN_REVIEW instead of executing
        return False, "Unsafe: High risk or high value requires human review"
        
    return True, "Safe"
