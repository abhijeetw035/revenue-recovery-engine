import numpy as np
from django.db import transaction as db_transaction
from recovery.models import Transaction, Experiment, Assignment, Outcome
from recovery.simulator import simulate_outcome

class ExperimentEngine:
    @staticmethod
    @db_transaction.atomic
    def create_and_assign_experiment(target_segment, arms, random_seed):
        """
        Creates an experiment and assigns all eligible transactions
        to the specified arms using a reproducible random seed.
        """
        # 1. Create the experiment record
        experiment = Experiment.objects.create(
            target_segment=target_segment,
            arms=arms,
            random_seed=random_seed,
            status='CREATED'
        )

        # 2. Eligibility selection
        # Stratification is inherently handled because we are targeting a specific segment
        # which already groups by payment_method, failure_reason, and band.
        eligible_transactions = list(Transaction.objects.filter(segment=target_segment).order_by('id'))
        
        if not eligible_transactions:
            return experiment
            
        n_transactions = len(eligible_transactions)
        
        # 3. Randomization
        np.random.seed(random_seed)
        
        # Uniformly distribute across arms
        assigned_arms = np.random.choice(arms, size=n_transactions)
        
        # 4. Store Assignments
        assignments_to_create = []
        for i, tx in enumerate(eligible_transactions):
            assignments_to_create.append(
                Assignment(
                    experiment=experiment,
                    transaction=tx,
                    arm=assigned_arms[i]
                )
            )
            
        Assignment.objects.bulk_create(assignments_to_create, batch_size=1000)
        
        return experiment

    @staticmethod
    def execute_experiment(experiment):
        """
        Executes an experiment by running the outcome simulator
        for all assignments, without accessing hidden ground truth.
        """
        experiment.status = 'RUNNING'
        experiment.save()
        
        assignments = Assignment.objects.filter(experiment=experiment).select_related('transaction')
        outcomes_to_create = []
        
        # Iterate over assignments and simulate outcomes
        # Use the experiment seed combined with transaction id hash to ensure reproducible noise
        # that doesn't just repeat identically for every single row.
        for assignment in assignments:
            tx = assignment.transaction
            arm = assignment.arm
            
            # The transaction segment format is "PM | FR | BAND"
            parts = [p.strip() for p in tx.segment.split('|')]
            if len(parts) == 3:
                pm, fr, band = parts
            else:
                pm, fr, band = tx.payment_method, tx.failure_reason, 'MID_VALUE'
                
            # Create a unique but deterministic seed for this specific execution
            tx_seed = hash(f"{experiment.random_seed}_{tx.id}") % (2**32 - 1)
            
            # Call simulator - ONLY receiving the observable outcome
            result = simulate_outcome(
                transaction_amount=tx.amount,
                payment_method=pm,
                failure_reason=fr,
                band=band,
                action=arm,
                seed=tx_seed
            )
            
            outcomes_to_create.append(
                Outcome(
                    experiment=experiment,
                    transaction=tx,
                    recovered=result['recovered'],
                    recovered_amount=result['recovered_amount'],
                    intervention_cost=result['cost']
                )
            )
            
        # Store observed outcomes
        Outcome.objects.bulk_create(outcomes_to_create, batch_size=1000)
        
        experiment.status = 'COMPLETED'
        experiment.save()
        
        return experiment
