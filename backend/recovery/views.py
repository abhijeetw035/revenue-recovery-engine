from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from .models import Transaction, Experiment, ExperimentResult, Policy, Execution
import json
import os

class RevenueSummaryView(APIView):
    def get(self, request):
        summary = Transaction.objects.aggregate(
            transaction_count=Count('id'),
            revenue_at_risk=Sum('amount')
        )
        
        # Ensure we return 0 if there are no transactions
        revenue_at_risk = summary['revenue_at_risk'] or 0.0
        
        # Breakdown by failure reason
        reasons = list(Transaction.objects.values('failure_reason').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-count'))

        # Breakdown by segment
        segments = list(Transaction.objects.values('segment').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-count'))
        
        return Response({
            "status": "success",
            "data": {
                "transaction_count": summary['transaction_count'],
                "revenue_at_risk": float(revenue_at_risk),
                "by_reason": reasons,
                "by_segment": segments
            }
        })

class ExperimentListView(APIView):
    def get(self, request):
        experiments = Experiment.objects.all().order_by('-created_at')
        data = []
        for exp in experiments:
            results = list(exp.results.all().values())
            data.append({
                "id": str(exp.id),
                "target_segment": exp.target_segment,
                "arms": exp.arms,
                "status": exp.status,
                "created_at": exp.created_at,
                "results": results
            })
        return Response({"status": "success", "data": data})

class PolicyListView(APIView):
    def get(self, request):
        policies = Policy.objects.all().order_by('segment', '-version')
        data = []
        for p in policies:
            data.append({
                "id": str(p.id),
                "segment": p.segment,
                "action": p.action,
                "version": p.version,
                "reason": p.reason,
                "created_at": p.created_at
            })
        return Response({"status": "success", "data": data})

class ImpactView(APIView):
    def get(self, request):
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'demo_impact.json'), 'r') as f:
                data = json.load(f)
            return Response({"status": "success", "data": data})
        except FileNotFoundError:
            return Response({"status": "error", "message": "Impact data not found. Run the demo evaluation first."})

class AuditView(APIView):
    def get(self, request):
        # Fetch a sample of transactions with their executions
        transactions = Transaction.objects.all().prefetch_related('executions')[:100]
        data = []
        for tx in transactions:
            execution = tx.executions.first()
            data.append({
                "id": str(tx.id),
                "amount": float(tx.amount),
                "segment": tx.segment,
                "failure_reason": tx.failure_reason,
                "status": tx.status,
                "attempt_count": tx.attempt_count,
                "action": execution.action if execution else ("NONE" if tx.status == "PENDING" else tx.status),
                "expected_net_value": execution.expected_net_value if execution else 0.0,
                "estimated_cost": execution.estimated_cost if execution else 0.0,
            })
        return Response({"status": "success", "data": data})
