from django.test import TestCase
from recovery.models import Transaction, CustomerState
from recovery.safety import check_safety, MAX_ATTEMPTS, MAX_CONTACTS, HIGH_VALUE_THRESHOLD

class SafetyTest(TestCase):
    def setUp(self):
        self.tx = Transaction.objects.create(
            amount=100.0,
            payment_method='UPI',
            failure_reason='Insufficient Funds',
            customer_id='CUST_001',
            segment='UPI | Insufficient Funds | MID_VALUE',
            risk_level='LOW'
        )

    def test_none_is_always_safe(self):
        # Even if expected net value is negative, NONE is safe
        is_safe, reason = check_safety(self.tx, 'NONE', -5.0)
        self.assertTrue(is_safe)
        self.assertIn("NONE", reason)

    def test_negative_net_value(self):
        is_safe, reason = check_safety(self.tx, 'SMS', -1.0)
        self.assertFalse(is_safe)
        self.assertIn("negative", reason)

    def test_max_attempts(self):
        self.tx.attempt_count = MAX_ATTEMPTS
        is_safe, reason = check_safety(self.tx, 'SMS', 10.0)
        self.assertFalse(is_safe)
        self.assertIn("maximum attempts", reason)

    def test_opt_out(self):
        CustomerState.objects.create(customer_id='CUST_001', opted_out=True)
        is_safe, reason = check_safety(self.tx, 'SMS', 10.0)
        self.assertFalse(is_safe)
        self.assertIn("opted out", reason)

    def test_max_contacts(self):
        CustomerState.objects.create(customer_id='CUST_001', contact_count=MAX_CONTACTS)
        is_safe, reason = check_safety(self.tx, 'SMS', 10.0)
        self.assertFalse(is_safe)
        self.assertIn("maximum customer contacts", reason)

    def test_high_value(self):
        self.tx.amount = HIGH_VALUE_THRESHOLD + 1.0
        is_safe, reason = check_safety(self.tx, 'SMS', 10.0)
        self.assertFalse(is_safe)
        self.assertIn("human review", reason)

    def test_high_risk(self):
        self.tx.risk_level = 'HIGH'
        is_safe, reason = check_safety(self.tx, 'SMS', 10.0)
        self.assertFalse(is_safe)
        self.assertIn("human review", reason)

    def test_safe(self):
        is_safe, reason = check_safety(self.tx, 'SMS', 10.0)
        self.assertTrue(is_safe)
        self.assertEqual("Safe", reason)
