# -*- coding: utf-8 -*-
"""Vista: Asistente IA (Gemini)."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.ai.gemini_client import GeminiClient
from src.ai.tools import (
    apply_filter_spec,
    apply_transform_spec,
    build_chart,
    dataset_profile,
    is_financial_schema,
    run_compute,
)
from src.kpis.financial_kpis import calculate_kpis
from src.utils.exporters import (
    build_ai_markdown_report,
    build_dashboard_html,
    build_generic_markdown_report,
)


SYSTEM_PROMPT = """Eres un asistente de datos (tablas Excel/CSV) integrado en un dashboard.
Responde al usuario en lenguaje natural dentro del campo `message`.
Cuando aplique, incluye JSON estructurado para que la app ejecute acciones; el usuario NO verá el JSON, solo `message`.

Contexto:
- El campo `profile.schema_kind` será "financial" (datos ya normalizados) o "generic" (cualquier otra tabla).
- Si es "generic", usa obligatoriamente `profile.numeric_columns`, `profile.numeric_stats`, `profile.text_summaries`,
  `profile.date_like_columns` y `profile.columns`. No inventes nombres de columnas.

Reglas:
- Nunca inventes columnas: solo las listadas en `profile.columns` o en los subcampos del perfil.
- Si el usuario pide un resumen o panorama del archivo: `kind` = "summary" o "answer" y escribe un resumen claro en `message`
  usando `numeric_stats` y `text_summaries`.
- Si pide filtrar:
  - Con schema financial: `propose_filter` con proposal {"kind":"filter","spec":{...}} (fechas/moneda/categoría/cuenta).
  - Con schema generic: `propose_filter` con proposal {"kind":"filter","spec":{"generic_filters":[...]}}
    cada regla: {"column":"nombre","op":"eq|ne|contains|in|gte|lte|notna","value":...}
    para "in", value debe ser lista de strings.
- Si pide gráfica:
  - financial: puedes usar proposal {"kind":"chart","spec":{"chart":"monthly_result|...", "limit":10}}
  - generic: usa proposal {"kind":"chart","spec":{"kind":"bar"|"line","x":"columna_x","y":"columna_y","agg":"sum"|"mean","title":"..."}}
    x e y deben existir en `profile.columns`; y debe estar en `numeric_columns` o ser convertible a número.
- Si pide métricas (máximo, suma, conteos, top): `kind` = "compute" con `compute`:
  {"op":"max|min|sum|mean|groupby_sum|groupby_count|value_counts|nunique|count_rows","column":"...","group_by":"...","limit":20}

Kinds permitidos: answer, propose_filter, propose_transform, propose_chart, compute, summary.

Formato:
{
  "kind": "...",
  "message": "texto para el usuario",
  "proposal": { ... },
  "compute": { ... }
}
"""


def _get_target_df() -> tuple[str, pd.DataFrame | None]:
    target = st.session_state.get("ai_target", "clean")
    if target == "raw":
        return "raw", st.session_state.get("raw_data")
    return "clean", st.session_state.get("clean_data")


def _set_target_df(target: str, df: pd.DataFrame) -> None:
    if target == "raw":
        st.session_state.raw_data = df
    else:
        st.session_state.clean_data = df


def _safe_json_parse(text: str) -> dict:
    text = text.strip()
    # 1) Si viene en bloque ```...```, lo extraemos.
    if "```" in text:
        parts = text.split("```")
        # Preferimos el contenido dentro del primer bloque fenced.
        if len(parts) >= 2:
            candidate = parts[1]
            candidate = candidate.removeprefix("json").removeprefix("JSON").strip()
            text = candidate

    # 2) Intentamos extraer el primer objeto JSON aunque venga con texto extra.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return json.loads(text)

def _auth_supported() -> bool:
    return hasattr(st, "user") and hasattr(st, "login") and hasattr(st, "logout")


def _is_logged_in() -> bool:
    user = getattr(st, "user", None)
    if user is None:
        return False
    return bool(getattr(user, "is_logged_in", False))


def render() -> None:
    st.title("🤖 Asistente IA (Gemini)")

    # Auth es opcional: si existe y está configurado, se muestra botón.
    # Si no existe o falla, igual dejamos usar la IA (modo simple).
    if _auth_supported() and not _is_logged_in():
        with st.expander("Acceso (opcional)", expanded=False):
            st.caption("Puedes iniciar sesión con Google, pero no es obligatorio para usar la IA en este modo.")
            if st.button("Iniciar sesión con Google"):
                st.login()

    # Selector de dataset objetivo
    target = st.radio(
        "Dataset objetivo",
        options=[("clean", "Datos limpios"), ("raw", "Datos crudos")],
        format_func=lambda x: x[1],
        horizontal=True,
        index=0 if st.session_state.get("ai_target", "clean") == "clean" else 1,
    )[0]
    st.session_state.ai_target = target

    target_name, df = _get_target_df()
    if df is None or df.empty:
        if target_name == "clean":
            st.warning("No hay datos limpios todavía. Si quieres consultar sin ETL, cambia a **Datos crudos**.")
        else:
            st.warning("No hay datos crudos. Ve a **Cargar datos** y sube un Excel/CSV.")
        return

    # contexto compacto para la IA (no mandamos todo el df)
    profile = dataset_profile(df, max_rows_preview=15)
    kpis = calculate_kpis(df) if is_financial_schema(df) else None

    with st.expander("Contexto enviado a IA (resumen)", expanded=False):
        st.json(
            {
                "dataset": target_name,
                "profile": profile,
                "kpis": kpis if kpis else "N/A (solo si el dataset ya tiene estructura financiera)",
            }
        )

    if "ai_keep_history" not in st.session_state:
        st.session_state.ai_keep_history = False
    st.session_state.setdefault("ai_last_user_msg", None)
    st.session_state.setdefault("ai_last_assistant_msg", None)

    keep_history = st.toggle("Guardar historial del chat", value=bool(st.session_state.ai_keep_history))
    st.session_state.ai_keep_history = keep_history

    # Mostrar historial (si aplica)
    history = st.session_state.get("ai_chat_history", [])
    if keep_history:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    else:
        # Sin historial, al menos mostramos el último intercambio para evitar “parpadeo”
        last_user = st.session_state.get("ai_last_user_msg")
        last_asst = st.session_state.get("ai_last_assistant_msg")
        if last_user:
            with st.chat_message("user"):
                st.markdown(str(last_user))
        if last_asst:
            with st.chat_message("assistant"):
                st.markdown(str(last_asst))

    # Controles rápidos
    top_left, top_right = st.columns([1, 1])
    with top_left:
        if st.button("Limpiar chat", use_container_width=True):
            st.session_state.ai_chat_history = []
            st.rerun()
    with top_right:
        if st.button("Limpiar resultados", use_container_width=True):
            st.session_state.ai_last_proposal = None
            st.session_state.ai_preview_df = None
            st.session_state.ai_preview_chart = None
            st.session_state.ai_last_compute = None
            st.rerun()

    user_msg = st.chat_input("Pregunta por tus datos (ej: 'resume el mes con más egresos', 'filtra COP y abril').")
    if user_msg:
        # Cada nueva pregunta reemplaza el panel de resultados (evita que se quede pegado lo anterior)
        st.session_state.ai_last_proposal = None
        st.session_state.ai_preview_df = None
        st.session_state.ai_preview_chart = None
        st.session_state.ai_last_compute = None
        st.session_state.ai_last_user_msg = user_msg
        st.session_state.ai_last_assistant_msg = None

        if keep_history:
            history.append({"role": "user", "content": user_msg})
            st.session_state.ai_chat_history = history
        with st.chat_message("user"):
            st.markdown(user_msg)

        try:
            client = GeminiClient()
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            st.stop()
        user_context = {
            "dataset": target_name,
            "profile": profile,
            "kpis": kpis,
            "question": user_msg,
        }
        # El profile puede contener Timestamps/NaN; serializamos de forma segura.
        try:
            raw = client.generate_text(
                system=SYSTEM_PROMPT,
                user=json.dumps(user_context, ensure_ascii=False, default=str),
            )
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            with st.chat_message("assistant"):
                st.warning(
                    "**Gemini no está disponible ahora mismo** (saturación temporal en Google, error 503/429).\n\n"
                    "Prueba de nuevo en 1–2 minutos. Si pasa seguido, en `secrets.toml` o variables de entorno pon:\n"
                    "`GEMINI_MODEL=gemini-2.0-flash` (u otro modelo que tengas habilitado).\n\n"
                    f"Detalle: `{err[:400]}`"
                )
            st.session_state.ai_last_assistant_msg = (
                "Gemini no disponible temporalmente (503). Reintenta en un momento."
            )
            st.stop()

        try:
            payload = _safe_json_parse(raw)
        except Exception:  # noqa: BLE001
            # Si Gemini no devolvió JSON bien formado, igual mostramos el texto al usuario.
            payload = {"kind": "answer", "message": raw, "proposal": None}

        kind = payload.get("kind", "answer")
        message = payload.get("message", "")
        compute_spec = payload.get("compute")

        # Render assistant message
        with st.chat_message("assistant"):
            st.markdown(message if message else "Listo.")

        st.session_state.ai_last_assistant_msg = message if message else "Listo."
        if keep_history:
            history.append({"role": "assistant", "content": message if message else "Listo."})
            st.session_state.ai_chat_history = history

        # Aceptamos dos formatos:
        # 1) payload.proposal = {"kind": "...", "spec": {...}}
        # 2) payload.kind = "propose_*" y payload contiene {"spec": {...}} directamente (Gemini a veces lo hace)
        proposal = payload.get("proposal")
        if not isinstance(proposal, dict) and isinstance(kind, str) and kind.startswith("propose_"):
            implied = kind.replace("propose_", "", 1)
            proposal = {"kind": "chart" if implied == "chart" else implied, "spec": payload.get("spec") or {}}

        if isinstance(proposal, dict) and proposal.get("kind") in {"filter", "transform", "chart"}:
            st.session_state.ai_last_proposal = proposal
            spec = proposal.get("spec") or {}
            if proposal["kind"] == "filter":
                st.session_state.ai_preview_df = apply_filter_spec(df, spec)
                st.session_state.ai_preview_chart = None
            elif proposal["kind"] == "transform":
                st.session_state.ai_preview_df = apply_transform_spec(df, spec)
                st.session_state.ai_preview_chart = None
            else:
                st.session_state.ai_preview_df = None
                st.session_state.ai_preview_chart = spec

        if isinstance(compute_spec, dict):
            st.session_state.ai_last_compute = compute_spec
        # No forzamos rerun: evita que desaparezcan mensajes cuando no hay historial.

    # Panel de propuesta (si existe)
    proposal_dict = st.session_state.get("ai_last_proposal")
    preview_df = st.session_state.get("ai_preview_df")
    preview_chart = st.session_state.get("ai_preview_chart")
    compute_spec = st.session_state.get("ai_last_compute")

    if proposal_dict and isinstance(preview_df, pd.DataFrame):
        st.subheader("Propuesta de IA (requiere confirmación)")
        st.json(proposal_dict)
        st.dataframe(preview_df.head(100), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Aplicar cambios", type="primary", use_container_width=True):
                _set_target_df(target_name, preview_df)
                st.session_state.ai_last_proposal = None
                st.session_state.ai_preview_df = None
                st.success("Cambios aplicados.")
                st.rerun()
        with col2:
            if st.button("Descartar", use_container_width=True):
                st.session_state.ai_last_proposal = None
                st.session_state.ai_preview_df = None
                st.info("Propuesta descartada.")
                st.rerun()

    if proposal_dict and proposal_dict.get("kind") == "chart" and isinstance(preview_chart, dict):
        st.subheader("Gráfica propuesta por la IA")
        st.json(proposal_dict)
        fig = build_chart(df, preview_chart)
        st.plotly_chart(fig, use_container_width=True)
        if st.button("Descartar gráfica"):
            st.session_state.ai_last_proposal = None
            st.session_state.ai_preview_chart = None
            st.rerun()

    if isinstance(compute_spec, dict):
        st.subheader("Cálculo (resultado)")
        result = run_compute(df, compute_spec)
        st.json(result)
        if st.button("Limpiar resultado"):
            st.session_state.ai_last_compute = None
            st.rerun()

    st.divider()
    st.subheader("Descargables (con dataset actual)")
    if is_financial_schema(df):
        col_a, col_b = st.columns(2)
        with col_a:
            md = build_ai_markdown_report(
                df,
                ai_summary="(Genera un resumen con el chat y pégalo aquí si deseas).",
                cleaning_log=st.session_state.get("cleaning_log", []),
            )
            st.download_button(
                "Descargar reporte IA (Markdown)",
                data=md.encode("utf-8"),
                file_name="reporte_ia.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_b:
            st.download_button(
                "Descargar dashboard HTML",
                data=build_dashboard_html(df),
                file_name="dashboard.html",
                mime="text/html",
                use_container_width=True,
            )
    else:
        g1, g2, g3 = st.columns(3)
        with g1:
            st.download_button(
                "Descargar CSV (datos actuales)",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name="dataset.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with g2:
            st.download_button(
                "Descargar resumen Markdown",
                data=build_generic_markdown_report(df, profile).encode("utf-8"),
                file_name="resumen_archivo.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with g3:
            st.download_button(
                "Descargar perfil JSON",
                data=json.dumps(profile, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                file_name="perfil_dataset.json",
                mime="application/json",
                use_container_width=True,
            )

