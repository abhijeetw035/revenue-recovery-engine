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

