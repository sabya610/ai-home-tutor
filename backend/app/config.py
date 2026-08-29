"""Application configuration loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "AI Home Tutor"

    # ai_mode: "auto" runs a role for real when it has a usable target (an API
    # key or a custom endpoint), otherwise mock. Force all roles with "openai"
    # or "mock".
    ai_mode: str = "auto"

    # Shared OpenAI defaults, used when a per-role value below is blank.
    openai_api_key: str = ""
    openai_base_url: str = ""
    # TLS to OpenAI behind a corporate proxy that intercepts HTTPS: point this at
    # the proxy's root CA (PEM) so verification passes. Dev-only escape hatch:
    # openai_insecure_skip_verify disables verification entirely.
    openai_ca_bundle: str = ""
    openai_insecure_skip_verify: bool = False

    # Vision role (handwriting OCR) — needs a vision-capable model.
    vision_model: str = "gpt-4o"
    vision_base_url: str = ""
    vision_api_key: str = ""

    # Tutor role (reasoning, scoring, explanations) — may be a cluster-hosted
    # llama3 exposed as an OpenAI-compatible endpoint (rag-app / llama.cpp).
    tutor_model: str = "gpt-4o-mini"
    tutor_base_url: str = ""
    tutor_api_key: str = ""
    tutor_json_mode: str = "auto"  # auto | json | prompt
    # Model used for the "cloud" tutor mode when the default tutor is a custom
    # endpoint (so the UI can offer OpenAI as an alternative). GPT-5.6 Luna;
    # override with CLOUD_TUTOR_MODEL if the exact model id differs.
    cloud_tutor_model: str = "gpt-5.6-luna"
    # Cap tutor response length (keeps slow local models responsive).
    tutor_max_tokens: int = 512

    db_path: str = "data/tutor.db"

    # Optional Tapo C201 RTSP source, e.g.
    # rtsp://user:pass@192.168.1.50:554/stream1
    tapo_rtsp_url: str = ""

    cors_origins: str = "*"

    def vision_target(self) -> tuple[str, str]:
        """(base_url, api_key) for the vision role."""
        return (
            self.vision_base_url or self.openai_base_url,
            self.vision_api_key or self.openai_api_key,
        )

    def tutor_target(self) -> tuple[str, str]:
        """(base_url, api_key) for the tutor role."""
        return (
            self.tutor_base_url or self.openai_base_url,
            self.tutor_api_key or self.openai_api_key,
        )

    def _role_mock(self, base_url: str, api_key: str) -> bool:
        if self.ai_mode == "mock":
            return True
        if self.ai_mode == "openai":
            return False
        return not (bool(base_url) or bool(api_key))

    def vision_mock(self) -> bool:
        return self._role_mock(*self.vision_target())

    def tutor_mock(self) -> bool:
        return self._role_mock(*self.tutor_target())

    def tutor_uses_json_mode(self) -> bool:
        """Whether to request native JSON output (response_format).

        OpenAI supports it; many llama.cpp builds reject it, so for a custom
        tutor endpoint we default to prompt-based JSON instead.
        """
        if self.tutor_json_mode == "json":
            return True
        if self.tutor_json_mode == "prompt":
            return False
        base_url, _ = self.tutor_target()
        return not bool(base_url)

    def tutor_mode_targets(self) -> dict[str, dict]:
        """Named tutor providers the UI can pick from -> resolved target.

        The frontend only ever sends a mode *name*; URLs/keys stay server-side.
        """
        mock_target = {
            "label": "Offline demo",
            "base_url": "",
            "api_key": "",
            "model": "mock",
            "json": False,
        }
        if self.ai_mode == "mock":
            return {"mock": mock_target}

        modes: dict[str, dict] = {}
        if self.tutor_base_url:
            modes["cluster"] = {
                "label": f"Cluster ({self.tutor_model})",
                "base_url": self.tutor_base_url,
                "api_key": self.tutor_api_key or self.openai_api_key,
                "model": self.tutor_model,
                "json": self.tutor_json_mode == "json",
            }
        if self.openai_api_key or self.openai_base_url:
            cloud_model = self.tutor_model if not self.tutor_base_url else self.cloud_tutor_model
            modes["cloud"] = {
                "label": f"Cloud ({cloud_model})",
                "base_url": self.openai_base_url,
                "api_key": self.openai_api_key,
                "model": cloud_model,
                "json": self.tutor_json_mode != "prompt" and not self.openai_base_url,
            }
        modes["mock"] = mock_target
        return modes

    def default_tutor_mode(self) -> str:
        if self.ai_mode == "mock":
            return "mock"
        if self.tutor_base_url:
            return "cluster"
        if self.openai_api_key or self.openai_base_url:
            return "cloud"
        return "mock"

    def resolve_tutor_mode(self, mode: str | None) -> str:
        """Name of the tutor mode that will actually be used (no side effects)."""
        if not mode or mode == "auto" or mode not in self.tutor_mode_targets():
            return self.default_tutor_mode()
        return mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
