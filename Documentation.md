# System Design Documentation & Justifications
**Project:** Coupon Management & Redemption System

## Objective Fulfillment
This project demonstrates a scalable Coupon Management System handling real-time validation, discount calculations, usage tracking, and fraud prevention boundaries. By using FastAPI, SQLite, and simulated Redis caching, we model exactly how e-commerce giants validate extreme traffic during flash sales while maintaining transactional safety.

---

## Technical Explanations (As Required)

### 1. Why caching is important (Reduces DB Load during Peak Traffic)
During an event like a "Flash Sale," millions of users might try to apply the same coupon code simultaneously. If every `/apply` request directly queried the relational database to fetch the coupon rules (expiry, discount percentage), the database CPU and Connections would max out immediately, causing system-wide timeouts. By bringing this read-heavy operation to an In-Memory Cache (or Redis in production), the service can return the coupon rules in sub-milliseconds without touching the database, effectively shielding the primary DB from read crashes.

### 2. Why validation must be fast (Checkout UX)
Coupon validation happens at the most critical stage of user flow: **Checkout**. If applying a coupon takes 3 seconds, a significant percentage of users will abandon their carts, leading to a direct loss in company revenue. Validation must be `<100ms`, which translates to an instant UI update on the front-end, reassuring the customer's intent to pay.

### 3. Trade-off between Strong Consistency vs Availability
*   **Strong Consistency:** If we strictly locked the database to ensure a coupon with `usage_limit = 1000` is never used 1001 times, it would create extreme bottlenecks at the database layer (Row locking / Transactions wait times). 
*   **High Availability:** We favor Availability. By checking cache limits and using asynchronous tracking, we ensure the checkout system is *always* up and always responds instantly. The trade-off is eventual consistency: it might mean coupon 1000 and 1001 are processed concurrently before the DB lock triggers. For e-commerce companies, processing that one extra sale (Availability) is often worth slightly exceeding a global limit.

### 4. Why idempotency is required in payment + coupon usage
Idempotency ensures that if a user clicks the "Apply Coupon" button 5 times quickly, or if the network disconnects and retries the request automatically, the discount is only applied once, and the `CouponUsage` is only recorded once. We establish idempotency by binding the application to a unique `order_id`. If `order_id` X applies Coupon Y, a second retry with `order_id` X will be caught gracefully.

### 5. Why async logging (Message Queues) improves performance & reliability
Updating the database to record that "User X used Coupon Y" requires establishing a DB connection, executing an `INSERT/UPDATE`, locking rows to increment counters, and committing the transaction. Doing this synchronously adds latency and creates a single point of failure.

By utilizing **Message Queues** (like Kafka), the Validation Service instantly calculates the discount, pushes a lightweight JSON event to the `UsageEvents` topic, and returns `200 OK` to the user in <50ms. 
*   **Scale**: Background workers consume these events at their own pace, batching database inserts during flash sales to prevent DB Connection Exhaustion.
*   **Fault Tolerance (DLQ)**: If the DB crashes, the messages safely wait in the queue. If an event repeatedly fails processing, it is routed to a **Dead Letter Queue (DLQ)** for manual engineering review, ensuring zero data loss.

### 6. Why use Pub/Sub for Cache Invalidation?
When an admin updates a coupon (e.g., changing expiry or reducing stock), those changes must immediately reflect across all active instances worldwide to prevent overselling. 
Using a **Pub/Sub** model (e.g., Redis Pub/Sub), the Admin Service publishes a `CouponUpdated` event. Every validation server/Redis Replica subscribed to this topic instantly invalidates or updates its cached version. This ensures high availability (fetching from cache) without suffering from stale data, establishing immediate eventual consistency.

### 7. The importance of Edge Security (WAF & Rate Limiting)
Attackers frequently use automated bots to test random dictionary combinations (e.g., `SAVE10`, `SAVE11`) to discover hidden discount codes. 
*   **Web Application Firewall (WAF)** blocks known malicious IPs at the edge.
*   **Rate Limiting** tracking prevents any single user token or IP from submitting more than 5 coupon attempts per minute, explicitly stopping brute-force guessing and shielding upstream microservices.

### 8. Data Warehousing for Analytics
Production databases must handle live, transactional user traffic (OLTP). Business stakeholders asking, *"What were the demographics of users who used SUMMER50?"*, run heavy, complex `JOIN` queries. To prevent these queries from crashing the checkout system, we perform a Nightly ETL (Extract, Transform, Load) dump of our Relational DB into a **Data Warehouse** (OLAP) like Snowflake or Redshift. Business Intelligence tools (Tableau) run safely against this separated analytical environment.

---

## Endpoints Summary (LLD)
1. **POST `/coupon/create`**: Admin inputs discount type, expiry. (Data cached immediately).
2. **GET `/coupon/{code}`**: Fetches details (hits cache primarily).
3. **POST `/coupon/validate`**: Validates the code against cart amount and user eligibility.
4. **POST `/coupon/apply`**: Validates, calculates math, and triggers async tracking task.
