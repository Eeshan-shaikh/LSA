# LSA Booking Backend System

This is a prototype backend system built for booking Learning Support Assistants (LSAs).

## Features
* **LSA Search API**: Retrieves available LSAs filtered by skills and optional time windows. Uses `prefetch_related` to eliminate N+1 query bottlenecks.
* **Booking API**: Creates a booking securely. Implements strict input validation and database-level locking (`select_for_update`) within atomic transactions to prevent race conditions and double-bookings.
* **External Verification/Payment**: Integrates with a simulated external API via the `requests` library. Designed to separate network I/O from database transactions to avoid holding long DB locks.
* **Secure Webhook Support**: Receives external async payment events. Implements idempotency, strict payload validation, and a mock signature verification mechanism.
* **Robust Testing Suite**: 13 automated tests built with `pytest`, covering success, edge cases, invalid data, missing payloads, webhook idempotency, and network failures.
* **CI/CD**: GitHub Actions workflow automatically installs dependencies and runs tests on push.

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
pip install -r requirements.txt
```

### 4. Setup Environment Variables:
Copy `.env.example` to `.env` and fill in the required variables (specifically `DJANGO_SECRET_KEY`).
```bash
cp .env.example .env
```

### 5. Apply Database Migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Run the Server:
```bash
python manage.py runserver
```

## API Endpoints

### 1. Search LSAs
**Endpoint:** `GET /api/v1/lsas/search/`  
**Purpose:** Finds LSAs that possess a given skill and are available during the specified timeframe.  
**Parameters:**
- `skill` (string) - Example: `Python`
- `start_time` (string, optional) - ISO 8601 format
- `end_time` (string, optional) - ISO 8601 format

**Example Request:**
```http
GET /api/v1/lsas/search/?skill=Python&start_time=2024-05-15T10:00:00Z&end_time=2024-05-15T12:00:00Z
```

**Success Response (200 OK):**
```json
[
    {
        "id": 1,
        "name": "Jane Smith",
        "skills": [{"id": 1, "name": "Python"}]
    }
]
```

### 2. Create Booking
**Endpoint:** `POST /api/v1/bookings/`  
**Purpose:** Creates a booking for an LSA. Validates input and safely blocks double-bookings.  

**Example Request:**
```json
{
    "parent": 1,
    "lsa": 1,
    "start_time": "2024-05-15T10:00:00Z",
    "end_time": "2024-05-15T12:00:00Z"
}
```

**Responses:**
* `201 Created`: Booking created successfully.
* `400 Bad Request`: Input validation failed (e.g., overlapping times, start_time >= end_time, missing fields).
* `502 Bad Gateway`: The external payment/verification service failed.

### 3. Payment Webhook
**Endpoint:** `POST /api/v1/payments/webhook/`  
**Purpose:** Asynchronously updates payment state. Requires `X-Webhook-Signature` header.  

**Example Request:**
```json
{
    "booking_id": 1,
    "status": "success",
    "transaction_id": "txn-abc-123"
}
```

**Responses:**
* `200 OK`: Webhook processed successfully (or acknowledged idempotently).
* `400 Bad Request`: Invalid payload or status.
* `401 Unauthorized`: Missing or invalid signature header.
* `404 Not Found`: Payment record does not exist.

## Architectural Decisions

### Django MVT vs Flask MVC
* **Django (MVT - Model-View-Template)**: Django comes with batteries included (ORM, Admin, Authentication). Its structure enforcing Models (Data), Views (Logic), and Templates (Presentation) allows for rapid development of data-driven apps. We used Django REST Framework which acts as the "Template" layer by serializing data to JSON.
* **Flask (MVC - Model-View-Controller)**: Flask is a micro-framework that gives developers more flexibility to choose their ORM (like SQLAlchemy) and structure.
* **Why Django MVT for this?** Since the project required a robust database structure with complex relationships and validation, Django's built-in ORM, migration system, and DRF's out-of-the-box model serializers made it much faster and more structured to build the API compared to manually gluing SQLAlchemy and Marshmallow in Flask.

### SQLite vs PostgreSQL
SQLite was selected for this take-home prototype to keep local setup lightweight, zero-configuration, and highly portable. 
However, **PostgreSQL is strongly preferred for production.** PostgreSQL offers superior database-level concurrency control (which empowers things like `select_for_update()`), better constraints handling, and scaling capabilities that SQLite lacks in high-throughput environments.

### Transaction Management and Network I/O
Database locks should never be held while waiting for network operations. In the `BookingView`, we execute a strict `transaction.atomic()` block to lock the LSA row, validate overlaps, and create the booking. **We close this transaction before calling the external mocked payment API.** If the API fails, we open a *new* atomic transaction to update the status to `CANCELLED`.

## Running Tests
Run the comprehensive test suite (13 tests) using `pytest`:
```bash
pytest tests/
```
