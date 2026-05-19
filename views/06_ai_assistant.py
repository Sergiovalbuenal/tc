# -*- coding: utf-8 -*-
"""Vista: Asistente IA (Gemini / Claude)."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

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
  - financial: puedes usar proposal {"kind":"chart","spec":{"chart":"monthly_result|cashflow_cumulative|donut_tipo|weekday|bar_categoria_egresos|bar_categoria_ingresos", "limit":10}}
  - generic: usa proposal {"kind":"chart","spec":{"kind":"bar"|"line","x":"columna_x","y":"columna_y","agg":"sum"|"mean","title":"..."}}
    x e y deben existir en `profile.columns`; y debe estar en `numeric_columns` o ser convertible a número.
- Si pide métricas (máximo, suma, conteos, top): `kind` = "compute" con `compute`:
  {"op":"max|min|sum|mean|groupby_sum|groupby_count|value_counts|nunique|count_rows","column":"...","group_by":"...","limit":20}

Kinds permitidos: answer, propose_filter, propose_transform, propose_chart, compute, summary.

Formato de respuesta (siempre JSON válido):
{
  "kind": "...",
  "message": "texto claro para el usuario",
  "proposal": { ... },
  "compute": { ... }
}
"""


# ── Proveedores disponibles ────────────────────────────────────────────────────

def _available_providers() -> list[tuple[str, str]]:
    """Retorna lista de (key, label) para los proveedores configurados."""
    providers: list[tuple[str, str]] = []


    try:
        from src.ai.gemini_client import GeminiProvider
        if GeminiProvider.is_available():
            providers.append(("gemini", GeminiProvider.display_name()))
    except Exception as e:  # noqa: BLE001
        st.caption(f"⚠️ Gemini no cargó: `{e}`")
    try:
        from src.ai.claude_client import ClaudeProvider
        if ClaudeProvider.is_available():
            providers.append(("claude", ClaudeProvider.display_name()))
    except Exception as e:  # noqa: BLE001
        st.caption(f"⚠️ Claude no cargó: `{e}`")
    return providers


def _build_provider(key: str):
    if key == "gemini":
        from src.ai.gemini_client import GeminiProvider
        return GeminiProvider()
    if key == "claude":
        from src.ai.claude_client import ClaudeProvider
        return ClaudeProvider()
    raise ValueError(f"Proveedor desconocido: {key}")


# ── Helpers ────────────────────────────────────────────────────────────────────

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
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            candidate = parts[1].removeprefix("json").removeprefix("JSON").strip()
            text = candidate
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start: end + 1]
    return json.loads(text)


def _render_compute_result(result: dict) -> None:
    """Muestra el resultado de un cálculo como tabla cuando es posible."""
    op = result.get("op", "")
    if "top" in result:
        rows = result["top"]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            return
    if op in {"max", "min", "sum", "mean"}:
        col_name = result.get("column", "valor")
        val = result.get("value")
        st.metric(f"{op.upper()} — {col_name}", f"{val:,.4g}" if isinstance(val, float) else val)
        row = result.get("row")
        if row:
            st.dataframe(pd.DataFrame([row]), use_container_width=True)
        return
    if op in {"nunique", "count_rows"}:
        st.metric(op, result.get("value"))
        return
    # Fallback: mostrar como JSON (solo campos técnicos, no todo)
    st.json({k: v for k, v in result.items() if k != "op"})


# ── Vista principal ────────────────────────────────────────────────────────────

def render() -> None:
    st.title("🤖 Asistente IA")

    # ── Verificar proveedores ──────────────────────────────────────────────────
    available = _available_providers()
    if not available:
        st.error(
            "No hay ningún proveedor de IA configurado.\n\n"
            "Agrega tu clave API en `.streamlit/secrets.toml` o como variable de entorno:\n"
            "- **Gemini**: `GEMINI_API_KEY = \"tu-clave\"`\n"
            "- **Claude**: `ANTHROPIC_API_KEY = \"tu-clave\"`"
        )
        return

    # ── Configuración (proveedor + dataset) ───────────────────────────────────
    with st.container(border=True):
        col_prov, col_target = st.columns([1, 1])

        with col_prov:
            provider_keys = [p[0] for p in available]
            saved_provider = st.session_state.get("ai_provider", provider_keys[0])
            default_idx = provider_keys.index(saved_provider) if saved_provider in provider_keys else 0
            selected_provider = st.selectbox(
                "Proveedor de IA",
                options=provider_keys,
                format_func=lambda k: dict(available).get(k, k),
                index=default_idx,
                key="ai_provider_selector",
            )
            st.session_state.ai_provider = selected_provider

        with col_target:
            target_opts = [("clean", "Datos limpios"), ("raw", "Datos crudos")]
            saved_target = st.session_state.get("ai_target", "clean")
            target_idx = 0 if saved_target == "clean" else 1
            target = st.radio(
                "Dataset objetivo",
                options=[o[0] for o in target_opts],
                format_func=lambda k: dict(target_opts)[k],
                horizontal=True,
                index=target_idx,
                key="ai_target_radio",
            )
            st.session_state.ai_target = target

    # ── Validar datos disponibles ──────────────────────────────────────────────
    target_name, df = _get_target_df()
    if df is None or df.empty:
        if target_name == "clean":
            st.warning("No hay datos limpios. Cambia a **Datos crudos** o ejecuta el ETL primero.")
        else:
            st.warning("No hay datos crudos. Ve a **Cargar datos** y sube un archivo.")
        return

    profile = dataset_profile(df, max_rows_preview=15)
    kpis = calculate_kpis(df) if is_financial_schema(df) else None

    # Info compacta del dataset activo
    schema_tag = "Financiero" if is_financial_schema(df) else "Genérico"
    st.caption(
        f"Dataset activo: **{target_name}** · {len(df):,} filas · {len(df.columns)} columnas · esquema {schema_tag}"
    )

    with st.expander("Ver contexto enviado a la IA", expanded=False):
        st.json({"dataset": target_name, "profile": profile, "kpis": kpis or "N/A"})

    st.session_state.setdefault("ai_keep_history", False)
    st.session_state.setdefault("ai_last_user_msg", None)
    st.session_state.setdefault("ai_last_assistant_msg", None)

    # ── Controles del chat ─────────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1:
        keep_history = st.toggle("Guardar historial", value=bool(st.session_state.ai_keep_history))
        st.session_state.ai_keep_history = keep_history
    with ctrl2:
        if st.button("Limpiar chat", use_container_width=True, key="btn_clear_chat"):
            st.session_state.ai_chat_history = []
            st.session_state.ai_last_user_msg = None
            st.session_state.ai_last_assistant_msg = None
            st.rerun()
    with ctrl3:
        if st.button("Limpiar resultados", use_container_width=True, key="btn_clear_results"):
            for k in ("ai_last_proposal", "ai_preview_df", "ai_preview_chart", "ai_last_compute"):
                st.session_state[k] = None
            st.rerun()

    st.divider()

    # ── Historial de mensajes ──────────────────────────────────────────────────
    history: list[dict] = st.session_state.get("ai_chat_history", [])
    if keep_history:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    else:
        last_user = st.session_state.get("ai_last_user_msg")
        last_asst = st.session_state.get("ai_last_assistant_msg")
        if last_user:
            with st.chat_message("user"):
                st.markdown(str(last_user))
        if last_asst:
            with st.chat_message("assistant"):
                st.markdown(str(last_asst))

    user_msg = st.chat_input("Pregunta sobre tus datos (ej: 'resume el dataset', 'gráfica de ventas por mes').")
    if user_msg:
        for k in ("ai_last_proposal", "ai_preview_df", "ai_preview_chart", "ai_last_compute"):
            st.session_state[k] = None
        st.session_state.ai_last_user_msg = user_msg
        st.session_state.ai_last_assistant_msg = None

        if keep_history:
            history.append({"role": "user", "content": user_msg})
            st.session_state.ai_chat_history = history

        with st.chat_message("user"):
            st.markdown(user_msg)

        try:
            provider = _build_provider(selected_provider)
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            st.stop()

        user_context = {
            "dataset": target_name,
            "profile": profile,
            "kpis": kpis,
            "question": user_msg,
        }

        messages_to_send: list[dict] = []
        if keep_history:
            # Incluir historial previo sin el mensaje actual (ya estará al final)
            messages_to_send = [m for m in history if m != {"role": "user", "content": user_msg}]
        messages_to_send.append({
            "role": "user",
            "content": json.dumps(user_context, ensure_ascii=False, default=str),
        })

        try:
            raw = provider.generate(
                system=SYSTEM_PROMPT,
                messages=messages_to_send,
                max_tokens=4096,
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            err_text = str(exc)
            with st.chat_message("assistant"):
                st.warning(
                    f"**{dict(available).get(selected_provider, selected_provider)} no está disponible ahora mismo.**\n\n"
                    f"Verifica que la clave API esté configurada correctamente.\n\n"
                    f"Detalle: `{err_text[:400]}`"
                )
            st.session_state.ai_last_assistant_msg = f"Error: {err_text[:200]}"
            st.stop()

        try:
            payload = _safe_json_parse(raw)
        except Exception:  # noqa: BLE001
            payload = {"kind": "answer", "message": raw, "proposal": None}

        kind = payload.get("kind", "answer")
        message = payload.get("message", "")
        compute_spec = payload.get("compute")

        with st.chat_message("assistant"):
            st.markdown(message if message else "Listo.")

        reply = message if message else "Listo."
        st.session_state.ai_last_assistant_msg = reply
        if keep_history:
            history.append({"role": "assistant", "content": reply})
            st.session_state.ai_chat_history = history

        # Normalizar propuesta (Gemini a veces la pone directamente en el payload)
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

    # ── Panel de propuesta (filtro / transformación) ───────────────────────────
    proposal_dict = st.session_state.get("ai_last_proposal")
    preview_df = st.session_state.get("ai_preview_df")
    preview_chart = st.session_state.get("ai_preview_chart")
    compute_spec = st.session_state.get("ai_last_compute")

    if proposal_dict and isinstance(preview_df, pd.DataFrame):
        st.subheader("Vista previa de la propuesta")
        st.caption(f"Tipo: **{proposal_dict.get('kind', '—')}** | {len(preview_df):,} filas resultantes")
        st.dataframe(preview_df.head(100), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Aplicar cambios", type="primary", use_container_width=True, key="btn_apply"):
                _set_target_df(target_name, preview_df)
                st.session_state.ai_last_proposal = None
                st.session_state.ai_preview_df = None
                st.success("Cambios aplicados al dataset.")
                st.rerun()
        with col2:
            if st.button("❌ Descartar", use_container_width=True, key="btn_discard"):
                st.session_state.ai_last_proposal = None
                st.session_state.ai_preview_df = None
                st.info("Propuesta descartada.")
                st.rerun()

    # ── Gráfica propuesta ──────────────────────────────────────────────────────
    if proposal_dict and proposal_dict.get("kind") == "chart" and isinstance(preview_chart, dict):
        st.subheader("Gráfica generada por la IA")
        fig = build_chart(df, preview_chart)
        st.plotly_chart(fig, use_container_width=True)
        if st.button("Cerrar gráfica", key="btn_close_chart"):
            st.session_state.ai_last_proposal = None
            st.session_state.ai_preview_chart = None
            st.rerun()

    # ── Resultado de cálculo ───────────────────────────────────────────────────
    if isinstance(compute_spec, dict):
        st.subheader("Resultado del cálculo")
        result = run_compute(df, compute_spec)
        _render_compute_result(result)
        if st.button("Limpiar resultado", key="btn_clear_compute"):
            st.session_state.ai_last_compute = None
            st.rerun()

    # ── Descargables ───────────────────────────────────────────────────────────
    with st.expander("Descargables", expanded=False):
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
            profile_for_dl = dataset_profile(df, max_rows_preview=15)
            g1, g2, g3 = st.columns(3)
            with g1:
                st.download_button(
                    "Descargar CSV",
                    data=df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="dataset.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with g2:
                st.download_button(
                    "Descargar resumen Markdown",
                    data=build_generic_markdown_report(df, profile_for_dl).encode("utf-8"),
                    file_name="resumen_archivo.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with g3:
                st.download_button(
                    "Descargar perfil JSON",
                    data=json.dumps(profile_for_dl, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                    file_name="perfil_dataset.json",
                    mime="application/json",
                    use_container_width=True,
                )
