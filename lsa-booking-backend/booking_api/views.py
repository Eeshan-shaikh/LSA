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
    API endpoint to search for Learning Support Assistants (LSAs) by skill and availability.
    Implements prefetch_related to optimize database queries and avoid the N+1 problem.
    """
    
    def get(self, request: Request) -> Response:
        skill: str | None = request.query_params.get('skill', None)
        start_time: str | None = request.query_params.get('start_time', None)
        end_time: str | None = request.query_params.get('end_time', None)
        
        # Using prefetch_related to avoid N+1 query problem
        lsas: QuerySet[LSA_Profile] = LSA_Profile.objects.all().prefetch_related('skills')
        
        if skill:
            lsas = lsas.filter(skills__name__icontains=skill).distinct()
            
        if start_time and end_time:
            # Exclude LSAs that have an overlapping booking
            lsas = lsas.exclude(
                bookings__status__in=['PENDING', 'CONFIRMED'],
                bookings__start_time__lt=end_time,
                bookings__end_time__gt=start_time
            ).distinct()
            
        serializer = LSASerializer(lsas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class BookingView(APIView):
    """
    API endpoint to create a new booking request.
    Handles validation, race-condition safe double-booking prevention, 
    and robust mock external payment integration securely.
    """

    def post(self, request: Request) -> Response:
        try:
            # We use an atomic transaction for validation and creation to prevent race conditions
            with transaction.atomic():
                serializer = BookingRequestSerializer(data=request.data)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                lsa = serializer.validated_data['lsa']
                start_time = serializer.validated_data['start_time']
                end_time = serializer.validated_data['end_time']
                
                # Lock the LSA to prevent race conditions during concurrent bookings
                # select_for_update is highly effective in PostgreSQL/MySQL for this scenario.
                locked_lsa = LSA_Profile.objects.select_for_update().get(id=lsa.id)
                
                # Check for double-booking / overlapping bookings safely inside the lock
                overlapping_bookings = Booking_Request.objects.filter(
                    lsa=locked_lsa,
                    status__in=['PENDING', 'CONFIRMED'],
                    start_time__lt=end_time,
                    end_time__gt=start_time
                )
                
                if overlapping_bookings.exists():
                    return Response({"error": "LSA is already booked for this time slot."}, status=status.HTTP_400_BAD_REQUEST)
                
                # Save booking as pending
                booking: Booking_Request = serializer.save(status='PENDING')
                
                # Create a pending payment
                payment: Payment = Payment.objects.create(booking=booking, amount=100.00)
            
            # The atomic block is closed here. The DB lock is released.
            # Now we call the mock external service outside the transaction to avoid holding DB locks during network IO.
            ext_response: dict[str, Any] = process_payment_with_external_service(booking.id, payment.amount)
            
            if not ext_response['success']:
                # Open a new transaction to handle the failure state safely
                with transaction.atomic():
                    booking = Booking_Request.objects.get(id=booking.id)
                    payment = Payment.objects.get(id=payment.id)
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

class PaymentWebhookView(APIView):
    """
    Webhook to receive async payment success/failure events.
    Hardened with basic security (mock signature), payload validation, and idempotency.
    """
    def post(self, request: Request) -> Response:
        # 1. Mock Authentication / Signature Verification
        # In production, this would verify a cryptographic signature (e.g., HMAC-SHA256)
        signature = request.headers.get('X-Webhook-Signature')
        if signature != 'mock-secret-signature':
            return Response({"error": "Unauthorized or invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)
            
        # 2. Payload Validation
        booking_id = request.data.get('booking_id')
        payment_status = request.data.get('status')
        transaction_id = request.data.get('transaction_id')
        
        if not booking_id or not payment_status:
            return Response({"error": "Missing required fields: booking_id, status"}, status=status.HTTP_400_BAD_REQUEST)
            
        if payment_status not in ['success', 'failed']:
            return Response({"error": "Invalid status. Must be 'success' or 'failed'"}, status=status.HTTP_400_BAD_REQUEST)
            
        if payment_status == 'success' and not transaction_id:
            return Response({"error": "transaction_id is required for successful payments"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 3. Process Webhook Safely
        try:
            with transaction.atomic():
                # select_for_update to prevent race conditions during webhook processing
                payment = Payment.objects.select_for_update().get(booking__id=booking_id)
                booking = payment.booking
                
                # 4. Idempotency Check
                # If already processed, just acknowledge receipt
                if payment.status in ['SUCCESS', 'FAILED']:
                    return Response({"message": "Webhook already processed"}, status=status.HTTP_200_OK)
                
                if payment_status == 'success':
                    payment.status = 'SUCCESS'
                    payment.transaction_id = transaction_id
                    booking.status = 'CONFIRMED'
                else:
                    payment.status = 'FAILED'
                    booking.status = 'CANCELLED'
                    
                payment.save(update_fields=['status', 'transaction_id'])
                booking.save(update_fields=['status'])
                
            return Response({"message": "Webhook processed successfully"}, status=status.HTTP_200_OK)
            
        except Payment.DoesNotExist:
            return Response({"error": "Payment record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
