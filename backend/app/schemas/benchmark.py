"""Benchmark schemas."""
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class BenchmarkCreate(BaseModel):
    """Schema for creating/updating benchmark."""
    ticker: str
    description: Optional[str] = None


class BenchmarkResponse(BaseModel):
    """Schema for benchmark response."""
    id: int
    ticker: str
    description: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
