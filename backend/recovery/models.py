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

class ExperimentResult(models.Model):
    """Stores the lift analysis result for one treatment arm vs control."""
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='results')
    segment = models.CharField(max_length=100)
    treatment = models.CharField(max_length=50)  # The treatment arm name
    control_n = models.IntegerField()             # Control group sample size
    treatment_n = models.IntegerField()           # Treatment group sample size
    control_rate = models.FloatField()            # Control recovery rate
    treatment_rate = models.FloatField()          # Treatment recovery rate
    lift = models.FloatField()                    # Absolute lift = treatment_rate - control_rate
    ci_lower = models.FloatField()               # 95% CI lower bound
    ci_upper = models.FloatField()               # 95% CI upper bound
    evidence_status = models.CharField(max_length=30)  # INSUFFICIENT_SAMPLE, POSITIVE, NEGATIVE, NEUTRAL
    sufficient_sample = models.BooleanField()    # Whether sample size meets minimum threshold
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('experiment', 'treatment', 'segment')

class Policy(models.Model):
    """
    One record per (segment, version).  The latest active version for a
    segment is the current policy for that segment.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    segment = models.CharField(max_length=100, db_index=True)
    action = models.CharField(max_length=50)          # e.g. 'DELAYED_RETRY' or 'NONE'
    version = models.PositiveIntegerField()            # monotonically increasing per segment
    source_experiment = models.ForeignKey(
        Experiment, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='policies'
    )
    reason = models.TextField()                        # human-readable explanation
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('segment', 'version')
        ordering = ['-version']

    def __str__(self):
        return f"Policy v{self.version} | {self.segment} → {self.action}"
