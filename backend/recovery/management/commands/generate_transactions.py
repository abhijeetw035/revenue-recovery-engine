from django.core.management.base import BaseCommand
from recovery.models import Transaction
import numpy as np
import uuid

class Command(BaseCommand):
    help = 'Generates a synthetic dataset of failed transactions'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10000, help='Number of transactions to generate')
        parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')

    def handle(self, *args, **options):
        count = options['count']
        seed = options['seed']

        np.random.seed(seed)
        
        self.stdout.write(f'Generating {count} transactions with seed {seed}...')

        # Distributions
        payment_methods = ['UPI', 'Credit Card', 'Debit Card', 'Net Banking']
        pm_probs = [0.70, 0.15, 0.10, 0.05]

        failure_reasons = ['Insufficient Funds', 'Technical Decline', 'Risk Block', 'Invalid Details']
        fr_probs = [0.40, 0.30, 0.20, 0.10]

        risk_levels = ['LOW', 'MEDIUM', 'HIGH']
        rl_probs = [0.60, 0.30, 0.10]

        # Generate data
        amounts = np.round(np.random.lognormal(mean=7.0, sigma=1.0, size=count), 2)
        # Cap outliers and enforce minimums
        amounts = np.clip(amounts, 10.0, 100000.0)
        
        pms = np.random.choice(payment_methods, size=count, p=pm_probs)
        frs = np.random.choice(failure_reasons, size=count, p=fr_probs)
        rls = np.random.choice(risk_levels, size=count, p=rl_probs)
        
        # 5000 unique customers
        customer_ids = [f'CUST_{np.random.randint(1, 5001):04d}' for _ in range(count)]

        transactions_to_create = []
        for i in range(count):
            amount = amounts[i]
            pm = pms[i]
            fr = frs[i]
            
            # Simple segmentation logic
            if amount < 500:
                band = 'LOW_VALUE'
            elif amount <= 5000:
                band = 'MID_VALUE'
            else:
                band = 'HIGH_VALUE'
                
            segment = f"{pm} | {fr} | {band}"

            tx = Transaction(
                id=uuid.uuid4(),
                amount=amount,
                payment_method=pm,
                failure_reason=fr,
                customer_id=customer_ids[i],
                segment=segment,
                risk_level=rls[i]
            )
            transactions_to_create.append(tx)

        Transaction.objects.bulk_create(transactions_to_create, batch_size=1000)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} transactions'))
