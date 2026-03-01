#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
from typing import Optional, List, Union, Dict, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import json
import logging

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas
from gns3server.services import auth_service

log = logging.getLogger(__name__)


class UsersRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)
        self._auth_service = auth_service

    async def get_user(self, user_id: UUID) -> Optional[models.User]:
        """
        Get a user by its ID.
        """

        query = select(models.User).where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_by_username(self, username: str) -> Optional[models.User]:
        """
        Get a user by its name.
        """

        query = select(models.User).where(models.User.username == username)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_by_email(self, email: str) -> Optional[models.User]:
        """
        Get a user by its email.
        """

        query = select(models.User).where(models.User.email == email)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_users(self) -> List[models.User]:
        """
        Get all users.
        """

        query = select(models.User)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_user(self, user: schemas.UserCreate) -> models.User:
        """
        Create a new user.
        """

        hashed_password = self._auth_service.hash_password(user.password.get_secret_value())
        db_user = models.User(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            hashed_password=hashed_password
        )
        self._db_session.add(db_user)
        await self._db_session.commit()
        await self._db_session.refresh(db_user)
        return db_user

    async def update_user(self, user_id: UUID, user_update: schemas.UserUpdate) -> Optional[models.User]:
        """
        Update a user.
        """

        update_values = user_update.model_dump(exclude_unset=True)
        password = update_values.pop("password", None)
        if password:
            update_values["hashed_password"] = self._auth_service.hash_password(password=password.get_secret_value())

        query = update(models.User).\
            where(models.User.user_id == user_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        user_db = await self.get_user(user_id)
        if user_db:
            await self._db_session.refresh(user_db)  # force refresh of updated_at value
        return user_db

    async def delete_user(self, user_id: UUID) -> bool:
        """
        Delete a user.
        """

        query = delete(models.User).where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def authenticate_user(self, username: str, password: str) -> Optional[models.User]:
        """
        Authenticate user.
        """

        user = await self.get_user_by_username(username)
        if not user:
            return None
        # Allow user to be authenticated if hashed password in the db is null
        # this is useful for manual password recovery like:
        # sqlite3 gns3_controller.db "UPDATE users SET hashed_password = null WHERE username = 'admin';"
        if user.hashed_password is None:
            log.warning(f"User '{username}' has been authenticated without a password "
                        f"configured. Please set a new password.")
            return user
        if not self._auth_service.verify_password(password, user.hashed_password):
            return None

        # Backup the updated_at value
        updated_at = user.updated_at
        user.last_login = func.current_timestamp()
        await self._db_session.commit()
        # Restore the original updated_at value
        # so it is not affected by the last login update
        user.updated_at = updated_at
        await self._db_session.commit()
        return user

    async def get_user_memberships(self, user_id: UUID) -> List[models.UserGroup]:
        """
        Get all user memberships (user groups).
        """

        query = select(models.UserGroup).\
            join(models.UserGroup.users).\
            filter(models.User.user_id == user_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_user_group(self, user_group_id: UUID) -> Optional[models.UserGroup]:
        """
        Get a user group by its ID.
        """

        query = select(models.UserGroup).where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_group_by_name(self, name: str) -> Optional[models.UserGroup]:
        """
        Get a user group by its name.
        """

        query = select(models.UserGroup).where(models.UserGroup.name == name)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_groups(self) -> List[models.UserGroup]:
        """
        Get all user groups.
        """

        query = select(models.UserGroup)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_user_group(self, user_group: schemas.UserGroupCreate) -> models.UserGroup:
        """
        Create a new user group.
        """

        db_user_group = models.UserGroup(name=user_group.name)
        self._db_session.add(db_user_group)
        await self._db_session.commit()
        await self._db_session.refresh(db_user_group)
        return db_user_group

    async def update_user_group(
            self,
            user_group_id: UUID,
            user_group_update: schemas.UserGroupUpdate
    ) -> Optional[models.UserGroup]:
        """
        Update a user group.
        """

        update_values = user_group_update.model_dump(exclude_unset=True)
        query = update(models.UserGroup).\
            where(models.UserGroup.user_group_id == user_group_id).\
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        user_group_db = await self.get_user_group(user_group_id)
        if user_group_db:
            await self._db_session.refresh(user_group_db)  # force refresh of updated_at value
        return user_group_db

    async def delete_user_group(self, user_group_id: UUID) -> bool:
        """
        Delete a user group.
        """

        query = delete(models.UserGroup).where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def add_member_to_user_group(
            self,
            user_group_id: UUID,
            user: models.User
    ) -> Union[None, models.UserGroup]:
        """
        Add a member to a user group.
        """

        query = select(models.UserGroup).\
            options(selectinload(models.UserGroup.users)).\
            where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        user_group_db = result.scalars().first()
        if not user_group_db:
            return None

        user_group_db.users.append(user)
        await self._db_session.commit()
        await self._db_session.refresh(user_group_db)
        return user_group_db

    async def remove_member_from_user_group(
            self,
            user_group_id: UUID,
            user: models.User
    ) -> Union[None, models.UserGroup]:
        """
        Remove a member from a user group.
        """

        query = select(models.UserGroup).\
            options(selectinload(models.UserGroup.users)).\
            where(models.UserGroup.user_group_id == user_group_id)
        result = await self._db_session.execute(query)
        user_group_db = result.scalars().first()
        if not user_group_db:
            return None

        user_group_db.users.remove(user)
        await self._db_session.commit()
        await self._db_session.refresh(user_group_db)
        return user_group_db

    async def get_user_group_members(self, user_group_id: UUID) -> List[models.User]:
        """
        Get all members from a user group.
        """

        query = select(models.User).\
            join(models.User.groups).\
            filter(models.UserGroup.user_group_id == user_group_id)

        result = await self._db_session.execute(query)
        return result.scalars().all()

    # Model profile methods (stored in user.model_configs as JSON)

    async def _get_model_configs_version(self, user_id: UUID) -> Optional[int]:
        """
        Helper method to get the current model_configs_version for a user.
        """
        user = await self.get_user(user_id)
        return user.model_configs_version if user else None

    async def get_model_configs(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get all model configurations for a user.
        Returns a dict with 'profiles' list and 'active' profile name.
        API keys are decrypted before returning.
        """

        user = await self.get_user(user_id)
        if not user:
            return {"profiles": [], "active": "default"}

        if not user.model_configs:
            return {"profiles": [], "active": "default"}

        try:
            from gns3server.utils.encryption import decrypt, is_encrypted

            configs = json.loads(user.model_configs)

            # Decrypt API keys in profiles
            for profile in configs.get("profiles", []):
                if "api_key" in profile and profile["api_key"]:
                    try:
                        encrypted = is_encrypted(profile["api_key"])
                        log.debug(f"Profile '{profile.get('name')}' api_key is_encrypted: {encrypted}")
                        if encrypted:
                            profile["api_key"] = decrypt(profile["api_key"])
                            log.debug(f"Profile '{profile.get('name')}' api_key decrypted successfully")
                    except Exception as e:
                        log.warning(f"Failed to decrypt API key for profile '{profile.get('name')}': {e}")

            return configs
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"Invalid model_configs JSON for user {user_id}: {e}")
            return {"profiles": [], "active": "default"}

    async def set_model_configs(
        self,
        user_id: UUID,
        configs: Dict[str, Any],
        expected_version: Optional[int] = None
    ) -> None:
        """
        Set all model configurations for a user.
        API keys are encrypted before storing.
        Uses optimistic locking to prevent concurrent modifications.

        :param user_id: User ID
        :param configs: Configuration dictionary
        :param expected_version: Expected version for optimistic locking (raises error if mismatch)
        :raises ValueError: If version mismatch (concurrent modification)
        """

        from gns3server.utils.encryption import encrypt

        # Encrypt API keys in profiles
        configs_to_store = json.loads(json.dumps(configs))  # Deep copy
        for profile in configs_to_store.get("profiles", []):
            if "api_key" in profile and profile["api_key"]:
                try:
                    profile["api_key"] = encrypt(profile["api_key"])
                except Exception as e:
                    log.error(f"Failed to encrypt API key for profile '{profile.get('name')}': {e}")
                    raise

        # Build update with optimistic locking
        values = {
            "model_configs": json.dumps(configs_to_store),
            "model_configs_version": models.User.model_configs_version + 1  # Increment version
        }

        # Build query with version check if provided
        query = update(models.User).where(models.User.user_id == user_id)
        if expected_version is not None:
            query = query.where(models.User.model_configs_version == expected_version)

        result = await self._db_session.execute(
            query.values(values)
        )

        await self._db_session.commit()

        # Check if the update actually happened (optimistic lock)
        if expected_version is not None and result.rowcount == 0:
            # Fetch current version to provide helpful error
            user = await self.get_user(user_id)
            current_version = user.model_configs_version if user else -1
            raise ValueError(
                f"Concurrent modification detected. Expected version {expected_version}, "
                f"but current version is {current_version}. Please retry."
            )

    async def add_model_profile(
        self,
        user_id: UUID,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a new model profile to the user's configurations.
        Accepts profile data including any extra fields.
        Uses optimistic locking to prevent concurrent modifications.
        """

        # Get current configs and version
        configs = await self.get_model_configs(user_id)
        current_version = await self._get_model_configs_version(user_id)

        # Check if profile with same name exists
        name = profile_data.get("name")
        if not name:
            raise ValueError("Profile name is required")

        # Reserve "active" as it conflicts with API routes
        if name == "active":
            raise ValueError("Profile name 'active' is reserved for system use")

        for profile in configs["profiles"]:
            if profile["name"] == name:
                raise ValueError(f"Profile '{name}' already exists")

        # Add new profile with all fields (including extra fields)
        new_profile = profile_data.copy()
        configs["profiles"].append(new_profile)

        # If this is the first profile, set it as active
        if len(configs["profiles"]) == 1:
            configs["active"] = name

        await self.set_model_configs(user_id, configs, expected_version=current_version)
        return new_profile

    async def update_model_profile(
        self,
        user_id: UUID,
        profile_name: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing model profile.
        Uses optimistic locking to prevent concurrent modifications.
        """

        # Get current configs and version
        configs = await self.get_model_configs(user_id)
        current_version = await self._get_model_configs_version(user_id)

        # Check if trying to rename to "active"
        new_name = updates.get("name")
        if new_name == "active":
            raise ValueError("Profile name 'active' is reserved for system use")

        # Check if new name conflicts with existing profile
        if new_name and new_name != profile_name:
            for profile in configs["profiles"]:
                if profile["name"] == new_name:
                    raise ValueError(f"Profile '{new_name}' already exists")

        for profile in configs["profiles"]:
            if profile["name"] == profile_name:
                # Update fields
                for key, value in updates.items():
                    if value is not None:
                        profile[key] = value

                # Update active profile reference if name changed
                if new_name and configs.get("active") == profile_name:
                    configs["active"] = new_name

                await self.set_model_configs(user_id, configs, expected_version=current_version)
                return profile

        return None

    async def delete_model_profile(self, user_id: UUID, profile_name: str) -> bool:
        """
        Delete a model profile.
        If deleting the active profile, switches to another profile.
        Uses optimistic locking to prevent concurrent modifications.
        """

        # Get current configs and version
        configs = await self.get_model_configs(user_id)
        current_version = await self._get_model_configs_version(user_id)

        # Find and remove the profile
        for i, profile in enumerate(configs["profiles"]):
            if profile["name"] == profile_name:
                configs["profiles"].pop(i)

                # If we deleted the active profile, switch to another
                if configs["active"] == profile_name:
                    if configs["profiles"]:
                        configs["active"] = configs["profiles"][0]["name"]
                    else:
                        configs["active"] = "default"

                await self.set_model_configs(user_id, configs, expected_version=current_version)
                return True

        return False

    async def set_active_model_profile(self, user_id: UUID, profile_name: str) -> bool:
        """
        Set the active model profile.
        Uses optimistic locking to prevent concurrent modifications.
        """

        # Get current configs and version
        configs = await self.get_model_configs(user_id)
        current_version = await self._get_model_configs_version(user_id)

        # Check if profile exists
        profile_exists = any(p["name"] == profile_name for p in configs["profiles"])
        if not profile_exists:
            return False

        configs["active"] = profile_name
        await self.set_model_configs(user_id, configs, expected_version=current_version)
        return True

    async def get_active_model_profile(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get the active model profile for a user.
        """

        configs = await self.get_model_configs(user_id)

        if not configs["profiles"]:
            return None

        for profile in configs["profiles"]:
            if profile["name"] == configs["active"]:
                return profile

        return None
