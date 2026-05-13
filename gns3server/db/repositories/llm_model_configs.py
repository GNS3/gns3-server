#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from uuid import UUID
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, and_
from datetime import datetime

import logging

from .base import BaseRepository
import gns3server.db.models as models

log = logging.getLogger(__name__)


class LLMModelConfigsRepository(BaseRepository):
    """Repository for LLM model configurations with inheritance support."""

    @staticmethod
    def _hide_api_key(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove API key from config dict for security.
        API keys should NEVER be returned via API endpoints.

        :param config: Configuration dictionary
        :return: Configuration dictionary with api_key set to None
        """
        config_copy = config.copy()
        if "api_key" in config_copy:
            config_copy["api_key"] = None
        return config_copy

    # User configuration methods

    async def get_user_config(self, config_id: UUID) -> Optional[models.LLMModelConfig]:
        """Get a user's LLM model configuration by ID."""
        query = select(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.user_id.isnot(None)
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_configs(self, user_id: UUID) -> List[models.LLMModelConfig]:
        """Get all LLM model configurations for a user."""
        query = select(models.LLMModelConfig).where(
            models.LLMModelConfig.user_id == user_id
        ).order_by(models.LLMModelConfig.created_at)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_user_default_config(self, user_id: UUID) -> Optional[models.LLMModelConfig]:
        """Get a user's default LLM model configuration."""
        query = select(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.user_id == user_id,
                models.LLMModelConfig.is_default
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def create_user_config(
        self,
        user_id: UUID,
        name: str,
        model_type: str,
        config_data: Dict[str, Any],
        is_default: bool = False
    ) -> models.LLMModelConfig:
        """Create a new LLM model configuration for a user."""
        # Encrypt API key if present
        from gns3server.utils.encryption import encrypt
        config_to_store = config_data.copy()
        if "api_key" in config_to_store and config_to_store["api_key"]:
            try:
                config_to_store["api_key"] = encrypt(config_to_store["api_key"])
            except Exception as e:
                log.error(f"Failed to encrypt API key: {e}")
                raise

        # Set timestamps manually for SQLite compatibility
        now = datetime.utcnow()
        db_config = models.LLMModelConfig(
            name=name,
            model_type=model_type,
            config=config_to_store,
            user_id=user_id,
            is_default=is_default,
            created_at=now,
            updated_at=now
        )
        self._db_session.add(db_config)
        await self._db_session.commit()
        await self._db_session.refresh(db_config)
        return db_config

    async def update_user_config(
        self,
        config_id: UUID,
        user_id: UUID,
        updates: Dict[str, Any],
        expected_version: Optional[int] = None
    ) -> Optional[models.LLMModelConfig]:
        """
        Update a user's LLM model configuration.
        Uses optimistic locking to prevent concurrent modifications.

        :param config_id: Configuration ID
        :param user_id: User ID
        :param updates: Dictionary of fields to update
        :param expected_version: Expected version for optimistic locking (raises error if mismatch)
        :raises ValueError: If version mismatch (concurrent modification)
        """
        query = select(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.user_id == user_id
            )
        )
        result = await self._db_session.execute(query)
        db_config = result.scalars().first()

        if not db_config:
            return None

        # Check optimistic lock if expected_version is provided
        if expected_version is not None and db_config.version != expected_version:
            raise ValueError(
                f"Concurrent modification detected. Expected version {expected_version}, "
                f"but current version is {db_config.version}. Please retry."
            )

        # Encrypt API key if present in updates
        from gns3server.utils.encryption import encrypt

        # Table-level fields
        if "name" in updates and updates["name"] is not None:
            db_config.name = updates["name"]
        if "model_type" in updates and updates["model_type"] is not None:
            db_config.model_type = updates["model_type"]
        if "is_default" in updates and updates["is_default"] is not None:
            db_config.is_default = updates["is_default"]

        # Config JSONB fields
        config_fields = ["provider", "base_url", "model", "temperature", "api_key", "max_tokens"]
        current_config = db_config.config.copy()

        for field in config_fields:
            if field in updates and updates[field] is not None:
                if field == "api_key":
                    # Encrypt API key
                    try:
                        current_config[field] = encrypt(updates[field])
                    except Exception as e:
                        log.error(f"Failed to encrypt API key: {e}")
                        raise
                else:
                    current_config[field] = updates[field]

        # Handle extra config fields
        for key, value in updates.items():
            if key not in ["name", "model_type", "is_default", "expected_version"] + config_fields:
                if value is not None:
                    current_config[key] = value

        db_config.config = current_config
        # Increment version for optimistic locking
        db_config.version = db_config.version + 1
        # Update timestamp manually for SQLite compatibility
        db_config.updated_at = datetime.utcnow()
        await self._db_session.commit()
        await self._db_session.refresh(db_config)
        return db_config

    async def delete_user_config(self, config_id: UUID, user_id: UUID) -> bool:
        """Delete a user's LLM model configuration."""
        query = delete(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.user_id == user_id
            )
        )
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def set_user_default_config(self, user_id: UUID, config_id: UUID) -> bool:
        """Set a user's default LLM model configuration."""
        now = datetime.utcnow()
        # First, unset current default
        await self._db_session.execute(
            update(models.LLMModelConfig)
            .where(
                and_(
                    models.LLMModelConfig.user_id == user_id,
                    models.LLMModelConfig.is_default
                )
            )
            .values(is_default=False, updated_at=now)
        )

        # Set new default
        query = update(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.user_id == user_id
            )
        ).values(is_default=True, updated_at=now)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    # Group configuration methods

    async def get_group_config(self, config_id: UUID) -> Optional[models.LLMModelConfig]:
        """Get a group's LLM model configuration by ID."""
        query = select(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.group_id.isnot(None)
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_group_configs(self, group_id: UUID) -> List[models.LLMModelConfig]:
        """Get all LLM model configurations for a group."""
        query = select(models.LLMModelConfig).where(
            models.LLMModelConfig.group_id == group_id
        ).order_by(models.LLMModelConfig.created_at)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_group_default_config(self, group_id: UUID) -> Optional[models.LLMModelConfig]:
        """Get a group's default LLM model configuration."""
        query = select(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.group_id == group_id,
                models.LLMModelConfig.is_default
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def create_group_config(
        self,
        group_id: UUID,
        name: str,
        model_type: str,
        config_data: Dict[str, Any],
        is_default: bool = False
    ) -> models.LLMModelConfig:
        """Create a new LLM model configuration for a group."""
        # Encrypt API key if present
        from gns3server.utils.encryption import encrypt
        config_to_store = config_data.copy()
        if "api_key" in config_to_store and config_to_store["api_key"]:
            try:
                config_to_store["api_key"] = encrypt(config_to_store["api_key"])
            except Exception as e:
                log.error(f"Failed to encrypt API key: {e}")
                raise

        # Set timestamps manually for SQLite compatibility
        now = datetime.utcnow()
        db_config = models.LLMModelConfig(
            name=name,
            model_type=model_type,
            config=config_to_store,
            group_id=group_id,
            is_default=is_default,
            created_at=now,
            updated_at=now
        )
        self._db_session.add(db_config)
        await self._db_session.commit()
        await self._db_session.refresh(db_config)
        return db_config

    async def update_group_config(
        self,
        config_id: UUID,
        group_id: UUID,
        updates: Dict[str, Any],
        expected_version: Optional[int] = None
    ) -> Optional[models.LLMModelConfig]:
        """
        Update a group's LLM model configuration.
        Uses optimistic locking to prevent concurrent modifications.

        :param config_id: Configuration ID
        :param group_id: Group ID
        :param updates: Dictionary of fields to update
        :param expected_version: Expected version for optimistic locking (raises error if mismatch)
        :raises ValueError: If version mismatch (concurrent modification)
        """
        query = select(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.group_id == group_id
            )
        )
        result = await self._db_session.execute(query)
        db_config = result.scalars().first()

        if not db_config:
            return None

        # Check optimistic lock if expected_version is provided
        if expected_version is not None and db_config.version != expected_version:
            raise ValueError(
                f"Concurrent modification detected. Expected version {expected_version}, "
                f"but current version is {db_config.version}. Please retry."
            )

        # Encrypt API key if present in updates
        from gns3server.utils.encryption import encrypt

        # Table-level fields
        if "name" in updates and updates["name"] is not None:
            db_config.name = updates["name"]
        if "model_type" in updates and updates["model_type"] is not None:
            db_config.model_type = updates["model_type"]
        if "is_default" in updates and updates["is_default"] is not None:
            db_config.is_default = updates["is_default"]

        # Config JSONB fields
        config_fields = ["provider", "base_url", "model", "temperature", "api_key", "max_tokens"]
        current_config = db_config.config.copy()

        for field in config_fields:
            if field in updates and updates[field] is not None:
                if field == "api_key":
                    # Encrypt API key
                    try:
                        current_config[field] = encrypt(updates[field])
                    except Exception as e:
                        log.error(f"Failed to encrypt API key: {e}")
                        raise
                else:
                    current_config[field] = updates[field]

        # Handle extra config fields
        for key, value in updates.items():
            if key not in ["name", "model_type", "is_default", "expected_version"] + config_fields:
                if value is not None:
                    current_config[key] = value

        db_config.config = current_config
        # Increment version for optimistic locking
        db_config.version = db_config.version + 1
        # Update timestamp manually for SQLite compatibility
        db_config.updated_at = datetime.utcnow()
        await self._db_session.commit()
        await self._db_session.refresh(db_config)
        return db_config

    async def delete_group_config(self, config_id: UUID, group_id: UUID) -> bool:
        """Delete a group's LLM model configuration."""
        query = delete(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.group_id == group_id
            )
        )
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def set_group_default_config(self, group_id: UUID, config_id: UUID) -> bool:
        """Set a group's default LLM model configuration."""
        now = datetime.utcnow()
        # First, unset current default
        await self._db_session.execute(
            update(models.LLMModelConfig)
            .where(
                and_(
                    models.LLMModelConfig.group_id == group_id,
                    models.LLMModelConfig.is_default
                )
            )
            .values(is_default=False, updated_at=now)
        )

        # Set new default
        query = update(models.LLMModelConfig).where(
            and_(
                models.LLMModelConfig.config_id == config_id,
                models.LLMModelConfig.group_id == group_id
            )
        ).values(is_default=True, updated_at=now)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    # Inheritance methods

    async def get_user_effective_configs(
        self,
        user_id: UUID,
        current_user_id: Optional[UUID] = None,
        current_user_is_superadmin: bool = False
    ) -> Dict[str, Any]:
        """
        Get user's effective configurations (own + inherited from groups).
        Returns a dict with 'configs' list and 'default_config'.

        API key visibility: ALWAYS hidden for security (never returned via API).
        """
        # Get user's own configs
        user_configs = await self.get_user_configs(user_id)

        # Get user's groups
        query = select(models.UserGroup).\
            join(models.UserGroup.users).\
            filter(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        user_groups = result.scalars().all()

        # Get group configs
        group_configs_map = {}  # group_id -> [configs]
        group_names_map = {}  # group_id -> group_name
        for group in user_groups:
            configs = await self.get_group_configs(group.user_group_id)
            if configs:
                group_configs_map[group.user_group_id] = configs
                group_names_map[group.user_group_id] = group.name

        # Build result with API keys always hidden
        configs_with_source = []
        default_config = None

        # Add user's configs
        for config in user_configs:
            # Always hide API key for security
            config_dict = self._hide_api_key(config.config)

            configs_with_source.append({
                "config_id": config.config_id,
                "name": config.name,
                "model_type": config.model_type,
                "config": config_dict,
                "user_id": config.user_id,
                "group_id": config.group_id,
                "is_default": config.is_default,
                "version": config.version,
                "created_at": config.created_at,
                "updated_at": config.updated_at,
                "source": "user",
                "group_name": None
            })

        # Add inherited group configs (always shown, regardless of user configs)
        for group_id, configs in group_configs_map.items():
            for config in configs:
                # Always hide API key for security
                config_dict = self._hide_api_key(config.config)

                configs_with_source.append({
                    "config_id": config.config_id,
                    "name": config.name,
                    "model_type": config.model_type,
                    "config": config_dict,
                    "user_id": config.user_id,
                    "group_id": config.group_id,
                    "is_default": config.is_default,
                    "version": config.version,
                    "created_at": config.created_at,
                    "updated_at": config.updated_at,
                    "source": "group",
                    "group_name": group_names_map[group_id]
                })

        # Select default_config with proper priority:
        # 1. User's config marked with is_default: true
        # 2. Group's config marked with is_default: true
        # 3. First config in the list (user configs come first)
        for config in configs_with_source:
            if config["is_default"] and config["source"] == "user":
                default_config = config
                break

        if default_config is None:
            for config in configs_with_source:
                if config["is_default"] and config["source"] == "group":
                    default_config = config
                    break

        # Fallback to first config if no default is marked
        if default_config is None and configs_with_source:
            default_config = configs_with_source[0]

        return {
            "configs": configs_with_source,
            "default_config": default_config
        }
