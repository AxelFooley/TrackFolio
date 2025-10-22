"""
System state manager - Manages application-level state like last price update timestamp.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import logging

from app.models.system_state import SystemState

logger = logging.getLogger(__name__)


class SystemStateManager:
    """Manager for system-level state and timestamps."""

    # State key constants
    PRICE_LAST_UPDATE = "price_last_update"
    BLOCKCHAIN_LAST_SYNC = "blockchain_last_sync"
    CRYPTO_PRICE_LAST_UPDATE = "crypto_price_last_update"

    @staticmethod
    def get_state(db: Session, key: str) -> Optional[SystemState]:
        """
        Retrieve a system state entry by key (synchronous).

        Args:
            db: Synchronous database session
            key: The state key identifier

        Returns:
            SystemState object if found, None otherwise
        """
        try:
            result = db.execute(
                select(SystemState).where(SystemState.key == key)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving system state for key '{key}': {e}")
            return None

    @staticmethod
    async def get_state_async(db: AsyncSession, key: str) -> Optional[SystemState]:
        """
        Retrieve a system state entry by key (asynchronous).

        Args:
            db: Asynchronous database session
            key: The state key identifier

        Returns:
            SystemState object if found, None otherwise
        """
        try:
            result = await db.execute(
                select(SystemState).where(SystemState.key == key)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving system state for key '{key}': {e}")
            return None

    @staticmethod
    def set_state(db: Session, key: str, value: str) -> bool:
        """
        Set or update a system state entry (synchronous).

        Args:
            db: Synchronous database session
            key: The state key identifier
            value: The state value

        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to get existing state
            existing = db.execute(
                select(SystemState).where(SystemState.key == key)
            ).scalar_one_or_none()

            if existing:
                # Update existing
                existing.value = value
                existing.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing)
                logger.debug(f"Updated system state '{key}' to '{value}'")
            else:
                # Create new
                new_state = SystemState(key=key, value=value)
                db.add(new_state)
                db.commit()
                db.refresh(new_state)
                logger.debug(f"Created new system state '{key}' = '{value}'")

            return True
        except IntegrityError:
            # Race condition - another process created this key
            db.rollback()
            try:
                # Try to update instead
                existing = db.execute(
                    select(SystemState).where(SystemState.key == key)
                ).scalar_one_or_none()
                if existing:
                    existing.value = value
                    existing.updated_at = datetime.utcnow()
                    db.commit()
                    db.refresh(existing)
                    logger.debug(f"Updated system state '{key}' (after race condition)")
                    return True
            except Exception as e:
                logger.error(f"Error handling race condition for key '{key}': {e}")
                db.rollback()
                return False
        except Exception as e:
            logger.error(f"Error setting system state for key '{key}': {e}")
            db.rollback()
            return False

    @staticmethod
    async def set_state_async(db: AsyncSession, key: str, value: str) -> bool:
        """
        Set or update a system state entry (asynchronous).

        Args:
            db: Asynchronous database session
            key: The state key identifier
            value: The state value

        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to get existing state
            result = await db.execute(
                select(SystemState).where(SystemState.key == key)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.value = value
                existing.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(existing)
                logger.debug(f"Updated system state '{key}' to '{value}'")
            else:
                # Create new
                new_state = SystemState(key=key, value=value)
                db.add(new_state)
                await db.commit()
                await db.refresh(new_state)
                logger.debug(f"Created new system state '{key}' = '{value}'")

            return True
        except IntegrityError:
            # Race condition - another process created this key
            await db.rollback()
            try:
                # Try to update instead
                result = await db.execute(
                    select(SystemState).where(SystemState.key == key)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.value = value
                    existing.updated_at = datetime.utcnow()
                    await db.commit()
                    await db.refresh(existing)
                    logger.debug(f"Updated system state '{key}' (after race condition)")
                    return True
            except Exception as e:
                logger.error(f"Error handling race condition for key '{key}': {e}")
                await db.rollback()
                return False
        except Exception as e:
            logger.error(f"Error setting system state for key '{key}': {e}")
            await db.rollback()
            return False

    @staticmethod
    def update_price_last_update(db: Session) -> bool:
        """
        Update the last price update timestamp to now (synchronous).

        Args:
            db: Synchronous database session

        Returns:
            True if successful, False otherwise
        """
        timestamp_str = datetime.utcnow().isoformat()
        return SystemStateManager.set_state(
            db,
            SystemStateManager.PRICE_LAST_UPDATE,
            timestamp_str
        )

    @staticmethod
    async def update_price_last_update_async(db: AsyncSession) -> bool:
        """
        Update the last price update timestamp to now (asynchronous).

        Args:
            db: Asynchronous database session

        Returns:
            True if successful, False otherwise
        """
        timestamp_str = datetime.utcnow().isoformat()
        return await SystemStateManager.set_state_async(
            db,
            SystemStateManager.PRICE_LAST_UPDATE,
            timestamp_str
        )

    @staticmethod
    def get_price_last_update(db: Session) -> Optional[datetime]:
        """
        Get the last price update timestamp (synchronous).

        Args:
            db: Synchronous database session

        Returns:
            datetime object if found and valid, None otherwise
        """
        state = SystemStateManager.get_state(db, SystemStateManager.PRICE_LAST_UPDATE)
        if state and state.value:
            try:
                return datetime.fromisoformat(state.value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp format in system state: {e}")
                return None
        return None

    @staticmethod
    async def get_price_last_update_async(db: AsyncSession) -> Optional[datetime]:
        """
        Get the last price update timestamp (asynchronous).

        Args:
            db: Asynchronous database session

        Returns:
            datetime object if found and valid, None otherwise
        """
        state = await SystemStateManager.get_state_async(db, SystemStateManager.PRICE_LAST_UPDATE)
        if state and state.value:
            try:
                return datetime.fromisoformat(state.value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp format in system state: {e}")
                return None
        return None

    @staticmethod
    def update_blockchain_last_sync(db: Session) -> bool:
        """
        Update the last blockchain sync timestamp to now (synchronous).

        Args:
            db: Synchronous database session

        Returns:
            True if successful, False otherwise
        """
        timestamp_str = datetime.utcnow().isoformat()
        return SystemStateManager.set_state(
            db,
            SystemStateManager.BLOCKCHAIN_LAST_SYNC,
            timestamp_str
        )

    @staticmethod
    def get_blockchain_last_sync(db: Session) -> Optional[datetime]:
        """
        Get the last blockchain sync timestamp (synchronous).

        Args:
            db: Synchronous database session

        Returns:
            datetime object if found and valid, None otherwise
        """
        state = SystemStateManager.get_state(db, SystemStateManager.BLOCKCHAIN_LAST_SYNC)
        if state and state.value:
            try:
                return datetime.fromisoformat(state.value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp format in system state: {e}")
                return None
        return None
