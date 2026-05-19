# -*- coding: utf-8 -*-
"""Interfaz común para proveedores de IA."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAIProvider(ABC):
    """Contrato mínimo que debe cumplir cualquier proveedor de IA."""

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        messages: list[dict],  # [{"role": "user"|"assistant", "content": str}]
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        """Envía la conversación y devuelve el texto de respuesta."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True si el SDK y la API key están configurados."""

    @classmethod
    @abstractmethod
    def display_name(cls) -> str:
        """Nombre legible para mostrar en la UI."""
