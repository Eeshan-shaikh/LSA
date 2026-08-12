# LSA Booking System - Presentation Slides

---
## Slide 1: Title
* Title: LSA Booking Backend System
* Subtitle: Architecture, API Design, and Implementation
* Name/Date

---
## Slide 2: The Problem
* Need a robust backend to book Learning Support Assistants (LSAs).
* Core requirements: Database models, API for searching, API for booking.
* Key challenges: Preventing double-bookings safely, eliminating N+1 queries, and integrating external services.

---
## Slide 3: Technology Stack & Architecture
* **Framework**: Django & Django REST Framework (DRF)
* **Database**: SQLite (Prototype) -> PostgreSQL (Production Target)
* **Testing**: pytest & pytest-django
* **External Integration**: Python `requests` library

---
## Slide 4: Django MVT Architecture
* **Models**: Define the data structure (Parent, LSA, Booking, Payment).
* **Views**: Handle business logic and API request processing.
* **"Templates"**: In an API context, DRF Serializers act as the presentation layer, transforming model instances into JSON.
* Chosen over Flask MVC for its "batteries-included" ORM and rapid API development capabilities.

---
## Slide 5: Database Schema
* **Parent**: Represents the user making the booking.
* **Skill**: Represents individual LSA qualifications.
* **LSA_Profile**: Has a ManyToMany relationship with `Skill`.
* **Booking_Request**: Links Parent & LSA with `start_time` and `end_time`.
* **Payment**: OneToOne relationship with `Booking_Request`.

---
## Slide 6: LSA Search API Design
* **Endpoint**: `GET /api/v1/lsas/search/`
* **Functionality**: Filter LSAs by skill AND availability (using `start_time` and `end_time`).
* Returns nested JSON containing available LSA details and their associated skills.

---
## Slide 7: Solving the N+1 Query Problem
* **The Problem**: Querying `N` LSAs and accessing their skills typically triggers `N+1` database queries, causing severe performance issues.
* **The Solution**: Used Django's `prefetch_related('skills')`.
* This optimizes the operation to exactly 2 database queries: one for all LSAs, and one for all related skills across those LSAs.

---
## Slide 8: Booking API Flow
* **Endpoint**: `POST /api/v1/bookings/`
* Receives parent ID, LSA ID, start time, and end time.
* Step 1: Validate payload format (e.g., start_time < end_time).
* Step 2: Open Atomic DB Transaction.
* Step 3: Lock LSA row & check for overlaps to prevent double-booking.
* Step 4: Save Pending Booking.
* Step 5: Close Transaction (Release locks) -> Call External API.

---
## Slide 9: Concurrency and Double-Booking Prevention
* Implemented `select_for_update()` inside `transaction.atomic()`.
* This grabs a database-level write lock on the specific LSA row being booked.
* Concurrent requests attempting to book the same LSA will queue sequentially, perfectly avoiding race conditions.

---
## Slide 10: External Service Integration (Network I/O)
* Simulates payment/verification via the `requests` library to `httpbin.org`.
* **Crucial Design Choice**: The external HTTP call is executed *outside* the initial database transaction. 
* This ensures the database doesn't hang holding locks if the network call times out (e.g., waiting 10 seconds).

---
## Slide 11: Asynchronous Webhook Hardening
* **Endpoint**: `POST /api/v1/payments/webhook/`
* Allows the mocked external service to asynchronously notify the system of payment success/failure.
* **Security**: Enforces mock header signature verification (`X-Webhook-Signature`).
* **Resilience**: Implements payload validation and idempotency (safely ignores duplicate success calls).

---
## Slide 12: Automated Testing Strategy
* Comprehensive suite written with `pytest` and `pytest-django`.
* Uses `unittest.mock.patch` to isolate external API calls.
* Focuses on boundary conditions, missing fields, and failure states, not just the happy path.

---
## Slide 13: Test Coverage Breakdown (13 Tests)
* ✅ **Validations**: Missing fields, bad IDs, end_time < start_time.
* ❌ **Overlap**: Catching double-booking attempts.
* ✅ **Search**: Query count verifications (N+1 fixed) & empty results logic.
* ❌ **External Failure**: Tests simulated network timeouts resulting in HTTP 502.
* 🛡️ **Webhook**: Success, Failure, Invalid payloads, Bad signatures, and Idempotency logic.

---
## Slide 14: Continuous Integration (CI/CD)
* Configured GitHub Actions (`.github/workflows/tests.yml`).
* Automatically runs `pip install -r requirements.txt`.
* Triggers on every push to `main`.
* Ensures tests pass before code can be considered integrated.

---
## Slide 15: Conclusion & Status
* **Status**: The prototype implements the requested booking, LSA search, payment, webhook, testing and CI workflows.
* **Production Hardening**: Identified and addressed areas around concurrency (DB locks), webhook security (signatures/idempotency), and deployment configuration (environment variables).
* [Live Demo / Q&A]
---
