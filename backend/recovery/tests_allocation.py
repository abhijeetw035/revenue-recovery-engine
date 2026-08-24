from django.test import TestCase
from recovery.models import Transaction, Policy, Experiment, ExperimentResult, Execution, CustomerState
from recovery.allocator import allocate_interventions
from django.core.management import call_command

class AllocatorTest(TestCase):
    def setUp(self):
        call_command('generate_transactions', count=100, seed=1)
        self.tx1 = Transaction.objects.first()
        self.tx1.segment = 'TEST_SEGMENT'
        self.tx1.amount = 100.0
        self.tx1.risk_level = 'LOW'
        self.tx1.save()
        
        self.tx2 = Transaction.objects.last()
        self.tx2.segment = 'TEST_SEGMENT'
        self.tx2.amount = 200.0
        self.tx2.risk_level = 'LOW'
        self.tx2.save()

        # Mock an experiment and policy
        self.exp = Experiment.objects.create(
            target_segment='TEST_SEGMENT',
            arms=['NONE', 'SMS'],
            random_seed=1,
            status='COMPLETED'
        )
        self.er = ExperimentResult.objects.create(
            experiment=self.exp,
            segment='TEST_SEGMENT',
            treatment='SMS',
            control_n=100,
            treatment_n=100,
            control_rate=0.1,
            treatment_rate=0.3,
            lift=0.2, # 20% lift
            ci_lower=0.1,
            ci_upper=0.3,
            evidence_status='POSITIVE',
            sufficient_sample=True,
            average_cost=10.0 # Cost is 10
        )
        self.policy = Policy.objects.create(
            segment='TEST_SEGMENT',
            action='SMS',
            version=1,
            source_experiment=self.exp,
            reason='test'
        )

    def test_allocation_prioritizes_net_value(self):
        # tx1 expected net value = (0.2 * 100) - 10 = 10
        # tx2 expected net value = (0.2 * 200) - 10 = 30
        
        # Budget = 15. Only tx2 should be allocated.
        executions = allocate_interventions(budget_limit=15.0)
        
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].transaction, self.tx2)
        self.assertEqual(executions[0].action, 'SMS')
        self.assertEqual(executions[0].expected_net_value, 30.0)

    def test_negative_value_rejected(self):
        # Make tx1 amount so small that net value is negative
        self.tx1.amount = 10.0
        self.tx1.save()
        # tx1 expected net value = (0.2 * 10) - 10 = -8
        
        # Make tx2 amount small too
        self.tx2.amount = 10.0
        self.tx2.save()
        
        executions = allocate_interventions(budget_limit=100.0)
        self.assertEqual(len(executions), 0)
        
        # Transactions should be marked STOPPED due to safety
        self.tx1.refresh_from_db()
        self.assertEqual(self.tx1.status, 'STOPPED')

    def test_human_review_cases_skipped(self):
        self.tx2.amount = 20000.0 # High value
        self.tx2.save()
        
        executions = allocate_interventions(budget_limit=1000.0)
        
        # tx2 is high value, should be sent to HUMAN_REVIEW, not executed
        self.tx2.refresh_from_db()
        self.assertEqual(self.tx2.status, 'HUMAN_REVIEW')
        
        # tx1 should still be executed
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].transaction, self.tx1)

    def test_none_always_allowed(self):
        # Create a tx with a different segment that has no policy
        tx3 = Transaction.objects.create(
            amount=500.0,
            payment_method='UPI',
            failure_reason='Risk Block',
            customer_id='CUST_003',
            segment='NO_POLICY_SEGMENT',
            risk_level='LOW'
        )
        
        executions = allocate_interventions(budget_limit=0.0)
        
        # tx3 should default to NONE, consume 0 budget, and be marked STOPPED
        tx3.refresh_from_db()
        self.assertEqual(tx3.status, 'STOPPED')
        
        # A NONE execution record should exist
        none_exec = Execution.objects.filter(transaction=tx3).first()
        self.assertIsNotNone(none_exec)
        self.assertEqual(none_exec.action, 'NONE')
        self.assertEqual(none_exec.estimated_cost, 0.0)
