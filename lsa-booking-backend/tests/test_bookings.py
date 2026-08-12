import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from booking_api.models import Parent, Skill, LSA_Profile, Booking_Request, Payment
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def sample_data():
    parent = Parent.objects.create(name="John Doe", email="john@example.com")
    skill1 = Skill.objects.create(name="Python")
    skill2 = Skill.objects.create(name="Math")
    
    lsa = LSA_Profile.objects.create(name="Jane Smith")
    lsa.skills.add(skill1, skill2)
    
    return {'parent': parent, 'lsa': lsa, 'skill': skill1}

@pytest.mark.django_db
class TestBookingAPI:
    @patch('booking_api.views.process_payment_with_external_service')
    def test_valid_booking_creation(self, mock_payment, api_client, sample_data):
        mock_payment.return_value = {'success': True, 'transaction_id': 'mock-txn-123'}
        
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        payload = {
            'parent': sample_data['parent'].id,
            'lsa': sample_data['lsa'].id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        
        response = api_client.post(reverse('booking-create'), payload, format='json')
        
        assert response.status_code == 201
        assert response.data['status'] == 'PENDING'
        
        booking = Booking_Request.objects.get(id=response.data['id'])
        payment = Payment.objects.get(booking=booking)
        mock_payment.assert_called_once_with(booking.id, payment.amount)
        
    @patch('booking_api.views.process_payment_with_external_service')
    def test_invalid_booking_time(self, mock_payment, api_client, sample_data):
        # end_time before start_time
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time - timedelta(hours=2)
        
        payload = {
            'parent': sample_data['parent'].id,
            'lsa': sample_data['lsa'].id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        
        response = api_client.post(reverse('booking-create'), payload, format='json')
        
        assert response.status_code == 400
        assert "error" in response.data
        mock_payment.assert_not_called()

    @patch('booking_api.views.process_payment_with_external_service')
    def test_overlapping_booking(self, mock_payment, api_client, sample_data):
        mock_payment.return_value = {'success': True, 'transaction_id': 'mock-txn-123'}
        
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        Booking_Request.objects.create(
            parent=sample_data['parent'],
            lsa=sample_data['lsa'],
            start_time=start_time,
            end_time=end_time,
            status='CONFIRMED'
        )
        
        payload = {
            'parent': sample_data['parent'].id,
            'lsa': sample_data['lsa'].id,
            'start_time': (start_time + timedelta(hours=1)).isoformat(),
            'end_time': (end_time + timedelta(hours=1)).isoformat()
        }
        
        response = api_client.post(reverse('booking-create'), payload, format='json')
        assert response.status_code == 400
        assert "already booked" in str(response.data)

    @patch('booking_api.views.process_payment_with_external_service')
    def test_external_service_failure(self, mock_payment, api_client, sample_data):
        mock_payment.return_value = {'success': False, 'error': 'Connection timeout'}
        
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        
        payload = {
            'parent': sample_data['parent'].id,
            'lsa': sample_data['lsa'].id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        
        response = api_client.post(reverse('booking-create'), payload, format='json')
        
        assert response.status_code == 502
        assert "failed" in response.data['error']
        
        booking = Booking_Request.objects.latest('id')
        assert booking.status == 'CANCELLED'

    def test_invalid_input_missing_fields(self, api_client):
        # Missing start_time and end_time
        payload = {'parent': 999, 'lsa': 999}
        response = api_client.post(reverse('booking-create'), payload, format='json')
        
        assert response.status_code == 400
        assert "start_time" in response.data
        assert "parent" in str(response.data) # Invalid PK check

@pytest.mark.django_db
class TestPaymentWebhookAPI:
    @pytest.fixture
    def pending_booking(self, sample_data):
        booking = Booking_Request.objects.create(
            parent=sample_data['parent'],
            lsa=sample_data['lsa'],
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            status='PENDING'
        )
        Payment.objects.create(booking=booking, amount=100.00, status='PENDING')
        return booking

    def test_webhook_success(self, api_client, pending_booking):
        payload = {
            "booking_id": pending_booking.id,
            "status": "success",
            "transaction_id": "txn-abc"
        }
        headers = {'HTTP_X_WEBHOOK_SIGNATURE': 'mock-secret-signature'}
        response = api_client.post(reverse('payment-webhook'), payload, format='json', **headers)
        
        assert response.status_code == 200
        pending_booking.refresh_from_db()
        assert pending_booking.status == 'CONFIRMED'
        assert pending_booking.payment.status == 'SUCCESS'

    def test_webhook_failure(self, api_client, pending_booking):
        payload = {
            "booking_id": pending_booking.id,
            "status": "failed"
        }
        headers = {'HTTP_X_WEBHOOK_SIGNATURE': 'mock-secret-signature'}
        response = api_client.post(reverse('payment-webhook'), payload, format='json', **headers)
        
        assert response.status_code == 200
        pending_booking.refresh_from_db()
        assert pending_booking.status == 'CANCELLED'
        assert pending_booking.payment.status == 'FAILED'

    def test_webhook_missing_signature(self, api_client, pending_booking):
        payload = {"booking_id": pending_booking.id, "status": "success"}
        response = api_client.post(reverse('payment-webhook'), payload, format='json')
        assert response.status_code == 401

    def test_webhook_invalid_payload(self, api_client):
        headers = {'HTTP_X_WEBHOOK_SIGNATURE': 'mock-secret-signature'}
        response = api_client.post(reverse('payment-webhook'), {}, format='json', **headers)
        assert response.status_code == 400
        assert "Missing required fields" in response.data['error']

    def test_webhook_idempotency(self, api_client, pending_booking):
        # Set to SUCCESS already
        pending_booking.status = 'CONFIRMED'
        pending_booking.save()
        pending_booking.payment.status = 'SUCCESS'
        pending_booking.payment.save()
        
        payload = {
            "booking_id": pending_booking.id,
            "status": "failed" # Try to change to failed
        }
        headers = {'HTTP_X_WEBHOOK_SIGNATURE': 'mock-secret-signature'}
        response = api_client.post(reverse('payment-webhook'), payload, format='json', **headers)
        
        assert response.status_code == 200
        assert "already processed" in response.data['message']
        
        pending_booking.refresh_from_db()
        assert pending_booking.status == 'CONFIRMED' # Did not change

    def test_webhook_nonexistent_booking(self, api_client):
        payload = {"booking_id": 9999, "status": "success", "transaction_id": "123"}
        headers = {'HTTP_X_WEBHOOK_SIGNATURE': 'mock-secret-signature'}
        response = api_client.post(reverse('payment-webhook'), payload, format='json', **headers)
        assert response.status_code == 404


@pytest.mark.django_db
class TestLSASearchAPI:
    def test_lsa_search_success_and_n_plus_1(self, api_client, django_assert_num_queries):
        skill_python = Skill.objects.create(name="Python")
        skill_math = Skill.objects.create(name="Math")
        
        lsa1 = LSA_Profile.objects.create(name="Alice")
        lsa1.skills.add(skill_python)
        
        lsa2 = LSA_Profile.objects.create(name="Bob")
        lsa2.skills.add(skill_math)
        
        lsa3 = LSA_Profile.objects.create(name="Charlie")
        lsa3.skills.add(skill_python, skill_math)
        
        with django_assert_num_queries(2):
            response = api_client.get(reverse('lsa-search') + '?skill=Python')
            
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_lsa_search_no_results(self, api_client):
        response = api_client.get(reverse('lsa-search') + '?skill=NonExistentSkill')
        assert response.status_code == 200
        assert len(response.data) == 0
