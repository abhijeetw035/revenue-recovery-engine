from django.test import TestCase, Client
from recovery.models import Transaction, Experiment, Policy
import json

class APITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tx = Transaction.objects.create(
            amount=100.0,
            payment_method='UPI',
            failure_reason='Insufficient Funds',
            customer_id='CUST_001',
            segment='UPI | Insufficient Funds | MID_VALUE',
            risk_level='LOW',
            status='PENDING'
        )
        
    def test_summary_api(self):
        response = self.client.get('/api/summary/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)['data']
        self.assertEqual(data['transaction_count'], 1)
        self.assertIn('by_reason', data)
        self.assertIn('by_segment', data)
        
    def test_experiments_api(self):
        response = self.client.get('/api/experiments/')
        self.assertEqual(response.status_code, 200)
        
    def test_policies_api(self):
        response = self.client.get('/api/policies/')
        self.assertEqual(response.status_code, 200)
        
    def test_audit_api(self):
        response = self.client.get('/api/audit/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)['data']
        self.assertEqual(len(data), 1)
