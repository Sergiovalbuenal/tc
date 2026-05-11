# -*- coding: utf-8 -*-
"""
Cargador de Archivos (CSV y Excel).

Este módulo es como el "portero" del dashboard: recibe los archivos, intenta 
descifrar su codificación y los prepara para que Streamlit pueda mostrarlos 
sin errores de tipos o caracteres extraños.
"""

from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from src.config import FIELD_ALIASES

# Formatos que aceptamos actualmente
SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xls"}

# Los bancos y ERPs a veces mandan archivos en formatos viejos.
# Aquí probamos los más comunes hasta que uno funcione.
CSV_ENCODINGS = (
    "utf-8-sig", # UTF-8 con BOM (común en Excel)
    "utf-8",     # Estándar moderno
    "cp1252",    # Windows occidental
    "latin1",    # ISO estándar
    "iso-8859-1",
)


def normalize_name(value: object) -> str:
    """
    Limpia un nombre de columna para que sea fácil de manejar en el código.
    Quita acentos, espacios y lo pone en minúsculas.
    """
    text = "" if value is None else str(value)
    text = text.strip().lower()
    # Quitamos acentos (ej: 'Fecha' -> 'fecha')
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # Cambiamos cualquier cosa que no sea letra o número por un guión bajo
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "columna"


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Asegura que todas las columnas del DataFrame tengan nombres limpios y únicos.
    """
    renamed: list[str] = []
    seen: dict[str, int] = {}

    for column in df.columns:
        base = normalize_name(column)
        count = seen.get(base, 0)
        seen[base] = count + 1
        renamed.append(base if count == 0 else f"{base}_{count + 1}")

    cleaned = df.copy()
    cleaned.columns = renamed
    return cleaned


def _read_csv_from_bytes(content: bytes) -> pd.DataFrame:
    """
    Intenta leer un CSV probando diferentes "idiomas" (encodings).
    Si no puede con uno, salta al siguiente.
    """
    last_error: Exception | None = None

    for encoding in CSV_ENCODINGS:
        try:
            return pd.read_csv(
                io.BytesIO(content),
                encoding=encoding,
                sep=None,      # Que pandas adivine si es coma o punto y coma
                engine="python",
                on_bad_lines="skip", # Si una línea está rota, la saltamos para no frenar todo
            )
        except Exception as exc:
            last_error = exc

    raise ValueError(
        "No pude leer el CSV. Prueba guardarlo como UTF-8 o XLSX y vuelve a cargarlo."
    ) from last_error


def _read_excel_from_bytes(content: bytes, suffix: str) -> pd.DataFrame:
    """
    Lee archivos de Excel (.xlsx o .xls).
    """
    if suffix == ".xls":
        return pd.read_excel(io.BytesIO(content), sheet_name=0)
    return pd.read_excel(io.BytesIO(content), sheet_name=0, engine="openpyxl")


def _sanitize_for_arrow(df: pd.DataFrame) -> pd.DataFrame:
    """
    ¡IMPORTANTE! Evita que el dashboard se rompa al mostrar los datos.
    Si una columna tiene mezcla de números y texto, Arrow (el motor de Streamlit) 
    falla. Aquí forzamos que todo sea texto en esas columnas problemáticas.
    """
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                # Convertimos todo a string para que Arrow no se queje
                df[col] = df[col].apply(lambda x: str(x) if pd.notnull(x) else x)
            except Exception:
                pass
    return df


def load_uploaded_file(uploaded_file: BinaryIO) -> pd.DataFrame:
    """
    Esta es la función principal que usa la página de carga.
    Recibe el archivo de Streamlit y devuelve una tabla (DataFrame) limpia.
    """
    name = getattr(uploaded_file, "name", "archivo")
    suffix = Path(name).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Formato no soportado: {suffix}. Usa {supported}.")

    # Leemos el contenido binario del archivo
    content = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()

    # Elegimos el lector según la extensión
    if suffix in {".csv", ".txt"}:
        df = _read_csv_from_bytes(content)
    else:
        df = _read_excel_from_bytes(content, suffix)

    # Quitamos filas y columnas que estén totalmente vacías
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    
    # Limpiamos los nombres de las columnas
    df = clean_column_names(df)
    
    # Sanitizamos para evitar errores de visualización
    return _sanitize_for_arrow(df)


def guess_column_mapping(df: pd.DataFrame) -> dict[str, str | None]:
    """
    Intenta "adivinar" qué columna es cada cosa (ej: cuál es la fecha).
    Usa los alias definidos en config.py para buscar coincidencias.
    """
    columns = list(df.columns)
    normalized_columns = {normalize_name(col): col for col in columns}

    mapping: dict[str, str | None] = {}
    for field, aliases in FIELD_ALIASES.items():
        match = None

        # Primero buscamos coincidencias exactas
        for alias in aliases:
            normalized_alias = normalize_name(alias)
            if normalized_alias in normalized_columns:
                match = normalized_columns[normalized_alias]
                break

        # Si no hay exacta, buscamos si alguna columna "contiene" la palabra clave
        if match is None:
            for column in columns:
                clean_col = normalize_name(column)
                if any(normalize_name(alias) in clean_col for alias in aliases):
                    match = column
                    break

        mapping[field] = match

    return mapping


def get_column_options(df: pd.DataFrame) -> list[str]:
    """
    Devuelve la lista de columnas disponibles más la opción 'No usar'.
    """
    return ["No usar"] + list(df.columns)
