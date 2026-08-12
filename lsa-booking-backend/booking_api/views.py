from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import LSA_Profile, Booking_Request, Payment
from .serializers import LSASerializer, BookingRequestSerializer
from .services import process_payment_with_external_service
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.request import Request
from typing import Any
import logging

logger = logging.getLogger(__name__)

class LSASearchView(APIView):
    """
    API endpoint to search for Learning Support Assistants (LSAs) by skill.
    Implements prefetch_related to optimize database queries and avoid the N+1 problem.
    """
    
    def get(self, request: Request) -> Response:
        skill: str | None = request.query_params.get('skill', None)
        
        # Using prefetch_related to avoid N+1 query problem
        lsas: QuerySet[LSA_Profile] = LSA_Profile.objects.all().prefetch_related('skills')
        
        if skill:
            lsas = lsas.filter(skills__name__icontains=skill).distinct()
            
        serializer = LSASerializer(lsas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class BookingView(APIView):
    """
    API endpoint to create a new booking request.
    Handles validation, double-booking prevention (via serializer), 
    and mock external payment integration securely.
    """

    def post(self, request: Request) -> Response:
        serializer = BookingRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Use a database transaction to ensure booking and payment are created together atomically
                with transaction.atomic():
                    # Save booking as pending
                    booking: Booking_Request = serializer.save(status='PENDING')
                    
                    # Create a pending payment
                    payment: Payment = Payment.objects.create(booking=booking, amount=100.00)
                
                # Call mock external service (outside the transaction to avoid holding DB locks during network IO)
                ext_response: dict[str, Any] = process_payment_with_external_service(booking.id, payment.amount)
                
                if not ext_response['success']:
                    with transaction.atomic():
                        booking.status = 'CANCELLED'
                        booking.save(update_fields=['status'])
                        payment.status = 'FAILED'
                        payment.save(update_fields=['status'])
                        
                    return Response({
                        "error": "External verification/payment failed.",
                        "details": ext_response.get('error')
                    }, status=status.HTTP_502_BAD_GATEWAY)
                    
                return Response(BookingRequestSerializer(booking).data, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                logger.error(f"Unexpected error creating booking: {str(e)}", exc_info=True)
                return Response({"error": "An unexpected server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PaymentWebhookView(APIView):
    def post(self, request):
        """
        Webhook to receive async payment success/failure events.
        """
        booking_id = request.data.get('booking_id')
        payment_status = request.data.get('status')
        transaction_id = request.data.get('transaction_id')
        
        try:
            payment = Payment.objects.get(booking__id=booking_id)
            booking = payment.booking
            
            if payment_status == 'success':
                payment.status = 'SUCCESS'
                payment.transaction_id = transaction_id
                booking.status = 'CONFIRMED'
            else:
                payment.status = 'FAILED'
                booking.status = 'CANCELLED'
                
            payment.save()
            booking.save()
            
            return Response({"message": "Webhook processed successfully"}, status=status.HTTP_200_OK)
        except Payment.DoesNotExist:
            return Response({"error": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)
