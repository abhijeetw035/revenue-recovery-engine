from django.test import TestCase
from recovery.models import Transaction, Execution, CustomerState
from recovery.evaluation import (
    get_deterministic_seed, 
    evaluate_decisions, 
    run_naive_baseline, 
    run_static_baseline, 
    run_learned_strategy
)
from django.core.management import call_command

class EvaluationTest(TestCase):
    def setUp(self):
        # Create a few explicit transactions
        self.tx1 = Transaction.objects.create(
            amount=100.0,
            payment_method='UPI',
            failure_reason='Insufficient Funds',
            customer_id='CUST_001',
            segment='UPI | Insufficient Funds | MID_VALUE',
            risk_level='LOW',
            status='PENDING'
        )
        self.tx2 = Transaction.objects.create(
            amount=200.0,
            payment_method='Credit Card',
            failure_reason='Technical Decline',
            customer_id='CUST_002',
            segment='Credit Card | Technical Decline | MID_VALUE',
            risk_level='LOW',
            status='PENDING'
        )
        self.tx3 = Transaction.objects.create(
            amount=300.0,
            payment_method='Netbanking',
            failure_reason='Risk Block',
            customer_id='CUST_003',
            segment='Netbanking | Risk Block | MID_VALUE',
            risk_level='HIGH',
            status='PENDING'
        )
        
    def test_deterministic_seed(self):
        seed1 = get_deterministic_seed(str(self.tx1.id), 'SMS')
        seed2 = get_deterministic_seed(str(self.tx1.id), 'SMS')
        seed3 = get_deterministic_seed(str(self.tx2.id), 'SMS')
        seed4 = get_deterministic_seed(str(self.tx1.id), 'WHATSAPP')
        
        self.assertEqual(seed1, seed2)  # Same tx, same action -> same seed
        self.assertNotEqual(seed1, seed3) # Different tx
        self.assertNotEqual(seed1, seed4) # Different action
        
    def test_naive_baseline(self):
        transactions = list(Transaction.objects.filter(status='PENDING'))
        decisions = run_naive_baseline(transactions)
        
        self.assertEqual(len(decisions), 3)
        for tx, action in decisions:
            self.assertEqual(action, 'IMMEDIATE_RETRY')
            
    def test_static_baseline(self):
        # tx1 (amount 100), tx2 (amount 200), tx3 (amount 300) are all < 5000.
        # Let's add a high value transaction.
        tx4 = Transaction.objects.create(
            amount=6000.0,
            payment_method='UPI',
            failure_reason='Technical Decline',
            customer_id='CUST_004',
            segment='UPI | Technical Decline | HIGH_VALUE',
            risk_level='LOW',
            status='PENDING'
        )
        transactions = list(Transaction.objects.all().order_by('amount'))
        decisions = run_static_baseline(transactions)
        
        # amounts: 100, 200, 300, 6000
        self.assertEqual(decisions[0][1], 'IMMEDIATE_RETRY') # <= 5000
        self.assertEqual(decisions[1][1], 'IMMEDIATE_RETRY') # <= 5000
        self.assertEqual(decisions[2][1], 'IMMEDIATE_RETRY') # <= 5000
        self.assertEqual(decisions[3][1], 'WHATSAPP') # > 5000
        
    def test_evaluate_decisions(self):
        decisions = [(self.tx1, 'NONE'), (self.tx2, 'NONE')]
        
        # When NONE is applied, recovery might still happen due to natural recovery.
        # But for this test, we can just verify the metrics structure.
        metrics = evaluate_decisions(decisions)
        
        self.assertEqual(metrics['total_transactions'], 2)
        self.assertIn('recovery_rate', metrics)
        self.assertIn('gross_recovery', metrics)
        self.assertIn('intervention_cost', metrics)
        self.assertIn('net_recovery', metrics)
        self.assertEqual(metrics['intervention_cost'], 0.0) # NONE costs 0

    def test_learned_strategy_isolation(self):
        """
        Verify that running the learned strategy rolls back database state
        (no actual Executions saved, tx status not permanently changed).
        """
        budget_limit = 1000.0
        
        # Act
        decisions = run_learned_strategy(budget_limit)
        
        # Assert
        # 1. We got decisions
        self.assertEqual(len(decisions), 3)
        
        # 2. Database state was NOT modified permanently
        self.assertEqual(Execution.objects.count(), 0)
        
        self.tx1.refresh_from_db()
        self.assertEqual(self.tx1.status, 'PENDING') # Should still be pending
        self.assertEqual(self.tx1.attempt_count, 0)
        
        self.assertEqual(CustomerState.objects.count(), 0)
