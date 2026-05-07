# Coupon Management & Redemption System - Mini Project

A high-performance system design implementation demonstrating a scalable, highly-available coupon distribution and validation engine. Modeled after actual e-commerce giants (Amazon, Flipkart), this system solves for high concurrency, duplicate usage prevention, transactional consistency, and sub-100ms checkout validations during flash sales.

---

## Technology Stack
### Core Technologies
*   **Backend Framework**: **FastAPI** (Python) 
    * *Why?* Unmatched async performance via ASGI, extreme type safety via Pydantic, and automatic Swagger/Redoc UI generation.
*   **Database**: **SQLite** (Managed via **SQLAlchemy ORM**)
    * *Why?* A localized, self-contained relational DB that allows testing complex ACID schema relationships without deployment overhead.
*   **Data Validation**: **Pydantic V2** 
    * *Why?* Enforces strict type casting at the API boundary, guaranteeing bad payloads hit 422 Unprocessable Entity *before* touching business logic.
### Advanced Concepts Simulated
*   **Redis Pub/Sub & Cache**: Coded via explicit In-Memory Dictionaries.
*   **Kafka / RabbitMQ (Queues)**: Coded via localized `BackgroundTasks` threads, allowing the main checkout API to return immediately while database insertion resolves asynchronously.

---

## Project Structure & Design Documents

### Source Code
*   `main.py`: Houses the API Gateway imitation, validation endpoints, Rule Engines, in-memory caching logic, and Async Workers.
*   `models.py`: Declarative structural tables for `Coupon` (Stores Admin rules) and `CouponUsage` (Acts as the historical ledger preventing duplicate fraud).
*   `schemas.py`: Pydantic object schemas governing JSON requests (`CouponValidateRequest`, `CouponApplyResponse`).
*   `database.py`: SQLAlchemy session factories and thread pool connections.

### Design Documents (DO NOT SKIP)
Make sure to read the comprehensive enterprise system design outlines included in this repository:
1. **[Architecture.md](Architecture.md)**: Contains robust Mermaid.js diagrams for our **High-Level Design (WAF, CDN, Kafka, Dead Letter Queues)**, **Low Level Design (Classes, Event Payloads)**, and **Sequence Diagrams**.
2. **[Documentation.md](Documentation.md)**: Directly defends architectural choices involving Consistency vs Availability, caching mechanisms, idempotency in payments, and the necessity of Pub/Sub and Message Brokers in modern scale.

---

## Installation & Setup Instructions

To avoid PEP-668 global installation conflicts (especially on macOS/Homebrew), this project firmly relies on isolated Virtual Environments.

1. **Verify Python Installation (Requires 3.9+)**
   ```bash
   python3 --version
   ```
2. **Create and Activate a Virtual Environment**
   ```bash
   python3 -m venv venv
   
   # Mac / Linux
   source venv/bin/activate  
   
   # Windows
   venv\Scripts\activate
   ```
3. **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
4. **Boot the Application Server**
    ```bash
    uvicorn main:app --reload
    ```
    *The server will boot locally on `http://127.0.0.1:8000`*

---

## Testing the APIs (No Frontend Required)

Because this utilizes FastAPI, interactive testing is automatically generated out of the box.

1. Open your web browser and navigate to: **`http://127.0.0.1:8000/docs`**
2. **Admin Flow (Create Coupon)**
   * Expand the `POST /coupon/create` boundary.
   * Click **Try it out** and use a payload like `{"code": "FLASHSALE", "discount_type": "flat", "discount_value": 50, "expiry_date": "2030-12-31T00:00:00Z", "usage_limit": 10}`.
3. **Checkout Flow (Apply Coupon)**
   * Expand the `POST /coupon/apply` boundary.
   * Click **Try it out** and pass `"code": "FLASHSALE", "user_id": "U1", "cart_value": 200, "order_id": "ORD1"`.
   * **Test Fraud limits**: Run the exact same payload again. The system will successfully block the transaction with HTTP 400 because `U1` has already used `FLASHSALE`.

---

## Core Features Delivered
*   **Fraud Prevention**: Prevents per-user duplicate redemption via historical DB ledger lookups.
*   **Ultra-Low Latency Validation**: Offloads read operations to an explicit Cache Manager, completely shielding the database from peak traffic.
*   **Asynchronous Event Tracking**: Returns a discounted cart total instantly `< 100ms`, while silently writing usage data into background queues/threads.
*   **Complex Rule Engines**: Enforces rules for Expiry timestamps, minimum cart value thresholds, and absolute total usage caps globally versus individually.
