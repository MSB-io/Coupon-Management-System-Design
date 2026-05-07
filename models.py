from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    discount_type = Column(String, nullable=False) # "flat" or "percentage"
    discount_value = Column(Float, nullable=False)
    min_order_value = Column(Float, default=0.0)
    max_discount = Column(Float, nullable=True) # Used if discount_type is percentage
    expiry_date = Column(DateTime, nullable=False)
    usage_limit = Column(Integer, default=1) # Limit per user or globally depending on rules
    usage_count = Column(Integer, default=0) # Track total number of times this coupon was used
    created_at = Column(DateTime, default=datetime.utcnow)

    usages = relationship("CouponUsage", back_populates="coupon")

class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"))
    user_id = Column(String, index=True) # String user ID for simplicity
    order_id = Column(String, unique=True, index=True)
    used_at = Column(DateTime, default=datetime.utcnow)

    coupon = relationship("Coupon", back_populates="usages")
