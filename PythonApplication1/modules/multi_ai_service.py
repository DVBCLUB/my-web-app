"""
Unified AI service for Gemini, ChatGPT, Claude, and Copilot-style endpoints.

This module keeps external AI integrations behind one small interface so the
UI does not grow a separate code path for every provider.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

import config
from modules.ai_service import GeminiAIService


@dataclass
class AIProviderInfo:
    name: str
    label: str
    icon: str
    is_configured: bool
    last_error: str = ""


class BaseAIProvider:
    name = "base"
    label = "AI"
    icon = "AI"

    def __init__(self, api_key: str = "", model: str = "", system_prompt: str = ""):
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.last_error = ""
        self.chat_history: List[Dict[str, str]] = []

    @property
    def is_initialized(self) -> bool:
        return bool(self.api_key)

    def is_ready(self) -> bool:
        return self.is_initialized

    def set_api_key(self, api_key: str) -> bool:
        self.api_key = api_key.strip()
        self.last_error = ""
        self.clear_history()
        return self.is_ready()

    def add_message(self, role: str, content: str) -> None:
        self.chat_history.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        max_history = int(getattr(config, "AI_MAX_HISTORY", 20) or 20)
        if len(self.chat_history) > max_history:
            del self.chat_history[: len(self.chat_history) - max_history]

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.chat_history)

    def clear_history(self) -> None:
        self.chat_history.clear()

    def send_message(self, user_message: str, callback: Optional[Callable] = None) -> Optional[str]:
        raise NotImplementedError


class GeminiProvider(BaseAIProvider):
    name = "gemini"
    label = "Gemini"
    icon = "G"

    def __init__(self):
        self.service = GeminiAIService()
        self.last_error = ""

    @property
    def api_key(self) -> str:
        return self.service.api_key

    @property
    def model(self) -> str:
        return self.service.model_name

    @property
    def chat_history(self):
        return self.service.chat_history

    @property
    def is_initialized(self) -> bool:
        return self.service.is_initialized

    def is_ready(self) -> bool:
        return self.service.is_ready()

    def set_api_key(self, api_key: str) -> bool:
        ok = self.service.set_api_key(api_key)
        self.last_error = self.service.last_error or ""
        return ok

    def get_history(self) -> List[Dict[str, str]]:
        return self.service.get_history()

    def clear_history(self) -> None:
        self.service.clear_history()

    def send_message(self, user_message: str, callback: Optional[Callable] = None) -> Optional[str]:
        response = self.service.send_message(user_message, callback)
        self.last_error = self.service.last_error or ""
        return response


class HttpChatProvider(BaseAIProvider):
    base_url = ""
    auth_header = "Authorization"
    auth_prefix = "Bearer "

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            self.auth_header: f"{self.auth_prefix}{self.api_key}",
        }

    def _messages(self, user_message: str) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        for item in self.chat_history[-int(getattr(config, "AI_MAX_HISTORY", 20) or 20) :]:
            if item.get("role") in ("user", "assistant"):
                messages.append({"role": item["role"], "content": item.get("content", "")})
        messages.append({"role": "user", "content": user_message})
        return messages

    def _post_json(self, payload: Dict) -> Dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base_url, data=data, headers=self._headers(), method="POST")
        timeout = int(getattr(config, "AI_RESPONSE_TIMEOUT", 30) or 30)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(self._format_http_error(exc.code, body)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Khong ket noi duoc {self.label}: {exc.reason}") from exc

    def _format_http_error(self, status_code: int, body: str) -> str:
        message = body
        code = ""
        try:
            payload = json.loads(body)
            error = payload.get("error") or {}
            message = error.get("message") or body
            code = error.get("code") or error.get("type") or ""
        except Exception:
            pass

        lowered = f"{code} {message}".lower()
        if status_code == 429 and ("quota" in lowered or "insufficient" in lowered):
            return (
                f"{self.label}: tai khoan/API key da het quota hoac chua bat billing.\n"
                "Vui long vao trang billing/usage cua nha cung cap de nap quota, bat thanh toan, "
                "hoac dung API key khac."
            )
        if status_code in (401, 403):
            return f"{self.label}: API key khong hop le hoac khong co quyen dung model {self.model}."
        if status_code == 404:
            return f"{self.label}: khong tim thay model/end-point {self.model}. Vui long kiem tra cau hinh model."
        if status_code >= 500:
            return f"{self.label}: dich vu dang loi tam thoi HTTP {status_code}. Thu lai sau."
        return f"{self.label} HTTP {status_code}: {message[:300]}"

    def send_message(self, user_message: str, callback: Optional[Callable] = None) -> Optional[str]:
        if not self.is_ready():
            self.last_error = f"Chua cau hinh API key cho {self.label}"
            return None
        try:
            payload = {
                "model": self.model,
                "messages": self._messages(user_message),
                "max_tokens": 2000,
            }
            data = self._post_json(payload)
            answer = data["choices"][0]["message"]["content"].strip()
            self.add_message("user", user_message)
            self.add_message("assistant", answer)
            if callback:
                callback(answer)
            return answer
        except Exception as exc:
            self.last_error = str(exc)
            return None


class OpenAIProvider(HttpChatProvider):
    name = "chatgpt"
    label = "ChatGPT"
    icon = "C"
    base_url = "https://api.openai.com/v1/chat/completions"


class ClaudeProvider(BaseAIProvider):
    name = "claude"
    label = "Claude"
    icon = "A"
    base_url = "https://api.anthropic.com/v1/messages"

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def _messages(self, user_message: str) -> List[Dict[str, str]]:
        messages = []
        for item in self.chat_history[-int(getattr(config, "AI_MAX_HISTORY", 20) or 20) :]:
            if item.get("role") in ("user", "assistant"):
                messages.append({"role": item["role"], "content": item.get("content", "")})
        messages.append({"role": "user", "content": user_message})
        return messages

    def send_message(self, user_message: str, callback: Optional[Callable] = None) -> Optional[str]:
        if not self.is_ready():
            self.last_error = "Chua cau hinh API key cho Claude"
            return None
        try:
            request = urllib.request.Request(
                self.base_url,
                data=json.dumps(
                    {
                        "model": self.model,
                        "system": self.system_prompt,
                        "messages": self._messages(user_message),
                        "max_tokens": 2000,
                    }
                ).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            timeout = int(getattr(config, "AI_RESPONSE_TIMEOUT", 30) or 30)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            answer = "".join(part.get("text", "") for part in data.get("content", [])).strip()
            self.add_message("user", user_message)
            self.add_message("assistant", answer)
            if callback:
                callback(answer)
            return answer
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            self.last_error = HttpChatProvider._format_http_error(self, exc.code, body)
            return None
        except Exception as exc:
            self.last_error = f"Loi Claude: {exc}"
            return None


class CopilotProvider(HttpChatProvider):
    name = "copilot"
    label = "Copilot"
    icon = "P"

    def __init__(self, api_key: str = "", model: str = "", system_prompt: str = ""):
        super().__init__(api_key, model, system_prompt)
        self.base_url = os.getenv(
            "COPILOT_BASE_URL",
            getattr(config, "COPILOT_BASE_URL", "https://models.github.ai/inference/chat/completions"),
        )


class MultiAIService:
    def __init__(self):
        prompt = getattr(config, "AI_SYSTEM_PROMPT", "")
        self.providers: Dict[str, BaseAIProvider] = {
            "gemini": GeminiProvider(),
            "chatgpt": OpenAIProvider(
                os.getenv("OPENAI_API_KEY", getattr(config, "OPENAI_API_KEY", "")),
                os.getenv("OPENAI_MODEL", getattr(config, "OPENAI_MODEL", "gpt-4o-mini")),
                prompt,
            ),
            "claude": ClaudeProvider(
                os.getenv("ANTHROPIC_API_KEY", getattr(config, "ANTHROPIC_API_KEY", "")),
                os.getenv("CLAUDE_MODEL", getattr(config, "CLAUDE_MODEL", "claude-3-5-haiku-latest")),
                prompt,
            ),
            "copilot": CopilotProvider(
                os.getenv("COPILOT_API_KEY", getattr(config, "COPILOT_API_KEY", "")),
                os.getenv("COPILOT_MODEL", getattr(config, "COPILOT_MODEL", "openai/gpt-4.1-mini")),
                prompt,
            ),
        }
        self.active_name = os.getenv("AI_PROVIDER", getattr(config, "AI_DEFAULT_PROVIDER", "gemini"))
        if self.active_name not in self.providers:
            self.active_name = "gemini"

    def list_providers(self) -> List[AIProviderInfo]:
        return [
            AIProviderInfo(
                name=p.name,
                label=p.label,
                icon=p.icon,
                is_configured=p.is_initialized,
                last_error=getattr(p, "last_error", "") or "",
            )
            for p in self.providers.values()
        ]

    def get_active_name(self) -> str:
        return self.active_name

    def get_active_provider(self) -> BaseAIProvider:
        return self.providers[self.active_name]

    def set_active_provider(self, name: str) -> None:
        if name in self.providers:
            self.active_name = name

    def set_api_key(self, provider_name: str, api_key: str) -> bool:
        if provider_name not in self.providers:
            return False
        return self.providers[provider_name].set_api_key(api_key)

    def validate_api_key(self, provider_name: str, api_key: str) -> tuple[bool, str]:
        if provider_name not in self.providers:
            return False, "Nha cung cap AI khong hop le."
        provider = self.providers[provider_name]
        previous_key = getattr(provider, "api_key", "") or ""
        if not provider.set_api_key(api_key):
            if previous_key:
                provider.set_api_key(previous_key)
            return False, getattr(provider, "last_error", "") or "Khong khoi tao duoc API key."
        response = provider.send_message("Tra loi dung mot tu: OK")
        if response:
            provider.clear_history()
            return True, "Ket noi API thanh cong."
        error = getattr(provider, "last_error", "") or "API khong tra loi."
        provider.set_api_key(previous_key)
        return False, error

    def is_ready(self) -> bool:
        return self.get_active_provider().is_ready()

    @property
    def is_initialized(self) -> bool:
        return self.get_active_provider().is_initialized

    @property
    def last_error(self) -> str:
        return getattr(self.get_active_provider(), "last_error", "") or ""

    def clear_history(self) -> None:
        self.get_active_provider().clear_history()

    def get_history(self) -> List[Dict[str, str]]:
        return self.get_active_provider().get_history()

    def send_message(
        self,
        user_message: str,
        callback: Optional[Callable] = None,
        provider_name: Optional[str] = None,
    ) -> Optional[str]:
        provider = self.providers.get(provider_name or self.active_name)
        if not provider:
            return None
        return provider.send_message(user_message, callback)

    def compare(self, user_message: str) -> Dict[str, str]:
        answers = {}
        for name, provider in self.providers.items():
            if not provider.is_initialized:
                answers[name] = f"Chua cau hinh API key cho {provider.label}."
                continue
            answers[name] = provider.send_message(user_message) or provider.last_error or "Khong co phan hoi."
        return answers


_multi_ai_service: Optional[MultiAIService] = None


def get_multi_ai_service() -> MultiAIService:
    global _multi_ai_service
    if _multi_ai_service is None:
        _multi_ai_service = MultiAIService()
    return _multi_ai_service
