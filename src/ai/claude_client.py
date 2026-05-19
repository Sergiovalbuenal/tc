# -*- coding: utf-8 -*-
"""Proveedor Claude (Anthropic SDK)."""

from __future__ import annotations

import os

from src.ai.base_provider import BaseAIProvider

try:
    import anthropic  # type: ignore
except Exception:  # noqa: BLE001
    anthropic = None  # type: ignore[assignment]


def _load_api_key() -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st  # type: ignore
        if "ANTHROPIC_API_KEY" in st.secrets:
            return str(st.secrets["ANTHROPIC_API_KEY"])
        if "anthropic" in st.secrets and "api_key" in st.secrets["anthropic"]:
            return str(st.secrets["anthropic"]["api_key"])
    except Exception:  # noqa: BLE001
        pass
    return None


def _load_model_name() -> str:
    if name := os.getenv("ANTHROPIC_MODEL"):
        return name.strip()
    try:
        import streamlit as st  # type: ignore
        if "ANTHROPIC_MODEL" in st.secrets:
            return str(st.secrets["ANTHROPIC_MODEL"]).strip()
    except Exception:  # noqa: BLE001
        pass
    return "claude-haiku-4-5-20251001"


class ClaudeProvider(BaseAIProvider):
    """Proveedor Claude/Anthropic implementando BaseAIProvider."""

    def __init__(self, *, api_key: str | None = None) -> None:
        if anthropic is None:
            raise RuntimeError(
                "SDK de Anthropic no encontrado. Ejecuta: pip install anthropic"
            )
        key = api_key or _load_api_key()
        if not key:
            raise RuntimeError("Falta ANTHROPIC_API_KEY en variables de entorno o secrets.toml.")
        self._client = anthropic.Anthropic(api_key=key)
        self._model = _load_model_name()

    @classmethod
    def is_available(cls) -> bool:
        if anthropic is None:
            return False
        return bool(_load_api_key())

    @classmethod
    def display_name(cls) -> str:
        return "Claude (Anthropic)"

    def generate(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,  # [{"role": "user"|"assistant", "content": str}]
            temperature=temperature,
        )
        return response.content[0].text
