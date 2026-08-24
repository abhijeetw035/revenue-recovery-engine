from recovery.models import Transaction, ExperimentResult

def calculate_expected_net_value(transaction: Transaction, experiment_result: ExperimentResult) -> float:
    """
    Calculates the expected net value of applying an intervention to a transaction.
    
    Expected Net Value = Expected Incremental Recovery Value - Intervention Cost
    where Expected Incremental Recovery Value = lift * transaction.amount
    
    Uses only observable information produced by experiments.
    """
    if experiment_result is None or experiment_result.treatment == 'NONE':
        return 0.0
        
    expected_incremental_recovery = experiment_result.lift * float(transaction.amount)
    
    # Cost is the average observed cost from the experiment
    cost = experiment_result.average_cost
    
    return expected_incremental_recovery - cost
