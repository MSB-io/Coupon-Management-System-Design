# System Architecture & Diagrams

Below are the highly detailed architectural representations of the Coupon Management & Redemption System, specifically incorporating advanced distributed system patterns such as Message Queues and Pub/Sub caching mechanisms.

## 1. High-Level Design (HLD) Architecture
This diagram illustrates how the system scales horizontally and uses asynchronous messaging (Queues) and Pub/Sub for eventual consistency and fast read synchronization.

```mermaid
graph TD
    %% Define Client Layer
    subgraph Client Layer
        Web[Web Browser]
        Mobile[Mobile App]
    end

    %% Define Gateway Layer
    subgraph Edge Layer
        WAF[Web Application Firewall]
        APIGW[API Gateway / Load Balancer]
    end

    %% Define Service Layer
    subgraph Microservices Layer
        AdminSvc[Admin Coupon Service]
        CouponSvc1[Coupon Validation Service - Instance 1]
        CouponSvc2[Coupon Validation Service - Instance ...N]
        OrderSvc[Order / Checkout Service]
    end

    %% Define Event/Messaging Layer
    subgraph Event and Messaging Layer
        PubSub((Redis Pub/Sub<br>Cache Sync Topic))
        MsgQueue[[Message Queue<br>Kafka / RabbitMQ<br>Topic: CouponUsageEvent]]
    end

    %% Define Worker Layer
    subgraph Worker Layer
        UsageWorker1[Usage Tracking Worker]
        UsageWorker2[Usage Tracking Worker]
    end

    %% Define Data Layer
    subgraph Data Layer
        Cache[(Distributed Cache<br>Redis Cluster)]
        DB[(Relational DB<br>PostgreSQL / MySQL)]
        ReadReplica[(DB Read Replica)]
    end

    %% Connections
    Web & Mobile --> WAF
    WAF --> APIGW
    
    %% Admin Flow (Pub/Sub)
    APIGW -->|POST /create| AdminSvc
    AdminSvc -->|1. Write| DB
    AdminSvc -->|2. Publish Update| PubSub
    PubSub -.->|3. Broadcast Invalidation| CouponSvc1 & CouponSvc2
    
    %% Checkout Flow (Queue)
    APIGW -->|POST /apply| CouponSvc1
    CouponSvc1 <-->|Read| Cache
    Cache -.->|Cache Miss| ReadReplica
    
    CouponSvc1 -->|Validate & Apply| OrderSvc
    CouponSvc1 -->|Async Publish Event| MsgQueue
    
    %% Worker Flow
    MsgQueue ==>|Consume| UsageWorker1 & UsageWorker2
    UsageWorker1 -->|Batch Insert/Update| DB
    DB -.->|Replication| ReadReplica
```

## 2. Low-Level Design (LLD): Component & Data Flow
This details the internal classes, methods, and rule engine logic inside the Validation Service, including how payloads are structured and pushed to the queue.

```mermaid
classDiagram
    class CouponController {
        +validate_coupon(req: ValidateReq)
        +apply_discount(req: ApplyReq)
    }
    
    class RuleEngine {
        +check_expiry(expiry_date)
        +check_cart_minimum(cart_val, min_val)
        +calculate_discount(type, val, max)
    }
    
    class CacheManager {
        +get_coupon(code)
        +set_coupon(code, data)
        +listen_invalidation_events()
    }
    
    class FraudPreventionService {
        +check_user_limits(user_id, coupon_id)
        +check_device_fingerprint(req_headers)
    }
    
    class MessageProducer {
        +publish_usage_event(payload: JSON)
    }

    CouponController --> RuleEngine : Uses
    CouponController --> CacheManager : Calls
    CouponController --> FraudPreventionService : Calls
    CouponController --> MessageProducer : Triggers

    %% Queue Payload Structure
    class UsageEventPayload {
        <<Queue Message>>
        +String event_id
        +String coupon_code
        +String user_id
        +String order_id
        +Timestamp timestamp
    }
    
    MessageProducer ..> UsageEventPayload : Produces
```

## 3. Detailed Sequence Diagram (Pub/Sub & Queues)
This sequence shows the exact lifecycle of an Admin updating a coupon (Pub/Sub) and a User applying a coupon (Message Queue).

```mermaid
sequenceDiagram
    autonumber
    actor Admin
    actor User
    participant Gateway as API Gateway
    participant ValidationSvc as Coupon Service
    participant Redis as Redis (Cache + PubSub)
    participant Queue as Kafka / RabbitMQ
    participant DB as Database
    participant Worker as DB Worker

    %% PUB/SUB Flow
    Note over Admin, Redis: Pub/Sub Flow: Admin updates a coupon
    Admin->>Gateway: PUT /coupon/SAVE50 (Update Limit)
    Gateway->>ValidationSvc: Route Request
    ValidationSvc->>DB: Update coupon limit in DB
    ValidationSvc->>Redis: Publish "INVALIDATE_SAVE50" to Topic
    Redis-->>ValidationSvc: (All Instances) Drop local cache for SAVE50

    %% QUEUE Flow
    Note over User, Worker: Queue Flow: High-traffic flash sale checkout
    User->>Gateway: POST /coupon/apply (Code: SAVE50)
    Gateway->>ValidationSvc: Route Request
    
    ValidationSvc->>Redis: Fetch SAVE50 Rules
    Redis-->>ValidationSvc: Rules (Hit)
    
    ValidationSvc->>ValidationSvc: RuleEngine: Validate Expiry & Min Value
    ValidationSvc->>DB: Fraud Check (Has user_id used this?)
    DB-->>ValidationSvc: Valid
    
    ValidationSvc->>ValidationSvc: RuleEngine: Calculate final cart value (-$50)
    
    %% Async decoupling
    ValidationSvc->>Queue: Publish Event {code: SAVE50, user: 123, order: 999}
    ValidationSvc-->>Gateway: 200 OK (Calculated total)
    Gateway-->>User: Show Discounted UI Immediately (< 50ms)
    
    %% Eventual Consistency Worker
    Queue-->>Worker: Consume Event
    Worker->>DB: Insert into CouponUsage table
    Worker->>DB: Increment Coupon global usage_count
    Worker->>Redis: Update global usage counter in Cache
```
