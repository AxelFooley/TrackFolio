"""
SystemState model - Stores application-level state like last price update timestamp.
"""
from datetime import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemState(Base):
    """
    SystemState model for storing application-level state and timestamps.

    This model is used to persist important system timestamps and configurations,
    such as the last successful price update. Using a dedicated model instead of
    relying on CachedMetrics ensures proper versioning and TTL handling.

    Each state is identified by a unique key (e.g., 'price_last_update', 'blockchain_last_sync').
    The value can be a timestamp or any string representation of the state.
    """
    __tablename__ = "system_state"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # State key (unique identifier)
    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique key for the state entry (e.g., 'price_last_update')"
    )

    # State value (typically a timestamp or state description)
    value: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
        comment="String representation of the state value"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When this state entry was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
        comment="When this state entry was last updated"
    )

    # Indexes
    __table_args__ = (
        Index('ix_system_state_updated_at', 'updated_at'),
    )

    def __repr__(self) -> str:
        return (
            f"SystemState(id={self.id!r}, "
            f"key={self.key!r}, "
            f"value={self.value!r}, "
            f"updated_at={self.updated_at!r})"
        )
