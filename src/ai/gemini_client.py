from __future__ import annotations

import os
import time
from dataclasses import dataclass

try:
    # SDK oficial (google-genai). La forma recomendada en docs es: from google import genai
    from google import genai  # type: ignore
except Exception:  # noqa: BLE001
    genai = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GeminiConfig:
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_output_tokens: int = 1024


def _default_fallback_models() -> list[str]:
    return [
        os.getenv("GEMINI_MODEL_FALLBACK", "gemini-2.0-flash"),
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]


def _is_retryable_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    if "503" in text or "unavailable" in text:
        return True
    if "429" in text or "resource exhausted" in text or "rate limit" in text:
        return True
    if "500" in text or "internal" in text:
        return True
    return False


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


class GeminiClient:
    def __init__(self, *, api_key: str | None = None, config: GeminiConfig | None = None) -> None:
        if genai is None:
            raise RuntimeError(
                "No se encontró el SDK de Gemini. Instala dependencias en el entorno activo:\n"
                "  pip install -r requirements.txt\n"
                "Asegúrate de estar usando la .venv correcta."
            )
        api_key = api_key or _load_api_key()
        if not api_key:
            raise RuntimeError(
                "Falta configurar GEMINI_API_KEY (variable de entorno) para usar el asistente IA."
            )
        self._client = genai.Client(api_key=api_key)
        base = config or GeminiConfig()
        primary = _load_model_name()
        self._config = GeminiConfig(
            model=primary,
            temperature=base.temperature,
            max_output_tokens=base.max_output_tokens,
        )

    def generate_text(self, *, system: str, user: str) -> str:
        models_to_try = [self._config.model]
        for fb in _default_fallback_models():
            if fb and fb not in models_to_try:
                models_to_try.append(fb)

        last_error: BaseException | None = None
        for model_name in models_to_try:
            for attempt in range(5):
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=[
                            {"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]},
                        ],
                        config={
                            "temperature": self._config.temperature,
                            "max_output_tokens": self._config.max_output_tokens,
                        },
                    )
                    text = getattr(response, "text", None)
                    if not text:
                        raise RuntimeError("Gemini no devolvió texto.")
                    return text
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if _is_retryable_error(exc) and attempt < 4:
                        time.sleep(1.2 * (2**attempt))
                        continue
                    if _is_retryable_error(exc):
                        break  # siguiente modelo
                    raise
        if last_error:
            raise RuntimeError(
                "Gemini no respondió (servicio saturado o error temporal). "
                "Es el error 503/429 de Google: espera 1–2 minutos y vuelve a intentar. "
                "Opcional: define `GEMINI_MODEL=gemini-2.0-flash` en el entorno o en secrets. "
                f"Detalle: {last_error}"
            ) from last_error
        raise RuntimeError("Gemini no respondió.")


def _load_api_key() -> str | None:
    # 1) variable de entorno
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key

    # 2) Streamlit secrets (recomendado para demos sin tocar el entorno)
    try:
        import streamlit as st  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"])
        if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
            return str(st.secrets["gemini"]["api_key"])
    except Exception:  # noqa: BLE001
        return None

    return None

