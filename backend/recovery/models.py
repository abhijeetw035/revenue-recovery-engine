from django.db import models
import uuid

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    failure_reason = models.CharField(max_length=100)
    customer_id = models.CharField(max_length=100)
    segment = models.CharField(max_length=100)
    risk_level = models.CharField(max_length=20)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.id} - {self.amount} - {self.failure_reason}"

class Experiment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_segment = models.CharField(max_length=100)
    arms = models.JSONField() # e.g. ["NONE", "DELAYED_RETRY"]
    random_seed = models.IntegerField()
    status = models.CharField(max_length=20, default='CREATED') # CREATED, RUNNING, COMPLETED
    created_at = models.DateTimeField(auto_now_add=True)

class Assignment(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='assignments')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='assignments')
    arm = models.CharField(max_length=50)
    
    class Meta:
        unique_together = ('experiment', 'transaction')

class Outcome(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='outcomes')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='outcomes')
    recovered = models.BooleanField(default=False)
    recovered_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    intervention_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    class Meta:
        unique_together = ('experiment', 'transaction')
