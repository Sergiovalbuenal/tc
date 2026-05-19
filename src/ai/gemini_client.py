# -*- coding: utf-8 -*-
"""Proveedor Gemini (google-genai >= 0.8)."""

from __future__ import annotations

import os
import time

from src.ai.base_provider import BaseAIProvider

try:
    from google import genai  # type: ignore
except Exception:  # noqa: BLE001
    genai = None  # type: ignore[assignment]

try:
    from google.genai import types as genai_types  # type: ignore
except Exception:  # noqa: BLE001
    genai_types = None  # type: ignore[assignment]


def _load_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st  # type: ignore
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"])
        if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
            return str(st.secrets["gemini"]["api_key"])
    except Exception:  # noqa: BLE001
        pass
    return None


def _load_model_name() -> str:
    if name := os.getenv("GEMINI_MODEL"):
        return name.strip()
    try:
        import streamlit as st  # type: ignore
        if "GEMINI_MODEL" in st.secrets:
            return str(st.secrets["GEMINI_MODEL"]).strip()
        if "gemini" in st.secrets and "model" in st.secrets["gemini"]:
            return str(st.secrets["gemini"]["model"]).strip()
    except Exception:  # noqa: BLE001
        pass
    return "gemini-2.5-flash"


def _is_retryable_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(kw in text for kw in ("503", "unavailable", "429", "resource exhausted", "rate limit", "500", "internal"))


def _fallback_models(primary: str) -> list[str]:
    candidates = [primary, os.getenv("GEMINI_MODEL_FALLBACK", ""), "gemini-2.0-flash", "gemini-1.5-flash"]
    seen: list[str] = []
    for m in candidates:
        if m and m not in seen:
            seen.append(m)
    return seen


class GeminiProvider(BaseAIProvider):
    """Proveedor Gemini implementando BaseAIProvider."""

    def __init__(self, *, api_key: str | None = None) -> None:
        if genai is None:
            raise RuntimeError(
                "SDK de Gemini no encontrado. Ejecuta: pip install -r requirements.txt"
            )
        key = api_key or _load_api_key()
        if not key:
            raise RuntimeError("Falta GEMINI_API_KEY en variables de entorno o secrets.toml.")
        self._client = genai.Client(api_key=key)
        self._model = _load_model_name()

    @classmethod
    def is_available(cls) -> bool:
        if genai is None:
            return False
        return bool(_load_api_key())

    @classmethod
    def display_name(cls) -> str:
        return "Gemini (Google)"

    def generate(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        # Convertir historial al formato de google-genai: role "user"/"model"
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        if genai_types is not None:
            config = genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        else:
            # Fallback para versiones del SDK sin types
            config = {
                "system_instruction": system,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

        last_error: BaseException | None = None
        for model_name in _fallback_models(self._model):
            for attempt in range(4):
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    text = getattr(response, "text", None)
                    if not text:
                        raise RuntimeError("Gemini no devolvió texto.")
                    return text
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if _is_retryable_error(exc) and attempt < 3:
                        time.sleep(1.5 * (2 ** attempt))
                        continue
                    if _is_retryable_error(exc):
                        break  # probar siguiente modelo
                    raise

        raise RuntimeError(
            "Gemini no respondió (503/429 — servicio saturado). "
            "Espera 1-2 minutos o define GEMINI_MODEL=gemini-2.0-flash. "
            f"Detalle: {last_error}"
        ) from last_error


# Alias de compatibilidad con el código existente que usaba GeminiClient
class GeminiClient(GeminiProvider):
    def generate_text(self, *, system: str, user: str) -> str:
        return self.generate(
            system=system,
            messages=[{"role": "user", "content": user}],
        )
