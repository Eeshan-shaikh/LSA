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
* Key challenges: Preventing double-bookings, preventing N+1 query inefficiencies, and mock external service integration.

---
## Slide 3: Technology Stack & Architecture
* **Framework**: Django & Django REST Framework (DRF)
* **Database**: SQLite (via Django ORM)
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
* **Functionality**: Filter LSAs by skill using query parameters (e.g., `?skill=Math`).
* Returns nested JSON containing LSA details and their associated skills.

---
## Slide 7: Solving the N+1 Query Problem
* **The Problem**: Querying `N` LSAs and accessing their skills typically triggers `N+1` database queries, causing severe performance issues at scale.
* **The Solution**: Used Django's `prefetch_related('skills')`.
* This optimizes the operation to exactly 2 database queries: one for all LSAs, and one for all related skills across those LSAs.

---
## Slide 8: Booking API Flow
* **Endpoint**: `POST /api/v1/bookings/`
* Receives parent ID, LSA ID, start time, and end time.
* Step 1: Validate payload format.
* Step 2: Validate temporal logic (start_time < end_time).
* Step 3: Check for overlaps to prevent double-booking.

---
## Slide 9: Double-Booking Prevention Logic
* Query the database for existing bookings for the requested LSA.
* Check if any existing booking overlaps with the requested time window:
  `start_time < requested_end_time` AND `end_time > requested_start_time`
* Returns HTTP 400 Bad Request if an overlap is found.

---
## Slide 10: External Service Integration
* Simulates payment/verification via the `requests` library.
* Code implements a simulated POST request to `httpbin.org`.
* **Exception Handling**: Uses `try/except requests.exceptions.RequestException` to catch timeouts or connection errors and gracefully fail the booking.

---
## Slide 11: Asynchronous Webhook
* **Endpoint**: `POST /api/v1/payments/webhook/`
* Allows the mocked external service to asynchronously notify the system of payment success/failure.
* Automatically updates both the Payment status and the Booking status.

---
## Slide 12: Automated Testing Strategy
* Used `pytest` with `pytest-django`.
* Replaced standard DB with in-memory test DB.
* Used `unittest.mock.patch` to mock external API calls during testing.

---
## Slide 13: Test Coverage
* ✅ **Valid Booking**: Ensures 201 Created and correct state.
* ❌ **Invalid Booking**: Rejects end_time before start_time.
* ❌ **Overlapping Booking**: Successfully catches double-booking attempts.
* ✅ **LSA Search**: Verifies query counts (N+1 fixed) using `django_assert_num_queries`.
* ❌ **External Failure**: Tests simulated network timeouts resulting in HTTP 502.

---
## Slide 14: Continuous Integration (CI/CD)
* Configured GitHub Actions.
* `.github/workflows/tests.yml` triggers on every push/pull_request to main.
* Automatically sets up Python, installs dependencies, and runs the `pytest` suite to ensure code quality.

---
## Slide 15: Conclusion & Demo
* System fulfills all assignment requirements securely and efficiently.
* Code is modular, well-tested, and ready for deployment.
* [Live Demo / Q&A]
---
