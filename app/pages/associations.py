"""
Association Rules Page V2 — Advanced Spatio-Temporal Analysis.

FP-Growth discovers frequent patterns between offense type, proximity to
USGS V2 infrastructure (police, fire, healthcare), and optionally
temporal blocks (time of day, weekday/weekend) and offense severity level.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st
from mlxtend.frequent_patterns import association_rules, fpgrowth

from app.components.background import (
    BackgroundTask,
    get_task,
    needs_recompute,
    show_progress_or_result,
)
from app.components.display import dataframe, plotly_chart
from app.components.distances import haversine_np
from app.components.filters import get_filtered_data, get_usgs_v2_layers
from app.components.utils import slugify as _slug

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_N = 10_000
TOP_OFFENSE_TYPES = 15
LIFT_THRESHOLD = 1.5
MAX_DISPLAY_ROWS = 30
TOP_SCATTER_RULES = 50
TOP_CHART_RULES = 10

# ---------------------------------------------------------------------------
# Time-block mapping
# ---------------------------------------------------------------------------
_TIME_BLOCKS = {
    range(0, 6): "MADRUGADA",
    range(6, 12): "MANANA",
    range(12, 18): "TARDE",
    range(18, 24): "NOCHE",
}

_TEMPORAL_PREFIXES = ("HORA=", "DIA=")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _hour_to_block(hour: int) -> str:
    """Map an integer hour (0-23) to a human-readable time block."""
    for rng, label in _TIME_BLOCKS.items():
        if hour in rng:
            return label
    return "NOCHE"


def _highlight_lift(row: pd.Series) -> list[str]:
    """Highlight rows with lift above threshold (dark green, bold white)."""
    style = "background-color: #1b5e20; color: #ffffff; font-weight: bold"
    return [style if row["lift"] > LIFT_THRESHOLD else "" for _ in row]


def _has_temporal(items_str: str) -> bool:
    """Return True if the items string contains temporal prefixes."""
    return any(prefix in items_str for prefix in _TEMPORAL_PREFIXES)


def _has_severity(items_str: str) -> bool:
    """Return True if the items string contains a severity level."""
    return "NIVEL=" in items_str


def _render_insight_section(
    rules_display: pd.DataFrame,
    title: str,
    icon: str,
    description: str,
    filter_fn: Callable[[str], bool],
    empty_msg: str,
    chart_title: str,
    breakdown_levels: list[str] | None = None,
) -> None:
    """Render a filtered insight section (temporal or severity).

    Applies *filter_fn* to antecedent/consequent columns, displays metrics,
    a styled table, a horizontal bar chart (top rules by lift), and an
    optional breakdown by sub-level.
    """
    st.markdown("---")
    st.subheader(f"{icon} {title}")
    st.markdown(description)

    mask = rules_display["antecedent"].apply(filter_fn) | rules_display["consequent"].apply(
        filter_fn
    )
    filtered_rules = rules_display[mask].head(MAX_DISPLAY_ROWS)

    if filtered_rules.empty:
        st.info(empty_msg)
        return

    st.metric(title, f"{int(mask.sum()):,}")
    dataframe(
        filtered_rules.style.apply(_highlight_lift, axis=1),
        hide_index=True,
    )

    # Bar chart: top rules by lift
    top_rules = filtered_rules.head(TOP_CHART_RULES)
    fig = px.bar(
        top_rules,
        x="lift",
        y="antecedent",
        orientation="h",
        color="lift",
        color_continuous_scale="YlOrRd",
        labels={"lift": "Lift", "antecedent": "Antecedente"},
        title=chart_title,
        hover_data=["consequent", "confidence"],
    )
    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        yaxis={"categoryorder": "total ascending"},
    )
    plotly_chart(fig)

    # Optional breakdown by sub-level (e.g., FELONY / MISDEMEANOR / VIOLATION)
    if breakdown_levels:
        for level in breakdown_levels:
            level_key = f"NIVEL={level}"
            level_mask = filtered_rules["antecedent"].str.contains(
                level_key, regex=False
            ) | filtered_rules["consequent"].str.contains(level_key, regex=False)
            level_rules = filtered_rules[level_mask]
            if not level_rules.empty:
                avg_lift = level_rules["lift"].mean()
                st.markdown(
                    f"- **{level}**: {len(level_rules)} reglas, lift promedio = {avg_lift:.2f}"
                )


# ---------------------------------------------------------------------------
# Page header & data loading
# ---------------------------------------------------------------------------
st.header("Reglas de Asociacion V2 - FP-Growth con USGS")
st.markdown(
    "FP-Growth V2 usa exclusivamente infraestructura **USGS V2**. Cada crimen se "
    "convierte en una transaccion con su tipo de delito y su cercania/lejanía a "
    "policia, bomberos y salud."
)

df = get_filtered_data()
usgs_layers = get_usgs_v2_layers()

if not usgs_layers:
    st.warning("No hay capas USGS V2 disponibles. Ejecuta el pipeline de referencia USGS.")
    st.stop()


# ---------------------------------------------------------------------------
# Algorithm parameters
# ---------------------------------------------------------------------------
with st.expander("Parametros del algoritmo V2", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        min_support = st.slider(
            "Soporte minimo",
            min_value=0.005,
            max_value=0.10,
            value=0.01,
            step=0.005,
            format="%.3f",
        )
    with col2:
        min_confidence = st.slider(
            "Confianza minima",
            min_value=0.5,
            max_value=1.0,
            value=0.7,
            step=0.05,
        )
    with col3:
        dist_threshold_km = st.slider(
            "Umbral CERCA/LEJOS USGS V2 (km)",
            min_value=0.1,
            max_value=2.0,
            value=0.5,
            step=0.1,
        )

    st.markdown("**Dimensiones adicionales**")
    adv_col1, adv_col2 = st.columns(2)
    with adv_col1:
        include_temporal = st.checkbox(
            "Incluir dimension temporal (bloque horario + dia)",
            value=False,
            help=(
                "Agrega items HORA=MADRUGADA/MANANA/TARDE/NOCHE y "
                "DIA=FIN_DE_SEMANA/ENTRE_SEMANA a cada transaccion."
            ),
        )
    with adv_col2:
        include_severity = st.checkbox(
            "Incluir nivel de gravedad (FELONY/MISDEMEANOR/VIOLATION)",
            value=False,
            help="Agrega un item NIVEL=FELONY, NIVEL=MISDEMEANOR o NIVEL=VIOLATION.",
        )


# ---------------------------------------------------------------------------
# Background compute
# ---------------------------------------------------------------------------
def _compute_associations_v2(
    task: BackgroundTask,
    crime_lats: np.ndarray,
    crime_lons: np.ndarray,
    offense_descriptions: list[str],
    layers_payload: list[tuple[str, np.ndarray, np.ndarray]],
    threshold_m: float,
    support: float,
    confidence: float,
    hours: list[int] | None = None,
    days_of_week: list[int] | None = None,
    offense_levels: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute FP-Growth in a background thread. No Streamlit API calls.

    Parameters
    ----------
    hours, days_of_week:
        If provided, temporal items (HORA=..., DIA=...) are appended to
        each transaction.
    offense_levels:
        If provided, severity items (NIVEL=...) are appended.
    """
    n = len(crime_lats)
    transactions: list[list[str]] = [[f"TIPO={desc}"] for desc in offense_descriptions]

    # --- Spatial proximity items ---
    total_layers = max(len(layers_payload), 1)
    for idx, (label, layer_lats, layer_lons) in enumerate(layers_payload, start=1):
        task.update(
            0.05 + 0.30 * (idx - 1) / total_layers,
            f"Calculando distancias V2 a {label}...",
        )
        distances = np.min(
            haversine_np(
                crime_lats[:, None],
                crime_lons[:, None],
                layer_lats[None, :],
                layer_lons[None, :],
            ),
            axis=1,
        )
        slug = _slug(label)
        near_item = f"CERCA_{slug}"
        far_item = f"LEJOS_{slug}"
        for i, distance in enumerate(distances):
            transactions[i].append(near_item if distance < threshold_m else far_item)
        del distances

    task.update(0.38, "Procesando dimensiones adicionales...")

    # --- Temporal items ---
    if hours is not None and days_of_week is not None:
        task.update(0.42, "Agregando items temporales...")
        for i in range(n):
            transactions[i].append(f"HORA={_hour_to_block(hours[i])}")
            # Polars dt.weekday() → ISO 8601: Mon=1 ... Sat=6, Sun=7
            is_weekend = days_of_week[i] in (6, 7)
            transactions[i].append("DIA=FIN_DE_SEMANA" if is_weekend else "DIA=ENTRE_SEMANA")

    # --- Severity items ---
    if offense_levels is not None:
        task.update(0.46, "Agregando items de gravedad...")
        for i in range(n):
            level = offense_levels[i]
            if level:
                transactions[i].append(f"NIVEL={level}")

    task.update(0.50, "Codificando transacciones V2...")
    all_items = sorted(set(item for transaction in transactions for item in transaction))
    item_idx = {item: i for i, item in enumerate(all_items)}

    onehot = np.zeros((n, len(all_items)), dtype=bool)
    for i, transaction in enumerate(transactions):
        for item in transaction:
            onehot[i, item_idx[item]] = True

    df_onehot = pd.DataFrame(onehot, columns=all_items)
    del onehot, transactions

    task.update(0.70, "Ejecutando FP-Growth V2...")
    itemsets = fpgrowth(df_onehot, min_support=support, use_colnames=True)
    num_transactions = len(df_onehot)
    del df_onehot

    if itemsets.empty:
        task.update(1.0, "Completado (sin itemsets).")
        return itemsets, pd.DataFrame()

    task.update(0.88, "Generando reglas de asociacion V2...")
    rules = association_rules(
        itemsets,
        metric="confidence",
        min_threshold=confidence,
        num_itemsets=num_transactions,
    )

    task.update(1.0, "Completado.")
    return itemsets, rules


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------
required_cols = ["latitude", "longitude", "offense_description"]
if include_temporal:
    required_cols.extend(["hour", "day_of_week"])
if include_severity:
    required_cols.append("offense_level")

# Validate that required columns exist
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.warning(
        f"Columnas requeridas no disponibles: {', '.join(missing)}. "
        "Desactivá las dimensiones adicionales o verificá el dataset."
    )
    st.stop()

base = df.filter(
    pl.col("latitude").is_not_null()
    & pl.col("longitude").is_not_null()
    & pl.col("offense_description").is_not_null()
)

if include_temporal:
    base = base.filter(pl.col("hour").is_not_null() & pl.col("day_of_week").is_not_null())
if include_severity:
    base = base.filter(pl.col("offense_level").is_in(["FELONY", "MISDEMEANOR", "VIOLATION"]))

top_offenses = (
    base.group_by("offense_description")
    .len()
    .sort("len", descending=True)
    .head(TOP_OFFENSE_TYPES)["offense_description"]
    .to_list()
)
base = base.filter(pl.col("offense_description").is_in(top_offenses))

if len(base) > SAMPLE_N:
    base = base.sample(n=SAMPLE_N, seed=42)

if base.is_empty():
    st.warning("No hay datos disponibles con los filtros actuales.")
    st.stop()

dims_label = "espacial"
if include_temporal:
    dims_label += " + temporal"
if include_severity:
    dims_label += " + gravedad"
st.caption(f"Transacciones V2 ({dims_label}): {len(base):,} (muestra de hasta {SAMPLE_N:,})")

crime_lats = base["latitude"].to_numpy()
crime_lons = base["longitude"].to_numpy()
offense_descs = base["offense_description"].to_list()

hours_list: list[int] | None = None
days_list: list[int] | None = None
levels_list: list[str] | None = None

if include_temporal:
    hours_list = base["hour"].to_list()
    days_list = base["day_of_week"].to_list()
if include_severity:
    levels_list = base["offense_level"].to_list()

layers_payload = [
    (label, layer_df["lat"].to_numpy(), layer_df["lon"].to_numpy())
    for label, layer_df in usgs_layers.items()
]

task = get_task("associations_v2")
params_hash = str(
    hash(
        (
            min_support,
            min_confidence,
            dist_threshold_km,
            include_temporal,
            include_severity,
            len(base),
            SAMPLE_N,
            TOP_OFFENSE_TYPES,
            tuple((label, len(layer_df)) for label, layer_df in usgs_layers.items()),
            tuple(sorted(df["year"].drop_nulls().unique().to_list())),
        )
    )
)

if needs_recompute(task, params_hash):
    task.start(
        _compute_associations_v2,
        crime_lats,
        crime_lons,
        offense_descs,
        layers_payload,
        dist_threshold_km * 1000,
        min_support,
        min_confidence,
        hours_list,
        days_list,
        levels_list,
    )

if not show_progress_or_result(task):
    st.stop()

itemsets_df, rules_df = task.result

# ---------------------------------------------------------------------------
# Display: itemsets
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("V2: itemsets frecuentes")

if itemsets_df.empty:
    st.warning("No se encontraron itemsets frecuentes. Proba reducir el soporte minimo.")
else:
    itemsets_display = (
        itemsets_df.assign(items=itemsets_df["itemsets"].apply(lambda x: ", ".join(sorted(x))))
        .sort_values("support", ascending=False)
        .head(MAX_DISPLAY_ROWS)[["items", "support"]]
        .reset_index(drop=True)
    )
    itemsets_display["support"] = itemsets_display["support"].round(4)
    dataframe(itemsets_display, hide_index=True)

# ---------------------------------------------------------------------------
# Display: rules
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("V2: reglas de asociacion")

if rules_df.empty:
    st.warning("No se generaron reglas. Proba reducir confianza o soporte.")
else:
    rules_display = (
        rules_df.assign(
            antecedent=rules_df["antecedents"].apply(lambda x: ", ".join(sorted(x))),
            consequent=rules_df["consequents"].apply(lambda x: ", ".join(sorted(x))),
        )
        .sort_values("lift", ascending=False)[
            ["antecedent", "consequent", "support", "confidence", "lift"]
        ]
        .reset_index(drop=True)
    )
    rules_display[["support", "confidence", "lift"]] = rules_display[
        ["support", "confidence", "lift"]
    ].round(4)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Reglas V2", f"{len(rules_display):,}")
    with col2:
        st.metric(
            f"Lift > {LIFT_THRESHOLD}",
            f"{int((rules_display['lift'] > LIFT_THRESHOLD).sum()):,}",
        )
    with col3:
        st.metric("Lift maximo", f"{rules_display['lift'].max():.2f}")
    with col4:
        st.metric("Confianza maxima", f"{rules_display['confidence'].max():.3f}")

    dataframe(
        rules_display.style.apply(_highlight_lift, axis=1),
        hide_index=True,
    )
    st.caption(
        f"Filas resaltadas: lift > {LIFT_THRESHOLD}. Un lift mayor a 1 indica que "
        "la relacion aparece mas de lo esperado por azar."
    )

    st.download_button(
        label="📥 Descargar CSV (Seguro)",
        data=rules_display.to_csv(index=False).encode("utf-8"),
        file_name="reglas_asociacion_v2.csv",
        mime="text/csv",
        help="Usa este boton para descargar los resultados. El icono de descarga "
        "de la tabla puede colgar el navegador debido a los estilos de color.",
    )

    # ------------------------------------------------------------------
    # Scatter: support vs confidence
    # ------------------------------------------------------------------
    st.markdown("---")
    st.subheader("V2: soporte vs. confianza")
    rules_plot = rules_display.head(TOP_SCATTER_RULES)
    fig_scatter = px.scatter(
        rules_plot,
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        hover_data=["antecedent", "consequent"],
        color_continuous_scale="YlOrRd",
        labels={"support": "Soporte", "confidence": "Confianza", "lift": "Lift"},
        title=f"V2: top {TOP_SCATTER_RULES} reglas USGS",
    )
    plotly_chart(fig_scatter)

    # ------------------------------------------------------------------
    # Spatio-temporal insights (only when temporal is enabled)
    # ------------------------------------------------------------------
    if include_temporal:
        _render_insight_section(
            rules_display,
            title="Insights espacio-temporales",
            icon="🕐",
            description=(
                "Reglas que involucran componentes temporales "
                "(`HORA=...`, `DIA=...`) ordenadas por Lift."
            ),
            filter_fn=_has_temporal,
            empty_msg=(
                "No se encontraron reglas con componentes temporales. "
                "Proba reducir el soporte minimo."
            ),
            chart_title="Top reglas espacio-temporales por Lift",
        )

    # ------------------------------------------------------------------
    # Severity insights (only when severity is enabled)
    # ------------------------------------------------------------------
    if include_severity:
        _render_insight_section(
            rules_display,
            title="Insights por nivel de gravedad",
            icon="⚖️",
            description=(
                "Reglas que involucran el nivel de gravedad del delito "
                "(`NIVEL=FELONY`, `NIVEL=MISDEMEANOR`, `NIVEL=VIOLATION`)."
            ),
            filter_fn=_has_severity,
            empty_msg=(
                "No se encontraron reglas con componentes de gravedad. "
                "Proba reducir el soporte minimo."
            ),
            chart_title="Top reglas por gravedad y Lift",
            breakdown_levels=["FELONY", "MISDEMEANOR", "VIOLATION"],
        )
