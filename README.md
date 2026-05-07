# Coupon Management & Redemption System - Mini Project

A high-performance mini project simulating a scalable coupon distribution and validation system, akin to Amazon or Flipkart checkouts.

## Tech Stack
*   **Framework**: FastAPI (Python) - Fast, built-in async support, automatic Swagger documentation.
*   **Database**: SQLite (via SQLAlchemy) - Lightweight, no setup required.
*   **Caching**: In-Memory Dictionary (simulating Redis in high-scale).

## File Structure
*   `database.py`: Maps the database connection engine.
*   `models.py`: Defines the relational SQLite tables (`Coupon`, `CouponUsage`).
*   `schemas.py`: Defines Data validation rules (Pydantic).
*   `main.py`: Contains the REST API endpoints, the cache layer, the validation rule engine, and background tasks.

## Setup Instructions
1. **Ensure you have Python 3.9+ installed.**
2. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## How to Test
FastAPI comes with a visually pleasing automated test dashboard.
1. Start the server (as shown above).
2. Open your browser and go to: `http://127.0.0.1:8000/docs`
3. Try out the `/coupon/create` API to create a coupon.
4. Try the `/coupon/apply` API passing the generated code, a cart value, user_id, and an order_id!

## Features Implemented (Code & Design)
*   ✅ **Coupon Validation**: Checks Expiry Date, Min Cart Value, Total Limits.
*   ✅ **Fraud Prevention**: DB check to prevent identical users from reusing limits on an order.
*   ✅ **Low Latency Architecture**: Employs an explicit In-Memory Cache tracking logic.
*   ✅ **Async Tracking**: Uses FastAPI `BackgroundTasks` to simulate Kafka-style async queue offloading dropping response time under 100ms.
*   ✅ **Enterprise System Design**: Full documentation and diagrams covering advanced distributed systems (CDN, WAF, Pub/Sub, Message Queues, DLQs, Read Replicas, and Data Warehousing).
