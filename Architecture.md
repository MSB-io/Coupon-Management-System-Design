# System Architecture & Diagrams

Below are the highly detailed architectural representations of the Coupon Management & Redemption System, specifically incorporating advanced distributed system patterns such as Message Queues and Pub/Sub caching mechanisms.

## 1. High-Level Design (HLD) Architecture
This diagram illustrates an enterprise-grade, highly scalable distributed system. It includes aggressive edge-caching, rate limiting, independent scaling of reads vs writes, dead letter queues for fault tolerance, and data warehousing for analytics.

```mermaid
graph TD
    %% 1. Client & Edge Layer
    subgraph Client and Edge Layer
        App[Mobile / Web Client]
        CDN[CDN - Edge Caching / Static Assets]
        WAF[Web Application Firewall - Block Malicious IPs]
        APIGW[API Gateway - Load Balancer & Routing]
        RL[Rate Limiter - Prevent Brute Force Attacks]
    end

    %% 2. Microservices Layer
    subgraph Microservices Layer
        AuthSvc[Auth & Fraud Service]
        AdminSvc[Admin Rules Service]
        CouponSvc[Validation Service - Auto-Scaling Cluster]
        OrderSvc[Checkout / Order Service]
    end

    %% 3. Distributed Cache Layer
    subgraph High-Speed Cache Layer
        RedisPrimary[(Redis Primary - Writes)]
        RedisReplica[(Redis Replica - Reads)]
    end

    %% 4. Event Streaming & Queues
    subgraph Async Event and Messaging Layer
        PubSub[[Redis Pub/Sub - Cache Sync]]
        KafkaUsage[[Kafka Topic - UsageEvents]]
        DLQ[[Dead Letter Queue - Failed Events]]
    end

    %% 5. Worker Layer
    subgraph Background Workers
        UsageWorker[DB Insertion Worker]
        AlertWorker[Fraud Detection Alert Worker]
    end

    %% 6. Persistence & Analytics Layer
    subgraph Database and Storage Layer
        DBPrimary[(PostgreSQL Primary<br/>ACID Writes)]
        DBReplica[(PostgreSQL Read Replica)]
        DataWarehouse[(Analytics DB<br/>Tableau / Snowflake)]
    end

    %% Connections - Edge
    App --> CDN
    CDN --> WAF
    WAF --> APIGW
    APIGW --> RL

    %% Connections - Routing
    RL -->|POST /create| AdminSvc
    RL -->|POST /apply| CouponSvc

    %% Connections - Admin Write Flow
    AdminSvc -->|1. Save New Rule| DBPrimary
    AdminSvc -->|2. Invalidate Cache| PubSub
    PubSub -.->|3. Synchronize| RedisPrimary
    RedisPrimary ===|Replication| RedisReplica

    %% Connections - Validation Read Flow
    CouponSvc -->|1. Verify User/Device| AuthSvc
    CouponSvc -->|2. Fetch Rules < 5ms| RedisReplica
    RedisReplica -.->|3. Fallback on Miss| DBReplica
    CouponSvc -->|4. Next Step| OrderSvc

    %% Connections - Async Tracking (Queue)
    CouponSvc -->|5. Fire & Forget| KafkaUsage
    KafkaUsage ==>|Consume| UsageWorker
    KafkaUsage ==>|Consume| AlertWorker
    
    %% Worker to DB
    UsageWorker -->|Batch Commit| DBPrimary
    UsageWorker -.-x|Error / Retry Fail| DLQ
    DBPrimary ===|Replication| DBReplica
    
    %% Analytics
    DBReplica -.->|Nightly ETL Data Dump| DataWarehouse
```

## 2. Low-Level Design (LLD): Component & Data Flow
This details the internal classes, methods, and rule engine logic inside the Validation Service, including how payloads are structured and pushed to the queue, as well as external interfaces for Fraud.

```mermaid
classDiagram
    %% Core Controllers and Engines
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
    
    %% External Service Adapters
    class FraudPreventionService {
        <<Gateway Component>>
        +check_user_limits(user_id, coupon_id)
        +call_auth_service(fingerprint)
    }
    
    class MessageProducer {
        <<Message Broker>>
        +publish_usage_event(payload: JSON)
        +route_to_dlq(payload, error_reason)
    }

    CouponController --> RuleEngine : Uses
    CouponController --> CacheManager : Calls
    CouponController --> FraudPreventionService : Calls
    CouponController --> MessageProducer : Triggers

    %% Queue Payload Structure
    class UsageEventPayload {
        <<Kafka Message>>
        +String event_id
        +String coupon_code
        +String user_id
        +String order_id
        +Timestamp timestamp
    }
    
    MessageProducer ..> UsageEventPayload : Produces
```

## 3. Detailed Sequence Diagram (Edge Security & Queues)
This sequence shows the exact lifecycle of an Admin updating a coupon (Pub/Sub) and a User applying a coupon through Edge security.

```mermaid
sequenceDiagram
    autonumber
    actor Admin
    actor User
    participant Edge as WAF & Rate Limiter
    participant Gateway as API Gateway
    participant ValidationSvc as Coupon Service
    participant AuthSvc as Auth & Fraud Svc
    participant Redis as Redis (Cache + PubSub)
    participant Queue as Kafka Topic
    participant DB as Postgres DB
    participant DLQ as Dead Letter Queue
    participant Worker as DB Worker

    %% PUB/SUB Flow
    Note over Admin, Redis: Pub/Sub Flow: Admin updates a coupon
    Admin->>Gateway: PUT /coupon/SAVE50 (Update Limit)
    Gateway->>ValidationSvc: Route Request
    ValidationSvc->>DB: Update coupon limit in DB
    ValidationSvc->>Redis: Publish "INVALIDATE_SAVE50" to Topic
    Redis-->>ValidationSvc: Drop local cache for SAVE50

    %% QUEUE Flow
    Note over User, Worker: Queue Flow: High-traffic flash sale checkout
    User->>Edge: POST /coupon/apply (Code: SAVE50)
    Edge->>Edge: Security Check (Pass)
    Edge->>Gateway: Route Request
    Gateway->>ValidationSvc: Forward
    
    %% Fraud Check
    ValidationSvc->>AuthSvc: Verify Session & Fingerprint
    AuthSvc-->>ValidationSvc: 200 OK (Trusted)

    %% Fetch & Rules
    ValidationSvc->>Redis: Fetch SAVE50 Rules
    Redis-->>ValidationSvc: Rules (Hit)
    
    ValidationSvc->>ValidationSvc: RuleEngine: Validate Expiry & Limits
    ValidationSvc->>ValidationSvc: RuleEngine: Calculate final cart value (-$50)
    
    %% Async decoupling
    ValidationSvc->>Queue: Publish Event {code: SAVE50, user: 123}
    ValidationSvc-->>Gateway: 200 OK (Calculated total)
    Gateway-->>Edge: 200 OK
    Edge-->>User: Show Discounted UI Immediately (< 50ms)
    
    %% Eventual Consistency Worker
    Queue-->>Worker: Consume Event
    alt Process Succeeds
        Worker->>DB: Insert into CouponUsage table
        Worker->>DB: Increment Global usage_count
    else DB Down / Constrain Error
        Worker-xDB: Insert Fails (Timeout / Transaction Error)
        Worker->>Worker: Retry 3 times
        Worker->>DLQ: Send to Dead Letter Queue for Manual Review
    end
```
