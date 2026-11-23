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

import logging
from typing import Any, Dict, List, Optional, Set, Union, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import gns3server.db.models as models
from gns3server import schemas
from gns3server.config import Config
from gns3server.db.models.users import user_group_map
from gns3server.db.rbac_state import RbacState
from gns3server.db.user_quota_state import UserQuotaState
from gns3server.services import auth_service, ldap_service
from gns3server.services.ldap import LDAPService, LDAPUserProfile

from .base import BaseRepository

log = logging.getLogger(__name__)


class UsersRepository(BaseRepository):
    def __init__(self, db_session: AsyncSession, ldap_service_instance: Optional[LDAPService] = None) -> None:

        super().__init__(db_session)
        self._auth_service = auth_service
        self._ldap_service = ldap_service_instance or ldap_service
        self._rbac_state = RbacState.instance()
        self._quota_state = UserQuotaState.instance()

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

    async def get_user_by_username_case_insensitive(self, username: str) -> Optional[models.User]:
        """
        Get a user by its name using case-insensitive matching.
        """

        query = select(models.User).where(func.lower(models.User.username) == username.lower())
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_by_email(self, email: str) -> Optional[models.User]:
        """
        Get a user by its email.
        """

        query = select(models.User).where(func.lower(models.User.email) == email.lower())
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_users(self) -> List[models.User]:
        """
        Get all users.
        """

        query = select(models.User)
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def create_user(self, user: schemas.UserCreate) -> models.User:
        """
        Create a new user and add it to the given user group.
        """

        existing_user = await self.get_user_by_username_case_insensitive(user.username)
        if existing_user:
            raise IntegrityError(
                f"User with username '{user.username}' already exists (case-insensitive collision with '{existing_user.username}')",
                params=None,
                orig=Exception("UNIQUE constraint failed: users.username"),
            )

        hashed_password = self._auth_service.hash_password(user.password.get_secret_value())
        db_user = models.User(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            hashed_password=hashed_password,
            max_nodes=user.max_nodes,
            max_running_nodes=user.max_running_nodes,
        )
        self._db_session.add(db_user)
        await self._db_session.flush()  # assign the user id
        await self._db_session.execute(
            user_group_map.insert().values(user_id=db_user.user_id, user_group_id=user.user_group_id)
        )
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        await self._db_session.refresh(db_user)
        return db_user

    async def update_user(
        self,
        user_id: UUID,
        user_update: Union[schemas.UserUpdate, schemas.LoggedInUserUpdate],
        **extra_values: Any,
    ) -> Optional[models.User]:
        """
        Update a user.
        """

        update_values = user_update.model_dump(exclude_unset=True)
        password = update_values.pop("password", None)
        if password:
            update_values["hashed_password"] = self._auth_service.hash_password(password=password.get_secret_value())
        update_values.update(extra_values)

        query = update(models.User).where(models.User.user_id == user_id).values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        user_db = await self.get_user(user_id)
        if user_db:
            await self._db_session.refresh(user_db)  # force refresh of updated_at value
        return user_db

    async def logout_user(self, user_id: UUID) -> None:
        """
        Increment token_version to invalidate all existing tokens for the user.
        """

        query = (
            update(models.User)
            .where(models.User.user_id == user_id)
            .values(token_version=models.User.token_version + 1)
        )

        await self._db_session.execute(query)
        await self._db_session.commit()

    async def delete_user(self, user_id: UUID) -> bool:
        """
        Delete a user.
        """

        query = delete(models.User).where(models.User.user_id == user_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        return cast(CursorResult, result).rowcount > 0

    async def _update_last_login(self, user: models.User) -> models.User:
        """
        Update user's last login timestamp without altering updated_at.
        """

        updated_at = user.updated_at
        user.last_login = func.current_timestamp()
        await self._db_session.commit()
        user.updated_at = updated_at
        await self._db_session.commit()
        await self._db_session.refresh(user)
        return user

    async def _lookup_or_link_ldap_user(self, profile: LDAPUserProfile) -> Optional[models.User]:
        user = None

        # 1. Primary lookup by immutable external directory identifier
        if profile.external_id:
            query_ext = (
                select(models.User)
                .options(selectinload(models.User.groups))
                .where(
                    models.User.auth_source == "ldap",
                    models.User.external_id == profile.external_id,
                )
            )
            res_ext = await self._db_session.execute(query_ext)
            user = res_ext.scalars().first()

        # 2. Secondary lookup by case-insensitive username match
        if not user:
            query = (
                select(models.User)
                .options(selectinload(models.User.groups))
                .where(func.lower(models.User.username) == profile.username.lower())
            )
            result = await self._db_session.execute(query)
            user = result.scalars().first()

            if user and user.auth_source == "local" and user.is_superadmin:
                log.warning(
                    "Refusing to adopt or overwrite local superadmin recovery account '%s' with LDAP profile",
                    profile.username,
                )
                return None

            if user and user.auth_source == "ldap" and profile.external_id and not user.external_id:
                user.external_id = profile.external_id
                await self._db_session.commit()

        return user

    async def _create_or_adopt_ldap_user(self, profile: LDAPUserProfile) -> models.User:
        email = profile.email
        if email:
            existing_email_user = await self.get_user_by_email(email)
            if existing_email_user:
                log.warning(
                    "Email '%s' from LDAP is already associated with account '%s'; omitting email to prevent adoption",
                    email,
                    existing_email_user.username,
                )
                email = None

        user = models.User(
            username=profile.username,
            email=email,
            full_name=profile.full_name,
            hashed_password=None,
            auth_source="ldap",
            external_id=profile.external_id,
            is_active=True,
            is_superadmin=False,
        )
        try:
            async with self._db_session.begin_nested():
                self._db_session.add(user)
                await self._db_session.flush()
        except IntegrityError:
            log.info(
                "Concurrent JIT provisioning detected for LDAP user '%s'; recovering existing record", profile.username
            )
            existing = await self._lookup_or_link_ldap_user(profile)
            if existing:
                return existing
            existing_by_name = await self.get_user_by_username_case_insensitive(profile.username)
            if existing_by_name:
                return existing_by_name
            raise
        return user

    async def _sync_user_profile_fields(self, user: models.User, profile: LDAPUserProfile) -> None:
        update_data: dict[str, Any] = {}

        if user.auth_source != "ldap":
            from gns3server.config import Config

            if user.username.lower() != Config.instance().settings.Controller.default_admin_username.lower():
                log.info("Transitioning local user '%s' to LDAP authenticated account", user.username)
                update_data["auth_source"] = "ldap"

        if profile.external_id and user.external_id != profile.external_id:
            update_data["external_id"] = profile.external_id

        if profile.email and user.email != profile.email:
            existing_email_user = await self.get_user_by_email(profile.email)
            if not existing_email_user or existing_email_user.user_id == user.user_id:
                update_data["email"] = profile.email
            elif existing_email_user.auth_source == "ldap" and existing_email_user.user_id != user.user_id:
                log.info(
                    "Migrating email '%s' from legacy LDAP account '%s' to canonical user '%s'",
                    profile.email,
                    existing_email_user.username,
                    user.username,
                )
                await self._db_session.execute(
                    update(models.User).where(models.User.user_id == existing_email_user.user_id).values(email=None)
                )
                update_data["email"] = profile.email
            else:
                log.warning(
                    "Cannot update email for user '%s': email '%s' already in use by another account",
                    user.username,
                    profile.email,
                )
        if profile.full_name and user.full_name != profile.full_name:
            update_data["full_name"] = profile.full_name

        if update_data:
            await self._db_session.execute(
                update(models.User).where(models.User.user_id == user.user_id).values(update_data)
            )
            await self._db_session.refresh(user)

    async def _sync_user_groups(self, user: models.User, profile: LDAPUserProfile) -> None:
        target_group_ids: List[UUID] = []
        target_group_names: Set[str] = set()
        log.info("Resolving mapped groups for LDAP user '%s' (profile.groups: %s)", profile.username, profile.groups)
        for group_name in profile.groups:
            grp = await self.get_user_group_by_name(group_name)
            if grp:
                target_group_ids.append(grp.user_group_id)
                target_group_names.add(str(grp.name))
                log.info(
                    "Assigned user '%s' to GNS3 group '%s' (UUID: %s)", profile.username, grp.name, grp.user_group_id
                )
            else:
                log.warning("LDAP mapped group '%s' not found in database", group_name)

        unique_group_ids = list(dict.fromkeys(target_group_ids))

        # Only synchronize memberships for groups governed by directory mappings or default group,
        # plus any groups previously granted to this user by LDAP.
        from gns3server.config import Config

        ldap_config = Config.instance().settings.LDAP
        managed_group_names = set(ldap_config.group_mapping.values())
        if ldap_config.default_group:
            managed_group_names.add(ldap_config.default_group)

        # Include groups previously granted to this user by LDAP so removed mappings are revoked
        import json

        previously_granted_names: Set[str] = set()
        if user.ldap_groups:
            try:
                parsed = json.loads(user.ldap_groups)
                if isinstance(parsed, list):
                    previously_granted_names = set(parsed)
            except Exception as e:
                log.warning("Failed to parse ldap_groups JSON for user '%s': %s", user.username, e)
        managed_group_names.update(previously_granted_names)

        # Ensure base privileges: if no mapped groups matched, fallback to default_group or 'Users'
        if not unique_group_ids:
            fallback_name = ldap_config.default_group or "Users"
            fallback_grp = await self.get_user_group_by_name(fallback_name)
            if not fallback_grp and fallback_name != "Users":
                log.warning(
                    "Configured LDAP default_group '%s' not found in database; falling back to 'Users'", fallback_name
                )
                fallback_grp = await self.get_user_group_by_name("Users")
            if fallback_grp:
                unique_group_ids.append(fallback_grp.user_group_id)
                target_group_names.add(str(fallback_grp.name))
                managed_group_names.add(str(fallback_grp.name))
                log.info(
                    "Assigned fallback group '%s' to LDAP user '%s' to ensure base privileges",
                    fallback_grp.name,
                    profile.username,
                )

        managed_group_ids: List[UUID] = []
        for name in managed_group_names:
            grp = await self.get_user_group_by_name(name)
            if grp:
                managed_group_ids.append(grp.user_group_id)

        if managed_group_ids:
            await self._db_session.execute(
                delete(models.user_group_map).where(
                    models.user_group_map.c.user_id == user.user_id,
                    models.user_group_map.c.user_group_id.in_(managed_group_ids),
                )
            )

        for group_id in unique_group_ids:
            await self._db_session.execute(
                models.user_group_map.insert().values(user_id=user.user_id, user_group_id=group_id)
            )

        user.ldap_groups = json.dumps(list(target_group_names))

        if not unique_group_ids:
            log.warning(
                "No GNS3 groups were assigned to LDAP user '%s' (profile.groups: %s)", profile.username, profile.groups
            )

    async def sync_ldap_user(self, profile: LDAPUserProfile) -> models.User:
        """
        Provision or synchronize an LDAP authenticated user.
        """
        user = await self._lookup_or_link_ldap_user(profile)
        if not user:
            user = await self._create_or_adopt_ldap_user(profile)
        else:
            await self._sync_user_profile_fields(user, profile)

        await self._sync_user_groups(user, profile)

        user = await self._update_last_login(user)
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        return user

    async def authenticate_user(self, username: str, password: str) -> Optional[models.User]:
        """
        Authenticate user.
        """

        local_user = await self.get_user_by_username(username)

        # 1. Superadmin local check first for emergency recovery (local accounts only)
        if local_user and local_user.auth_source == "local" and local_user.is_superadmin:
            if local_user.hashed_password is None:
                log.warning(
                    f"User '{username}' has been authenticated without a password configured. Please set a new password."
                )
                return await self._update_last_login(local_user)
            if self._auth_service.verify_password(password, local_user.hashed_password):
                return await self._update_last_login(local_user)
            log.warning("Authentication failed for local superadmin recovery account '%s'", username)
            return None

        # 2. LDAP authentication if enabled
        ldap_config = Config.instance().settings.LDAP
        if ldap_config.enabled:
            ldap_profile = await self._ldap_service.authenticate(username, password, ldap_config)
            if ldap_profile:
                return await self.sync_ldap_user(ldap_profile)
            if not ldap_config.fallback_to_local:
                return None

        # 3. Fallback to standard local database authentication
        if not local_user:
            return None

        # Directory-managed accounts cannot authenticate using local database fallback
        # unless LDAP has been explicitly disabled globally (Disaster Recovery scenario).
        # In disaster recovery mode, directory accounts require a local password hash to be explicitly
        # set by an administrator before local authentication is permitted.
        if local_user.auth_source == "ldap":
            if Config.instance().settings.LDAP.enabled or local_user.hashed_password is None:
                return None

        # Only allow passwordless login for the built-in local administrator (first-boot bootstrap)
        if local_user.hashed_password is None:
            if local_user.username == "admin" and local_user.auth_source == "local" and local_user.is_superadmin:
                log.warning(
                    f"User '{username}' has been authenticated without a password configured. Please set a new password."
                )
                return await self._update_last_login(local_user)
            return None

        if not self._auth_service.verify_password(password, local_user.hashed_password):
            return None

        return await self._update_last_login(local_user)

    async def get_user_preferences(self, user_id: UUID) -> Optional[models.UserPreferences]:
        """
        Get the preferences document of a user, or None if never saved.
        """

        query = select(models.UserPreferences).where(models.UserPreferences.user_id == user_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def save_user_preferences(self, user_id: UUID, preferences: Dict[str, Any]) -> models.UserPreferences:
        """
        Create or replace the preferences document of a user (last write wins).

        Concurrent first saves (e.g. two tabs of the same user) race on the
        single-row insert: the loser falls back to updating the winning row.
        """

        db_prefs = await self.get_user_preferences(user_id)
        if db_prefs is None:
            db_prefs = models.UserPreferences(user_id=user_id, preferences=preferences)
            self._db_session.add(db_prefs)
            try:
                await self._db_session.commit()
            except IntegrityError:
                await self._db_session.rollback()
                db_prefs = await self.get_user_preferences(user_id)
                if db_prefs is None:
                    raise
                db_prefs.preferences = preferences
                await self._db_session.commit()
        else:
            db_prefs.preferences = preferences
            await self._db_session.commit()
        await self._db_session.refresh(db_prefs)
        return db_prefs

    async def delete_user_preferences(self, user_id: UUID) -> bool:
        """
        Delete the preferences document of a user.
        """

        query = delete(models.UserPreferences).where(models.UserPreferences.user_id == user_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return cast(CursorResult, result).rowcount > 0

    async def get_user_memberships(self, user_id: UUID) -> List[models.UserGroup]:
        """
        Get all user memberships (user groups).
        """

        query = select(models.UserGroup).join(models.UserGroup.users).filter(models.User.user_id == user_id)

        result = await self._db_session.execute(query)
        return list(result.scalars().all())

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

        query = select(models.UserGroup).where(func.lower(models.UserGroup.name) == name.lower())
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_user_groups(self) -> List[models.UserGroup]:
        """
        Get all user groups.
        """

        query = select(models.UserGroup)
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def create_user_group(self, user_group: schemas.UserGroupCreate) -> models.UserGroup:
        """
        Create a new user group.
        """

        db_user_group = models.UserGroup(
            name=user_group.name,
            default_max_nodes=user_group.default_max_nodes,
            default_max_running_nodes=user_group.default_max_running_nodes,
        )
        self._db_session.add(db_user_group)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        await self._db_session.refresh(db_user_group)
        return db_user_group

    async def update_user_group(
        self, user_group_id: UUID, user_group_update: schemas.UserGroupUpdate
    ) -> Optional[models.UserGroup]:
        """
        Update a user group.
        """

        update_values = user_group_update.model_dump(exclude_unset=True)
        query = update(models.UserGroup).where(models.UserGroup.user_group_id == user_group_id).values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
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
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        return cast(CursorResult, result).rowcount > 0

    async def add_member_to_user_group(self, user_group_id: UUID, user: models.User) -> Union[None, models.UserGroup]:
        """
        Add a member to a user group.
        """

        query = (
            select(models.UserGroup)
            .options(selectinload(models.UserGroup.users))
            .where(models.UserGroup.user_group_id == user_group_id)
        )
        result = await self._db_session.execute(query)
        user_group_db = result.scalars().first()
        if not user_group_db:
            return None

        user_group_db.users.append(user)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        await self._db_session.refresh(user_group_db)
        return user_group_db

    async def remove_member_from_user_group(
        self, user_group_id: UUID, user: models.User
    ) -> Union[None, models.UserGroup]:
        """
        Remove a member from a user group.
        """

        query = (
            select(models.UserGroup)
            .options(selectinload(models.UserGroup.users))
            .where(models.UserGroup.user_group_id == user_group_id)
        )
        result = await self._db_session.execute(query)
        user_group_db = result.scalars().first()
        if not user_group_db:
            return None

        user_group_db.users.remove(user)
        await self._db_session.commit()
        self._rbac_state.mark_dirty()
        self._quota_state.mark_dirty()
        await self._db_session.refresh(user_group_db)
        return user_group_db

    async def get_user_group_members(self, user_group_id: UUID) -> List[models.User]:
        """
        Get all members from a user group.
        """

        query = select(models.User).join(models.User.groups).filter(models.UserGroup.user_group_id == user_group_id)

        result = await self._db_session.execute(query)
        return list(result.scalars().all())
