from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from .models import Transaction

class RevenueSummaryView(APIView):
    def get(self, request):
        summary = Transaction.objects.aggregate(
            transaction_count=Count('id'),
            revenue_at_risk=Sum('amount')
        )
        
        # Ensure we return 0 if there are no transactions
        revenue_at_risk = summary['revenue_at_risk'] or 0.0
        
        return Response({
            "status": "success",
            "data": {
                "transaction_count": summary['transaction_count'],
                "revenue_at_risk": float(revenue_at_risk)
            }
        })
