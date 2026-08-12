# LSA Booking Backend System

This is a small backend system built for booking Learning Support Assistants (LSAs).

## Features
* **LSA Search API**: Search for LSAs by skills with optimized queries (avoids N+1 problem using `prefetch_related`).
* **Booking API**: Book an LSA while preventing double-booking and overlapping time slots.
* **Mock External Verification/Payment**: Integrates with a simulated external API via `requests`, complete with exception handling.
* **Webhook Support**: Allows external services to update the booking status asynchronously.
* **Automated Tests**: Comprehensive test suite written in `pytest`.
* **CI/CD**: GitHub Actions workflow to run tests on push.

## Setup Instructions

### 1. Clone the repository and navigate into it:
```bash
cd lsa-booking-backend
```

### 2. Create and activate a virtual environment:
```bash
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies:
```bash
pip install django djangorestframework pytest pytest-django requests
# Or pip install -r requirements.txt if present
```

### 4. Apply Database Migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Run the Server:
```bash
python manage.py runserver
```

## API Endpoints

### 1. Search LSAs
`GET /api/v1/lsas/search/?skill=Python`
* Returns a list of available LSAs with matching skills.

### 2. Create Booking
`POST /api/v1/bookings/`
```json
{
    "parent": 1,
    "lsa": 1,
    "start_time": "2024-05-15T10:00:00Z",
    "end_time": "2024-05-15T12:00:00Z"
}
```

### 3. Payment Webhook
`POST /api/v1/payments/webhook/`
```json
{
    "booking_id": 1,
    "status": "success",
    "transaction_id": "txn-abc-123"
}
```

## Architectural Decisions

### N+1 Query Optimization
When fetching LSAs along with their skills (Many-to-Many relationship), doing this naively would result in 1 query to fetch `N` LSAs, and `N` subsequent queries to fetch skills for each LSA (the N+1 problem).
**Solution:** We used `prefetch_related('skills')` in the search view. This fetches all related skills in a single, secondary query, reducing the total queries to 2 regardless of how many LSAs are returned.

### Django MVT vs Flask MVC
* **Django (MVT - Model-View-Template)**: Django comes with batteries included (ORM, Admin, Authentication). Its structure enforcing Models (Data), Views (Logic), and Templates (Presentation) allows for rapid development of data-driven apps. We used Django REST Framework which acts as the "Template" layer by serializing data to JSON.
* **Flask (MVC - Model-View-Controller)**: Flask is a micro-framework that gives developers more flexibility to choose their ORM (like SQLAlchemy) and structure.
* **Why Django MVT for this?** Since the project required a robust database structure with complex relationships and validation (preventing overlapping bookings), Django's built-in ORM and DRF's out-of-the-box model serializers made it much faster and more structured to build the API compared to manually gluing SQLAlchemy and Marshmallow in Flask.

## Running Tests
Run the test suite using `pytest`:
```bash
pytest tests/
```
