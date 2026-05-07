from pydantic import BaseModel, conint
from typing import Optional
from datetime import datetime

# ====================
# Coupon Schemas
# ====================

class CouponBase(BaseModel):
    code: str
    discount_type: str # "flat" or "percentage"
    discount_value: float
    min_order_value: float = 0.0
    max_discount: Optional[float] = None
    expiry_date: datetime
    usage_limit: int = 1

class CouponCreate(CouponBase):
    pass

class CouponResponse(CouponBase):
    id: int
    usage_count: int
    created_at: datetime

    class Config:
        from_attributes = True

# ====================
# Validation & Application Schemas
# ====================

class CouponValidateRequest(BaseModel):
    code: str
    user_id: str
    cart_value: float

class CouponApplyRequest(CouponValidateRequest):
    order_id: str

class CouponApplyResponse(BaseModel):
    success: bool
    message: str
    original_cart_value: float
    discount_applied: float
    final_cart_value: float
