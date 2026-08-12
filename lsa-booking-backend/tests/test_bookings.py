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
        # Mock external service to return success
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
        
        # Verify payment mock was called
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
        
        # Create first booking
        Booking_Request.objects.create(
            parent=sample_data['parent'],
            lsa=sample_data['lsa'],
            start_time=start_time,
            end_time=end_time,
            status='CONFIRMED'
        )
        
        # Try to create second overlapping booking
        payload = {
            'parent': sample_data['parent'].id,
            'lsa': sample_data['lsa'].id,
            # Partially overlapping
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
        
        # Ensure status was set to cancelled
        booking = Booking_Request.objects.latest('id')
        assert booking.status == 'CANCELLED'

@pytest.mark.django_db
class TestLSASearchAPI:
    def test_lsa_search_success_and_n_plus_1(self, api_client, django_assert_num_queries):
        # Create some LSAs and skills
        skill_python = Skill.objects.create(name="Python")
        skill_math = Skill.objects.create(name="Math")
        
        lsa1 = LSA_Profile.objects.create(name="Alice")
        lsa1.skills.add(skill_python)
        
        lsa2 = LSA_Profile.objects.create(name="Bob")
        lsa2.skills.add(skill_math)
        
        lsa3 = LSA_Profile.objects.create(name="Charlie")
        lsa3.skills.add(skill_python, skill_math)
        
        # Search for Python
        # Expecting 2 queries: one for LSAs, one for prefetched skills (because we used distinct(), sqlite might add something, but usually it's 2)
        # Actually count queries without assert first to be safe, but let's test it.
        with django_assert_num_queries(2):
            response = api_client.get(reverse('lsa-search') + '?skill=Python')
            
        assert response.status_code == 200
        assert len(response.data) == 2
        names = [item['name'] for item in response.data]
        assert "Alice" in names
        assert "Charlie" in names
