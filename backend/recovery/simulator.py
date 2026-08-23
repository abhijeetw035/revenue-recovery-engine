import numpy as np

ACTIONS = ['NONE', 'IMMEDIATE_RETRY', 'DELAYED_RETRY', 'SMS', 'WHATSAPP']

# Base intervention costs (in currency units, e.g., INR)
INTERVENTION_COSTS = {
    'NONE': 0.0,
    'IMMEDIATE_RETRY': 0.05,
    'DELAYED_RETRY': 0.05,
    'SMS': 1.50,
    'WHATSAPP': 3.50
}

def get_natural_recovery_prob(payment_method, failure_reason, band):
    """Hidden ground truth: Base probability of recovery if we do NONE."""
    base_probs = {
        'Insufficient Funds': 0.10,
        'Technical Decline': 0.35,
        'Risk Block': 0.05,
        'Invalid Details': 0.00
    }
    prob = base_probs.get(failure_reason, 0.10)
    
    # Slight adjustments based on payment method
    if payment_method == 'UPI':
        prob += 0.05
        
    # High value transactions have slightly more natural motivation to resolve
    if band == 'HIGH_VALUE':
        prob += 0.05
        
    return max(0.0, min(1.0, prob))

def get_treatment_effect(failure_reason, action):
    """Hidden ground truth: Change in recovery probability due to an action."""
    if action == 'NONE':
        return 0.0
        
    # Default zero effect
    effect = 0.0
    
    if failure_reason == 'Technical Decline':
        if action == 'IMMEDIATE_RETRY':
            effect = 0.40  # Strong positive
        elif action == 'DELAYED_RETRY':
            effect = 0.10  # Weak positive
            
    elif failure_reason == 'Insufficient Funds':
        if action == 'DELAYED_RETRY':
            effect = 0.25  # Strong positive
        elif action == 'WHATSAPP':
            effect = 0.15  # Moderate positive
        elif action == 'SMS':
            effect = 0.08  # Weak positive
        elif action == 'IMMEDIATE_RETRY':
            effect = 0.00  # Zero effect

    elif failure_reason == 'Risk Block':
        # Counterintuitive: Pushing retries or messages on a risk block makes it worse
        if action in ['IMMEDIATE_RETRY', 'DELAYED_RETRY']:
            effect = -0.04 # Negative effect
        elif action in ['SMS', 'WHATSAPP']:
            effect = -0.02
            
    elif failure_reason == 'Invalid Details':
        # No intervention fixes invalid details without a totally different flow
        effect = 0.0
        
    return effect

def get_friction_cost(failure_reason, action):
    """Hidden ground truth: Abstract business friction/risk costs."""
    if action == 'IMMEDIATE_RETRY' and failure_reason == 'Risk Block':
        # High friction for spamming retries on risk blocked transactions
        return 50.0
    if action == 'WHATSAPP':
        # Small annoyance cost for messaging
        return 0.5
    return 0.0

def simulate_outcome(transaction_amount, payment_method, failure_reason, band, action, seed=None):
    """
    Simulates the outcome of applying an action to a transaction.
    This encapsulates the hidden ground truth.
    Returns: (recovered: bool, recovered_amount: float, cost: float)
    """
    if seed is not None:
        np.random.seed(seed)
        
    natural_prob = get_natural_recovery_prob(payment_method, failure_reason, band)
    treatment_effect = get_treatment_effect(failure_reason, action)
    
    # Calculate final probability
    final_prob = max(0.0, min(1.0, natural_prob + treatment_effect))
    
    # Simulate binary outcome
    recovered = np.random.random() < final_prob
    
    # Calculate costs
    base_cost = INTERVENTION_COSTS.get(action, 0.0)
    friction = get_friction_cost(failure_reason, action)
    total_cost = base_cost + friction
    
    recovered_amount = float(transaction_amount) if recovered else 0.0
    
    return {
        'recovered': bool(recovered),
        'recovered_amount': recovered_amount,
        'cost': total_cost,
        'true_prob': final_prob # Keeping this inside the simulator only for testing/validation purposes! DO NOT expose to engine.
    }
