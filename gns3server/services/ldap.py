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

"""
LDAP and Active Directory authentication service.

Provides directory authentication, user attribute retrieval, and group-to-RBAC
mapping using pure-Python ldap3. Blocking network I/O operations are run in a
worker thread pool to preserve FastAPI's async event loop.
"""

import asyncio
import logging
import os
import re
import ssl
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ldap3 import ALL, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from gns3server.config import Config
from gns3server.schemas.config import LDAPSettings

log = logging.getLogger(__name__)

# truststore on macOS/Windows enforces OS keychain certificate validation even when
# verify_mode is explicitly configured as ssl.CERT_NONE. Ensure CERT_NONE is respected across platforms:
try:
    import truststore._api as trust_api

    if not getattr(trust_api, "_gns3_cert_none_patched", False):
        orig_verify = trust_api._verify_peercerts

        def _safe_verify_peercerts(sock_or_sslobj, server_hostname=None):
            ctx = getattr(sock_or_sslobj, "context", None)
            if ctx and getattr(ctx, "verify_mode", None) == ssl.CERT_NONE:
                return
            return orig_verify(sock_or_sslobj, server_hostname=server_hostname)

        trust_api._verify_peercerts = _safe_verify_peercerts
        trust_api._gns3_cert_none_patched = True
except Exception:
    pass


def _format_ldap_error(e: Exception) -> str:
    """
    Format LDAPException or nested socket errors into clean, human-readable strings.
    """
    current: Any = e
    while hasattr(current, "args") and current.args:
        first = current.args[0]
        if isinstance(first, (tuple, list)) and first:
            current = first[0]
        elif isinstance(first, Exception):
            current = first
        else:
            current = first
            break
    msg = str(current)
    for artifact in ("('", "')", '("', '")', "',)", '",)', "\\'"):
        msg = msg.replace(artifact, "")
    return msg.strip("(),'\" ")


@dataclass
class LDAPUserProfile:
    """
    Profile information retrieved from LDAP upon successful authentication.
    """

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    is_superadmin: bool = False


def _unescape_rfc4514(val: str) -> str:
    """
    Unescape RFC 4514 escaped characters and hex octets in an RDN attribute value.
    Handles \\+, \\", \\\\, \\<, \\>, \\;, \\=, escaped spaces, and \\XX hex octets.
    """
    val = re.sub(r"\\([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), val)
    val = re.sub(r"\\([ +\",;<=>\\#])", r"\1", val)
    return val


def _extract_cn(dn_or_name: str) -> str:
    """
    Extract the Common Name (CN) from an LDAP Distinguished Name,
    or return the input unchanged if it is not a DN. Handles RFC 4514
    character and hex octet escapes.
    """
    if not dn_or_name:
        return ""
    clean = dn_or_name.strip()
    match = re.search(r"(?:^|,\s*)cn=((?:\\.|[^,])+)", clean, re.IGNORECASE)
    if match:
        raw = re.sub(r"(?<!\\) +$", "", match.group(1).lstrip(" "))
        return _unescape_rfc4514(raw)
    return clean


def _extract_entry_groups(user_entry: Any) -> Set[str]:
    """
    Extract raw group identifiers from memberOf/member user entry attributes.
    """
    groups: Set[str] = set()
    for attr_name in ("memberOf", "memberof", "member", "groups"):
        if not hasattr(user_entry, attr_name):
            continue
        attr = getattr(user_entry, attr_name)
        values = getattr(attr, "values", None) or getattr(attr, "value", None)
        if isinstance(values, (list, tuple, set)):
            for val in values:
                groups.add(str(val))
        elif values:
            groups.add(str(values))
    return groups


def _search_directory_groups(conn: Connection, user_dn: str, clean_username: str, settings: LDAPSettings) -> Set[str]:
    """
    Search for group objects in the directory matching the user.
    """
    groups: Set[str] = set()
    search_base = settings.group_search_base or settings.base_dn
    if not (settings.group_search_filter and search_base):
        return groups

    clean_user_dn = escape_filter_chars(user_dn)
    grp_filter = settings.group_search_filter.format(user_dn=clean_user_dn, username=clean_username)
    try:
        conn.search(
            search_base=search_base,
            search_filter=grp_filter,
            attributes=["cn", "sAMAccountName", "name", "distinguishedName"],
            size_limit=100,
        )
        for entry in conn.entries:
            groups.add(entry.entry_dn)
            for attr in ("cn", "sAMAccountName", "name"):
                val = getattr(entry, attr, None)
                if val and val.value:
                    groups.add(str(val.value))
    except Exception as e:
        log.warning("LDAP group search query failed for %s: %s", clean_username, e)

    # Active Directory recursive nested group search fallback if standard search found nothing
    if not groups and "objectclass=group" in (settings.group_search_filter or "").lower():
        ad_recursive_filter = f"(&(objectClass=group)(member:1.2.840.113556.1.4.1941:={clean_user_dn}))"
        try:
            conn.search(
                search_base=search_base,
                search_filter=ad_recursive_filter,
                attributes=["cn", "sAMAccountName", "name"],
                size_limit=100,
            )
            for entry in conn.entries:
                groups.add(entry.entry_dn)
                for attr in ("cn", "sAMAccountName", "name"):
                    val = getattr(entry, attr, None)
                    if val and val.value:
                        groups.add(str(val.value))
        except Exception as e:
            log.debug("LDAP AD recursive group search skipped: %s", e)

    return groups


def _map_to_user_groups(raw_groups: Set[str], group_mapping: Dict[str, str], default_group: str) -> List[str]:
    """
    Map raw LDAP group names/DNs to configured GNS3 UserGroups.
    """
    mapped_groups: List[str] = []
    for raw_group in raw_groups:
        cn = _extract_cn(raw_group)
        target_group = None
        for map_key, map_val in group_mapping.items():
            if map_key.lower() in (raw_group.lower(), cn.lower(), raw_group.strip().lower()):
                target_group = map_val
                break
        if target_group and target_group not in mapped_groups:
            mapped_groups.append(target_group)

    if not mapped_groups and default_group:
        mapped_groups.append(default_group)
    return mapped_groups


def _is_superadmin_member(raw_groups: Set[str], superadmin_groups: List[str]) -> bool:
    """
    Check if any raw group or its CN matches configured superadmin directory groups.
    """
    if not superadmin_groups:
        return False
    targets = {s.strip().lower() for s in superadmin_groups if s.strip()}
    for raw_group in raw_groups:
        cn = _extract_cn(raw_group).lower()
        if raw_group.strip().lower() in targets or cn in targets:
            return True
    return False


class LDAPService:
    """
    Asynchronous LDAP/Active Directory service.
    """

    def __init__(self, server: Optional[Server] = None, client_strategy: str = "SYNC") -> None:
        self._server = server
        self._client_strategy = client_strategy

    def _create_server(self, settings: LDAPSettings) -> Server:
        use_ssl = settings.uri.startswith("ldaps://")
        tls_config = None

        if use_ssl or settings.start_tls:
            validate_cert = ssl.CERT_REQUIRED if settings.verify_cert else ssl.CERT_NONE
            ca_file = settings.ca_cert_file if settings.ca_cert_file and os.path.exists(settings.ca_cert_file) else None
            tls_config = Tls(validate=validate_cert, ca_certs_file=ca_file)

        return Server(
            settings.uri,
            use_ssl=use_ssl,
            tls=tls_config,
            connect_timeout=settings.timeout,
            get_info=ALL,
        )

    def _create_connection(
        self, server: Server, user: Optional[str], password: Optional[str], timeout: int
    ) -> Connection:
        return Connection(
            server,
            user=user,
            password=password,
            auto_bind=False,
            auto_referrals=False,
            receive_timeout=timeout,
            client_strategy=self._client_strategy,
        )

    def _bind_connection(self, conn: Connection, start_tls: bool, uri: str) -> bool:
        if start_tls and not uri.startswith("ldaps://"):
            try:
                conn.open()
                if not conn.start_tls():
                    log.error("LDAP StartTLS negotiation was rejected by server")
                    return False
            except Exception as e:
                log.error("LDAP StartTLS negotiation failed: %s", e)
                return False
        return bool(conn.bind())

    def _resolve_groups(
        self,
        conn: Connection,
        user_entry: Any,
        user_dn: str,
        clean_username: str,
        settings: LDAPSettings,
    ) -> Tuple[List[str], bool]:
        raw_groups = _extract_entry_groups(user_entry)
        # In Active Directory, user_entry already includes all memberOf groups.
        # Skip slow, domain-wide directory queries if groups were already extracted from the user entry.
        if raw_groups:
            searched_groups: Set[str] = set()
        else:
            searched_groups = _search_directory_groups(conn, user_dn, clean_username, settings)

        all_raw_groups = raw_groups | searched_groups
        mapped = _map_to_user_groups(all_raw_groups, settings.group_mapping or {}, settings.default_group)
        is_superadmin = _is_superadmin_member(all_raw_groups, settings.superadmin_groups or [])
        log.info(
            "LDAP group resolution for user '%s': memberOf=%s, directory_search=%s -> total_raw=%s -> mapped_to_gns3=%s, is_superadmin=%s (configured mapping: %s, default: '%s', superadmin_groups: %s)",
            clean_username,
            raw_groups,
            searched_groups,
            all_raw_groups,
            mapped,
            is_superadmin,
            settings.group_mapping,
            settings.default_group,
            settings.superadmin_groups,
        )
        return mapped, is_superadmin

    def _verify_user_credentials(self, server: Server, user_dn: str, password: str, settings: LDAPSettings) -> bool:
        user_conn = self._create_connection(server, user_dn, password, settings.timeout)
        try:
            return self._bind_connection(user_conn, settings.start_tls, settings.uri)
        except Exception as e:
            log.warning("LDAP user bind error for %s: %s", user_dn, e)
            return False
        finally:
            if user_conn.bound:
                user_conn.unbind()

    def _extract_profile(
        self,
        conn: Connection,
        user_entry: Any,
        username: str,
        user_dn: str,
        clean_username: str,
        settings: LDAPSettings,
    ) -> LDAPUserProfile:
        canonical_username = None

        # 1. Primary: configured user_attr_username attribute
        if settings.user_attr_username:
            user_attr = getattr(user_entry, settings.user_attr_username, None)
            if user_attr and user_attr.value:
                canonical_username = str(user_attr.value).strip()

        # 2. Secondary fallback across standard directory attributes
        if not canonical_username:
            for fallback_attr in ("sAMAccountName", "userPrincipalName", "uid", "cn"):
                attr_val = getattr(user_entry, fallback_attr, None)
                if attr_val and attr_val.value:
                    canonical_username = str(attr_val.value).strip()
                    break

        # 3. Last resort: raw typed login string
        if not canonical_username:
            canonical_username = username.strip()

        email = None
        if settings.user_attr_email:
            email_attr = getattr(user_entry, settings.user_attr_email, None)
            if email_attr and email_attr.value:
                email = str(email_attr.value).strip().lower()

        if not email:
            for fallback_email in ("mail", "userPrincipalName"):
                em_val = getattr(user_entry, fallback_email, None)
                if em_val and em_val.value and "@" in str(em_val.value):
                    email = str(em_val.value).strip().lower()
                    break

        full_name = None
        fn_attr = getattr(user_entry, settings.user_attr_fullname, None)
        if fn_attr and fn_attr.value:
            full_name = str(fn_attr.value).strip()

        groups, is_superadmin = self._resolve_groups(conn, user_entry, user_dn, clean_username, settings)
        log.info(
            "Extracted LDAP profile for '%s': canonical_username='%s', email='%s', full_name='%s', is_superadmin=%s",
            username,
            canonical_username,
            email,
            full_name,
            is_superadmin,
        )
        return LDAPUserProfile(
            username=canonical_username,
            email=email,
            full_name=full_name,
            groups=groups,
            is_superadmin=is_superadmin,
        )

    def _sync_authenticate(self, username: str, password: str, settings: LDAPSettings) -> Optional[LDAPUserProfile]:
        if not username or not password:
            return None

        clean_username = escape_filter_chars(username)
        server = self._server or self._create_server(settings)

        bind_user = settings.bind_dn
        bind_password = settings.bind_password.get_secret_value() if settings.bind_password else None

        conn = self._create_connection(server, bind_user, bind_password, settings.timeout)
        try:
            if not self._bind_connection(conn, settings.start_tls, settings.uri):
                log.warning("LDAP service account bind failed: %s", conn.result)
                return None

            search_filter = settings.user_search_filter.format(username=clean_username)
            attributes = list(
                {
                    settings.user_attr_username,
                    settings.user_attr_email,
                    settings.user_attr_fullname,
                    "sAMAccountName",
                    "userPrincipalName",
                    "uid",
                    "cn",
                    "mail",
                    "displayName",
                    "memberOf",
                    "member",
                }
            )
            conn.search(search_base=settings.base_dn, search_filter=search_filter, attributes=attributes, size_limit=1)

            if not conn.entries:
                log.info("LDAP user '%s' not found with filter: %s", clean_username, search_filter)
                return None

            user_entry = conn.entries[0]
            user_dn = user_entry.entry_dn

            if not self._verify_user_credentials(server, user_dn, password, settings):
                log.info("LDAP credential verification failed for user DN: %s", user_dn)
                return None

            return self._extract_profile(conn, user_entry, username, user_dn, clean_username, settings)

        except LDAPException as e:
            log.warning("LDAP protocol error during authentication: %s", e)
            return None
        except Exception as e:
            log.warning("Unexpected error during LDAP authentication for %s: %s", clean_username, e)
            return None
        finally:
            if conn.bound:
                conn.unbind()

    async def authenticate(
        self, username: str, password: str, settings: Optional[LDAPSettings] = None
    ) -> Optional[LDAPUserProfile]:
        """
        Authenticate against LDAP/Active Directory in a worker thread.
        """
        if settings is None:
            settings = Config.instance().settings.LDAP

        if not settings.enabled:
            return None

        if not username or not password:
            return None

        return await asyncio.to_thread(self._sync_authenticate, username, password, settings)

    def _sync_test_connection(self, settings: LDAPSettings) -> Dict[str, Any]:
        """
        Synchronously attempt binding and canary search against the LDAP directory.
        """
        import time

        t0 = time.perf_counter()
        server = self._server or self._create_server(settings)
        bind_user = settings.bind_dn
        bind_password = settings.bind_password.get_secret_value() if settings.bind_password else None

        conn = self._create_connection(server, bind_user, bind_password, settings.timeout)
        try:
            if not self._bind_connection(conn, settings.start_tls, settings.uri):
                latency = round((time.perf_counter() - t0) * 1000, 2)
                error_desc = (
                    str(conn.result.get("description", "Bind failed")) if conn.result else "Connection or bind failed"
                )
                return {
                    "status": "error",
                    "bind_successful": False,
                    "user_search_successful": False,
                    "users_found": 0,
                    "latency_ms": latency,
                    "message": f"Failed to bind to LDAP server: {error_desc}",
                }

            user_search_ok = False
            users_found = 0
            if settings.base_dn:
                try:
                    test_filter = settings.user_search_filter.format(username="*")
                    conn.search(
                        search_base=settings.base_dn,
                        search_filter=test_filter,
                        attributes=[settings.user_attr_username],
                        size_limit=5,
                    )
                    user_search_ok = True
                    users_found = len(conn.entries)
                except Exception as e:
                    log.warning("LDAP test search error: %s", e)
                    user_search_ok = False

            latency = round((time.perf_counter() - t0) * 1000, 2)
            msg = "Directory server bind successful"

            return {
                "status": "success",
                "bind_successful": True,
                "user_search_successful": user_search_ok,
                "users_found": users_found,
                "latency_ms": latency,
                "message": msg,
            }

        except LDAPException as e:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "status": "error",
                "bind_successful": False,
                "user_search_successful": False,
                "users_found": 0,
                "latency_ms": latency,
                "message": f"LDAP protocol error: {_format_ldap_error(e)}",
            }
        except Exception as e:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "status": "error",
                "bind_successful": False,
                "user_search_successful": False,
                "users_found": 0,
                "latency_ms": latency,
                "message": f"Connection error: {_format_ldap_error(e)}",
            }
        finally:
            if conn.bound:
                conn.unbind()

    async def test_connection(self, settings: Optional[LDAPSettings] = None) -> Dict[str, Any]:
        """
        Test connection and canary query against LDAP server in a worker thread.
        """
        if settings is None:
            settings = Config.instance().settings.LDAP

        return await asyncio.to_thread(self._sync_test_connection, settings)
