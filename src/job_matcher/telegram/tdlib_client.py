from __future__ import annotations

import asyncio
import ctypes
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from job_matcher.core.config import Settings


class TDLibConfigurationError(RuntimeError):
    pass


@dataclass
class TDLibClient:
    settings: Settings

    def __post_init__(self) -> None:
        if not self.settings.telegram_tdjson_lib_path:
            raise TDLibConfigurationError("TELEGRAM_TDJSON_LIB_PATH is not configured")
        if not self.settings.telegram_tdlib_api_id or not self.settings.telegram_tdlib_api_hash:
            raise TDLibConfigurationError("TDLib API credentials are not configured")

        lib_path = self.settings.telegram_tdjson_lib_path
        self._tdjson = ctypes.CDLL(lib_path)
        self._tdjson.td_create_client_id.restype = ctypes.c_int
        self._tdjson.td_receive.restype = ctypes.c_char_p
        self._tdjson.td_receive.argtypes = [ctypes.c_double]
        self._tdjson.td_send.argtypes = [ctypes.c_int, ctypes.c_char_p]
        self._tdjson.td_execute.restype = ctypes.c_char_p
        self._tdjson.td_execute.argtypes = [ctypes.c_char_p]
        self._client_id = self._tdjson.td_create_client_id()
        self._authorized = False
        self._extra_counter = 0
        self._pending_updates: list[dict[str, Any]] = []
        self._execute({"@type": "setLogVerbosityLevel", "new_verbosity_level": 1})

    async def authorize(self) -> None:
        await asyncio.to_thread(self._authorize_blocking)

    async def search_public_chat(self, username: str) -> dict[str, Any]:
        await self.authorize()
        return await asyncio.to_thread(self._request, {"@type": "searchPublicChat", "username": username})

    async def get_chat(self, chat_id: int) -> dict[str, Any]:
        await self.authorize()
        return await asyncio.to_thread(self._request, {"@type": "getChat", "chat_id": chat_id})

    async def get_chat_history(self, chat_id: int, from_message_id: int = 0, limit: int = 100) -> dict[str, Any]:
        await self.authorize()
        payload = {
            "@type": "getChatHistory",
            "chat_id": chat_id,
            "from_message_id": from_message_id,
            "offset": 0,
            "limit": limit,
            "only_local": False,
        }
        return await asyncio.to_thread(self._request, payload)

    def _authorize_blocking(self) -> None:
        if self._authorized:
            return
        self._request({"@type": "getAuthorizationState"})
        deadline = time.time() + 120
        while time.time() < deadline:
            update = self._receive(1.0)
            if update is None:
                continue
            if update.get("@type") != "updateAuthorizationState":
                self._pending_updates.append(update)
                continue
            state = update["authorization_state"]["@type"]
            if state == "authorizationStateWaitTdlibParameters":
                self._send(
                    {
                        "@type": "setTdlibParameters",
                        "database_directory": str(Path(self.settings.telegram_tdlib_db_dir)),
                        "files_directory": str(Path(self.settings.telegram_tdlib_files_dir)),
                        "use_message_database": True,
                        "use_secret_chats": False,
                        "api_id": self.settings.telegram_tdlib_api_id,
                        "api_hash": self.settings.telegram_tdlib_api_hash,
                        "system_language_code": "en",
                        "device_model": "Codex",
                        "system_version": "1.0",
                        "application_version": "0.1.0",
                        "enable_storage_optimizer": True,
                    }
                )
            elif state == "authorizationStateWaitPhoneNumber":
                self._send(
                    {
                        "@type": "setAuthenticationPhoneNumber",
                        "phone_number": self.settings.telegram_tdlib_phone_number,
                    }
                )
            elif state == "authorizationStateWaitCode":
                if not self.settings.telegram_tdlib_auth_code:
                    raise TDLibConfigurationError(
                        "TELEGRAM_TDLIB_AUTH_CODE is required for first-time authorization"
                    )
                self._send(
                    {
                        "@type": "checkAuthenticationCode",
                        "code": self.settings.telegram_tdlib_auth_code,
                    }
                )
            elif state == "authorizationStateWaitPassword":
                if not self.settings.telegram_tdlib_password:
                    raise TDLibConfigurationError(
                        "TELEGRAM_TDLIB_PASSWORD is required for accounts with 2FA"
                    )
                self._send(
                    {
                        "@type": "checkAuthenticationPassword",
                        "password": self.settings.telegram_tdlib_password,
                    }
                )
            elif state == "authorizationStateReady":
                self._authorized = True
                return
            elif state in {"authorizationStateLoggingOut", "authorizationStateClosing", "authorizationStateClosed"}:
                raise TDLibConfigurationError(f"TDLib authorization failed: {state}")
        raise TDLibConfigurationError("TDLib authorization timed out")

    def _request(self, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        self._extra_counter += 1
        extra = f"req-{self._extra_counter}"
        payload["@extra"] = extra
        self._send(payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            update = self._receive(1.0)
            if update is None:
                continue
            if update.get("@extra") == extra:
                if update.get("@type") == "error":
                    raise TDLibConfigurationError(update.get("message", "unknown TDLib error"))
                return update
            self._pending_updates.append(update)
        raise TDLibConfigurationError(f"TDLib request timed out for {payload['@type']}")

    def _send(self, payload: dict[str, Any]) -> None:
        self._tdjson.td_send(self._client_id, json.dumps(payload).encode("utf-8"))

    def _execute(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        raw = self._tdjson.td_execute(json.dumps(payload).encode("utf-8"))
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    def _receive(self, timeout: float) -> dict[str, Any] | None:
        if self._pending_updates:
            return self._pending_updates.pop(0)
        raw = self._tdjson.td_receive(timeout)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))
