# System Architecture & Diagrams

Below are the architectural representations of the Coupon Management & Redemption System.

## 1. High-Level Architecture Diagram
This diagram shows the main components of the system and how they interact.

```mermaid
graph TD
    Client[Client Device / Web / Mobile App]
    LoadBalancer[API Gateway / Load Balancer]
    FastAPI[Coupon Service - FastAPI]
    Cache[(In-Memory Cache / Redis)]
    DB[(SQLite Database)]
    OrderSvc[Order Service / Payment]

    Client -->|Applies Coupon| LoadBalancer
    LoadBalancer -->|POST /coupon/apply| FastAPI
    
    FastAPI .->|1. Lookup Data| Cache
    Cache .->|Cache Miss| DB
    
    FastAPI <-->|2. Validate Rules Engine| FastAPI
    FastAPI -->|3. Async Usage Tracking| DB
    FastAPI -->|4. Return Discounted Price| Client
    Client -->|Complete Payment| OrderSvc
```

## 2. Sequence Flow Diagram
This details the exact step-by-step transaction when a user applies a discount during checkout.

```mermaid
sequenceDiagram
    actor User
    participant Client
    participant CouponAPI as Coupon Service
    participant Cache as Redis/Cache
    participant Database as Database
    participant BackgroundTask as Async Worker

    User->>Client: Enters code: "SAVE50"
    Client->>CouponAPI: POST /coupon/apply (code, user_id, cart_value, order_id)
    
    CouponAPI->>Cache: Get coupon rules
    alt Cache Miss
        CouponAPI->>Database: Fetch coupon
        Database-->>CouponAPI: Return coupon rules
        CouponAPI->>Cache: Store for next time
    else Cache Hit
        Cache-->>CouponAPI: Return coupon rules
    end
    
    CouponAPI->>CouponAPI: Validate: Expiry? User Usage Limit? Cart Value?
    
    CouponAPI->>Database: Check if user already used code? (Fraud Prevention)
    Database-->>CouponAPI: Valid / No prior use
    
    CouponAPI->>CouponAPI: Calculate final discount amount
    
    CouponAPI-->>Client: 200 OK (Calculated final cart value)
    
    %% Async task happens without blocking the user checkout
    CouponAPI-)BackgroundTask: Record usage asynchronously
    BackgroundTask->>Database: Insert into CouponUsage
    BackgroundTask->>Database: Increment total usage_count
    BackgroundTask->>Cache: Update Cache Usage count
```
