from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from datetime import datetime
import models, schemas
from database import engine, get_db

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Coupon Management System",
    description="A simple, scalable system for managing and applying e-commerce discount coupons.",
    version="1.0.0"
)

# ==========================================
# CACHE (In-Memory Simulation for Redis)
# ==========================================
# In a real system, this would be Redis. We use a Python dict to keep it simple.
# It stores coupon details to avoid hitting the DB for validation every time.
COUPON_CACHE = {}


# ==========================================
# BACKGROUND TASKS
# ==========================================
def record_coupon_usage_async(db: Session, coupon_code: str, user_id: str, order_id: str):
    """
    Async task to update database tables. 
    This allows the main checkout process to remain fast (<100ms) by not waiting for DB writes.
    """
    # 1. Get coupon from DB
    coupon = db.query(models.Coupon).filter(models.Coupon.code == coupon_code).first()
    if not coupon:
        return # Should not happen if validation passed, but safety check

    # 2. Record usage
    usage = models.CouponUsage(coupon_id=coupon.id, user_id=user_id, order_id=order_id)
    db.add(usage)

    # 3. Increment counter
    coupon.usage_count += 1
    db.commit()

    # 4. Update the Cache so the next validation knows about the new usage count
    COUPON_CACHE[coupon_code] = {
        "id": coupon.id,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "min_order_value": coupon.min_order_value,
        "max_discount": coupon.max_discount,
        "expiry_date": coupon.expiry_date,
        "usage_limit": coupon.usage_limit,
        "usage_count": coupon.usage_count,
    }


# ==========================================
# API ENDPOINTS
# ==========================================

@app.post("/coupon/create", response_model=schemas.CouponResponse)
def create_coupon(coupon: schemas.CouponCreate, db: Session = Depends(get_db)):
    """
    Admin Endpoint: Create a new coupon.
    """
    # Check if code already exists
    existing = db.query(models.Coupon).filter(models.Coupon.code == coupon.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists.")

    # Save to Database
    db_coupon = models.Coupon(**coupon.model_dump())
    db.add(db_coupon)
    db.commit()
    db.refresh(db_coupon)

    # Load into Cache immediately for fast future lookups
    COUPON_CACHE[db_coupon.code] = {
        "id": db_coupon.id,
        "discount_type": db_coupon.discount_type,
        "discount_value": db_coupon.discount_value,
        "min_order_value": db_coupon.min_order_value,
        "max_discount": db_coupon.max_discount,
        "expiry_date": db_coupon.expiry_date,
        "usage_limit": db_coupon.usage_limit,
        "usage_count": db_coupon.usage_count,
    }

    return db_coupon


@app.get("/coupon/{code}", response_model=schemas.CouponResponse)
def fetch_coupon_details(code: str, db: Session = Depends(get_db)):
    """
    Fetch coupon details. Tries cache first, then falls back to DB.
    """
    # 1. Cache hit?
    if code in COUPON_CACHE:
        # Construct response from cache to save DB query
        cached_data = COUPON_CACHE[code]
        # Note: in real-world you might want to fetch exact usage count from DB if high consistency is strictly needed
        # but serving from cache is faster.
        coupon = db.query(models.Coupon).filter(models.Coupon.code == code).first()
        if coupon:
             return coupon

    # 2. Database Fallback (Cache miss)
    coupon = db.query(models.Coupon).filter(models.Coupon.code == code).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    
    return coupon


@app.post("/coupon/validate")
def validate_coupon(req: schemas.CouponValidateRequest, db: Session = Depends(get_db)):
    """
    Validates if a user can use the coupon for the current cart value.
    """
    # Fetch from Cache primarily for high speed
    coupon_data = COUPON_CACHE.get(req.code)

    # Cache Miss -> Fetch from DB and populate cache
    if not coupon_data:
        coupon = db.query(models.Coupon).filter(models.Coupon.code == req.code).first()
        if not coupon:
            raise HTTPException(status_code=404, detail="Invalid coupon code.")
        
        coupon_data = {
            "id": coupon.id,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "min_order_value": coupon.min_order_value,
            "max_discount": coupon.max_discount,
            "expiry_date": coupon.expiry_date,
            "usage_limit": coupon.usage_limit,
            "usage_count": coupon.usage_count,
        }
        COUPON_CACHE[req.code] = coupon_data

    # Rule Engine: Checks
    # 1. Expiry Check
    if datetime.utcnow() > coupon_data["expiry_date"]:
        raise HTTPException(status_code=400, detail="Coupon has expired.")

    # 2. Global Usage Limit Check
    if coupon_data["usage_count"] >= coupon_data["usage_limit"]:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached.")

    # 3. Minimum Order Value Check
    if req.cart_value < coupon_data["min_order_value"]:
        raise HTTPException(status_code=400, detail=f"Minimum order value of {coupon_data['min_order_value']} required.")

    # 4. User-Specific Abuse / Duplicate Check
    # (Since this requires checking historical exact orders, we *do* hit the DB here for security)
    used_already = db.query(models.CouponUsage).filter(
        models.CouponUsage.coupon_id == coupon_data["id"],
        models.CouponUsage.user_id == req.user_id
    ).first()
    
    if used_already:
         raise HTTPException(status_code=400, detail="You have already used this coupon.")

    return {"valid": True, "message": "Coupon is valid and ready to apply."}


@app.post("/coupon/apply", response_model=schemas.CouponApplyResponse)
def apply_discount(req: schemas.CouponApplyRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Applies the discount to the cart and triggers async usage tracking. 
    """
    # 1. Re-validate to ensure state is still good
    validate_coupon(schemas.CouponValidateRequest(
        code=req.code, user_id=req.user_id, cart_value=req.cart_value
    ), db)

    # 2. Perform Discount Calculation
    coupon_data = COUPON_CACHE[req.code]
    discount_amount = 0.0

    if coupon_data["discount_type"] == "flat":
        discount_amount = coupon_data["discount_value"]
    elif coupon_data["discount_type"] == "percentage":
        discount_amount = (coupon_data["discount_value"] / 100.0) * req.cart_value
        # Cap the discount if maximum exists
        if coupon_data["max_discount"] and discount_amount > coupon_data["max_discount"]:
            discount_amount = coupon_data["max_discount"]

    # Safety constraint: discount can't be more than cart order value
    if discount_amount > req.cart_value:
        discount_amount = req.cart_value

    final_cart_value = round(req.cart_value - discount_amount, 2)

    # 3. Trigger asynchronous Database updates (Do not block the fast checkout response)
    # This handles "Tracking per-user and global usage count"
    background_tasks.add_task(record_coupon_usage_async, db, req.code, req.user_id, req.order_id)

    return schemas.CouponApplyResponse(
        success=True,
        message="Discount applied successfully.",
        original_cart_value=req.cart_value,
        discount_applied=round(discount_amount, 2),
        final_cart_value=final_cart_value
    )
