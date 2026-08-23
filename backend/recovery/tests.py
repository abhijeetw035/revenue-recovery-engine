from django.test import TestCase
from django.core.management import call_command
from recovery.models import Transaction

class TransactionGeneratorTest(TestCase):
    def test_generator_creates_records(self):
        # Generate a small batch
        call_command('generate_transactions', count=100, seed=1)
        self.assertEqual(Transaction.objects.count(), 100)
        
        # Check basic fields exist
        tx = Transaction.objects.first()
        self.assertIsNotNone(tx.amount)
        self.assertIsNotNone(tx.payment_method)
        self.assertIsNotNone(tx.segment)

    def test_reproducibility(self):
        call_command('generate_transactions', count=50, seed=42)
        batch1_amounts = list(Transaction.objects.all().values_list('amount', flat=True))
        batch1_segments = list(Transaction.objects.all().values_list('segment', flat=True))
        
        Transaction.objects.all().delete()
        
        call_command('generate_transactions', count=50, seed=42)
        batch2_amounts = list(Transaction.objects.all().values_list('amount', flat=True))
        batch2_segments = list(Transaction.objects.all().values_list('segment', flat=True))
        
        self.assertEqual(batch1_amounts, batch2_amounts)
        self.assertEqual(batch1_segments, batch2_segments)

    def test_different_seeds_produce_different_data(self):
        call_command('generate_transactions', count=50, seed=1)
        batch1_amounts = list(Transaction.objects.all().values_list('amount', flat=True))
        
        Transaction.objects.all().delete()
        
        call_command('generate_transactions', count=50, seed=2)
        batch2_amounts = list(Transaction.objects.all().values_list('amount', flat=True))
        
        self.assertNotEqual(batch1_amounts, batch2_amounts)

    def test_clear_option(self):
        # Generate initial batch
        call_command('generate_transactions', count=50, seed=1)
        self.assertTrue(Transaction.objects.count() >= 50)
        
        # Generate new batch with --clear
        call_command('generate_transactions', count=20, seed=2, clear=True)
        self.assertEqual(Transaction.objects.count(), 20)

class RevenueSummaryViewTest(TestCase):
    def test_summary_api(self):
        call_command('generate_transactions', count=10, seed=123)
        response = self.client.get('/api/summary/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['transaction_count'], 10)
        self.assertTrue(data['data']['revenue_at_risk'] > 0)

class SimulatorTest(TestCase):
    def test_reproducibility(self):
        from recovery.simulator import simulate_outcome
        
        # Same seed should give same result
        res1 = simulate_outcome(100.0, 'UPI', 'Technical Decline', 'MID_VALUE', 'IMMEDIATE_RETRY', seed=42)
        res2 = simulate_outcome(100.0, 'UPI', 'Technical Decline', 'MID_VALUE', 'IMMEDIATE_RETRY', seed=42)
        self.assertEqual(res1['recovered'], res2['recovered'])
        self.assertEqual(res1['cost'], res2['cost'])

    def test_effects_can_be_discovered(self):
        from recovery.simulator import simulate_outcome
        import numpy as np
        
        # Test large sample to discover effect
        # Insufficient Funds, NONE vs DELAYED_RETRY
        n_samples = 5000
        
        control_recoveries = 0
        for i in range(n_samples):
            res = simulate_outcome(100.0, 'UPI', 'Insufficient Funds', 'MID_VALUE', 'NONE', seed=i)
            if res['recovered']:
                control_recoveries += 1
                
        treatment_recoveries = 0
        for i in range(n_samples):
            res = simulate_outcome(100.0, 'UPI', 'Insufficient Funds', 'MID_VALUE', 'DELAYED_RETRY', seed=i + n_samples)
            if res['recovered']:
                treatment_recoveries += 1
                
        control_rate = control_recoveries / n_samples
        treatment_rate = treatment_recoveries / n_samples
        
        # Base is 0.10 + 0.05 (UPI) = 0.15
        # Treatment effect is +0.25 -> 0.40
        self.assertTrue(0.12 < control_rate < 0.18)
        self.assertTrue(0.37 < treatment_rate < 0.43)
        self.assertTrue(treatment_rate > control_rate)

    def test_none_is_better_for_invalid_details(self):
        from recovery.simulator import simulate_outcome
        
        # Test over sample since true_prob is not exposed
        n_samples = 1000
        cost_sms = 0
        cost_none = 0
        rec_sms = 0
        rec_none = 0
        
        for i in range(n_samples):
            res_none = simulate_outcome(100.0, 'Credit Card', 'Invalid Details', 'MID_VALUE', 'NONE', seed=i)
            res_sms = simulate_outcome(100.0, 'Credit Card', 'Invalid Details', 'MID_VALUE', 'SMS', seed=i)
            
            cost_none += res_none['cost']
            cost_sms += res_sms['cost']
            if res_none['recovered']: rec_none += 1
            if res_sms['recovered']: rec_sms += 1
            
        self.assertEqual(rec_none, 0)
        self.assertEqual(rec_sms, 0)
        self.assertTrue(cost_sms > cost_none)

    def test_counterintuitive_effect(self):
        from recovery.simulator import simulate_outcome
        
        n_samples = 5000
        rec_none = 0
        rec_retry = 0
        cost_retry = 0
        
        for i in range(n_samples):
            res_none = simulate_outcome(100.0, 'UPI', 'Risk Block', 'MID_VALUE', 'NONE', seed=i)
            res_retry = simulate_outcome(100.0, 'UPI', 'Risk Block', 'MID_VALUE', 'IMMEDIATE_RETRY', seed=i+n_samples)
            if res_none['recovered']: rec_none += 1
            if res_retry['recovered']: rec_retry += 1
            cost_retry += res_retry['cost']
            
        # Immediate retry on Risk Block makes recovery probability worse
        self.assertTrue(rec_retry < rec_none)
        # Also incurs huge friction cost (50 * 5000 = 250,000)
        self.assertTrue(cost_retry >= 200000.0)

