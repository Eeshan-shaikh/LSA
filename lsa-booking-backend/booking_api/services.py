import logging
import requests
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

def process_payment_with_external_service(booking_id: int, amount: Decimal) -> dict[str, Any]:
    """
    Mock external service call for payment/verification.
    Uses the requests library to simulate network interaction.
    
    Args:
        booking_id (int): The ID of the booking to verify/pay.
        amount (Decimal): The amount to charge.
        
    Returns:
        dict: A dictionary containing 'success' status and either a 'transaction_id' or 'error' message.
    """
    try:
        # Mocking an external call to httpbin to simulate an external API request
        response = requests.post(
            'https://httpbin.org/post', 
            json={'booking_id': booking_id, 'amount': float(amount)},
            timeout=5
        )
        response.raise_for_status()
        
        return {
            'success': True,
            'transaction_id': f'mock-txn-{booking_id}'
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"External service failed for booking {booking_id}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
