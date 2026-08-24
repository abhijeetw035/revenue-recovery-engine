from django.test import TestCase
from recovery.models import Transaction, ExperimentResult
from recovery.economics import calculate_expected_net_value

class EconomicsTest(TestCase):
    def test_calculate_expected_net_value(self):
        tx = Transaction.objects.create(
            amount=100.0,
            payment_method='UPI',
            failure_reason='Insufficient Funds',
            customer_id='CUST_001',
            segment='UPI | Insufficient Funds | MID_VALUE',
            risk_level='LOW'
        )
        
        er = ExperimentResult(
            lift=0.20,
            average_cost=5.0
        )
        
        # Expected value = (0.20 * 100) - 5.0 = 20.0 - 5.0 = 15.0
        net_value = calculate_expected_net_value(tx, er)
        self.assertAlmostEqual(net_value, 15.0)
        
    def test_negative_net_value(self):
        tx = Transaction.objects.create(
            amount=10.0,
            payment_method='UPI',
            failure_reason='Insufficient Funds',
            customer_id='CUST_001',
            segment='UPI | Insufficient Funds | LOW_VALUE',
            risk_level='LOW'
        )
        
        er = ExperimentResult(
            lift=0.10,
            average_cost=5.0
        )
        
        # Expected value = (0.10 * 10) - 5.0 = 1.0 - 5.0 = -4.0
        net_value = calculate_expected_net_value(tx, er)
        self.assertAlmostEqual(net_value, -4.0)

    def test_none_returns_zero(self):
        tx = Transaction.objects.create(amount=100.0)
        er = ExperimentResult(treatment='NONE', lift=0.10, average_cost=5.0)
        
        net_value = calculate_expected_net_value(tx, er)
        self.assertEqual(net_value, 0.0)
