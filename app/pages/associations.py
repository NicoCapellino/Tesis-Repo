"""
Association Rules Page — Reglas de asociación con FP-Growth.

Aplica el algoritmo FP-Growth para descubrir patrones frecuentes entre:
- Tipo de delito (offense_description)
- Proximidad a comisarías (CERCA_POLICIA / LEJOS_POLICIA)
- Proximidad a transporte público (CERCA_TRANSPORTE / LEJOS_TRANSPORTE)

Replica y mejora el análisis del notebook original (PySpark FPGrowth)
usando mlxtend, adaptado para correr sobre datos Polars sin Spark.

Parámetros ajustables:
- Umbral de distancia para CERCA/LEJOS
- Soporte mínimo
- Confianza mínima
"""

from __future__ import annotations

import gc

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
from app.components.distances import haversine_np
from app.components.filters import (
    get_filtered_data,
    get_police_stations,
    get_transport_stations,
)

st.header("Reglas de Asociación — FP-Growth")
st.markdown(
    "FP-Growth descubre qué combinaciones de **tipo de delito** y **proximidad "
    "a infraestructura** aparecen juntas con mayor frecuencia. "
    "Una regla del tipo `[TIPO=ROBO] → [LEJOS_POLICIA]` con alta confianza indica "
    "que los robos tienden a ocurrir lejos de comisarías."
)

df = get_filtered_data()
police_df = get_police_stations()
transport_df = get_transport_stations()

if police_df is None or police_df.is_empty():
    st.warning("Datos de comisarías no disponibles. Ejecutá el pipeline primero.")
    st.stop()

# ── Controles ────────────────────────────────────────────────────────────────
with st.expander("Parámetros del algoritmo", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        min_support = st.slider(
            "Soporte mínimo", min_value=0.005, max_value=0.10,
            value=0.01, step=0.005, format="%.3f",
            help="Fracción mínima de transacciones que deben contener el itemset.",
        )
    with col2:
        min_confidence = st.slider(
            "Confianza mínima", min_value=0.5, max_value=1.0,
            value=0.7, step=0.05,
            help="Probabilidad mínima de que el consecuente ocurra dado el antecedente.",
        )
    with col3:
        dist_threshold_km = st.slider(
            "Umbral CERCA/LEJOS (km)", min_value=0.1, max_value=2.0,
            value=0.5, step=0.1,
        )

SAMPLE_N = 10_000
TOP_OFFENSE_TYPES = 15


# ── Función de cómputo para background thread ────────────────────────────────
# IMPORTANTE: Esta función NO debe llamar a ninguna API de Streamlit
# (st.*, @st.cache_data, session_state). Solo usa numpy/pandas/polars/mlxtend.

def _compute_associations(
    task: BackgroundTask,
    crime_lats: np.ndarray,
    crime_lons: np.ndarray,
    offense_descriptions: list[str],
    p_lats: np.ndarray,
    p_lons: np.ndarray,
    t_lats: np.ndarray | None,
    t_lons: np.ndarray | None,
    threshold_m: float,
    support: float,
    confidence: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute FP-Growth in background thread. No Streamlit API calls."""

    n = len(crime_lats)

    # Paso 1: Distancias a comisarías
    task.update(0.10, f"Paso 1/5: Calculando distancias a {len(p_lats)} comisarías...")
    dist_police = np.min(
        haversine_np(
            crime_lats[:, None], crime_lons[:, None],
            p_lats[None, :], p_lons[None, :],
        ),
        axis=1,
    )

    # Paso 2: Distancias a transporte (opcional)
    has_transport = t_lats is not None and len(t_lats) > 0
    dist_transport = None
    if has_transport:
        task.update(0.25, f"Paso 2/5: Calculando distancias a {len(t_lats)} estaciones...")
        dist_transport = np.min(
            haversine_np(
                crime_lats[:, None], crime_lons[:, None],
                t_lats[None, :], t_lons[None, :],
            ),
            axis=1,
        )
    else:
        task.update(0.25, "Paso 2/5: Sin datos de transporte, salteando...")

    # Paso 3: Construir transacciones vectorizado
    # IMPORTANTE: usar str() nativo, no np.str_, para compatibilidad con mlxtend 0.24+
    # (mlxtend intenta int() sobre np.generic, lo que falla con strings)
    task.update(0.40, "Paso 3/5: Construyendo transacciones...")
    police_items = [
        "CERCA_POLICIA" if d < threshold_m else "LEJOS_POLICIA"
        for d in dist_police
    ]
    tipo_items = [f"TIPO={desc}" for desc in offense_descriptions]

    if has_transport and dist_transport is not None:
        transport_items = [
            "CERCA_TRANSPORTE" if d < threshold_m else "LEJOS_TRANSPORTE"
            for d in dist_transport
        ]
        transactions = [
            (tipo_items[i], police_items[i], transport_items[i])
            for i in range(n)
        ]
    else:
        transactions = [
            (tipo_items[i], police_items[i])
            for i in range(n)
        ]

    del dist_police, dist_transport, police_items, tipo_items
    gc.collect()

    # Paso 4: One-hot encoding + FP-Growth
    task.update(0.55, "Paso 4/5: Codificando y ejecutando FP-Growth...")
    all_items = sorted(set(item for t in transactions for item in t))
    item_idx = {item: i for i, item in enumerate(all_items)}
    n_items = len(all_items)

    # Build boolean array directly (más eficiente que TransactionEncoder)
    onehot = np.zeros((n, n_items), dtype=bool)
    for i, t in enumerate(transactions):
        for item in t:
            onehot[i, item_idx[item]] = True

    df_onehot = pd.DataFrame(onehot, columns=all_items)
    del onehot, transactions
    gc.collect()

    itemsets = fpgrowth(df_onehot, min_support=support, use_colnames=True)
    num_transactions = len(df_onehot)
    del df_onehot
    gc.collect()

    if itemsets.empty:
        return itemsets, pd.DataFrame()

    # Paso 5: Generar reglas
    task.update(0.80, "Paso 5/5: Generando reglas de asociación...")
    # mlxtend ≥0.24 requiere num_itemsets para calcular métricas correctamente
    rules = association_rules(
        itemsets,
        metric="confidence",
        min_threshold=confidence,
        num_itemsets=num_transactions,
    )

    return itemsets, rules


# ── Preparar datos en main thread ─────────────────────────────────────────────
base = df.filter(
    pl.col("latitude").is_not_null()
    & pl.col("longitude").is_not_null()
    & pl.col("offense_description").is_not_null()
)

# Limit to top N offense types
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

st.caption(f"Transacciones a procesar: {len(base):,} (muestra de hasta {SAMPLE_N:,})")

# Extract numpy arrays (thread-safe, no Streamlit dependency)
crime_lats = base["latitude"].to_numpy()
crime_lons = base["longitude"].to_numpy()
offense_descs = base["offense_description"].to_list()

p_lats = police_df["lat"].to_numpy()
p_lons = police_df["lon"].to_numpy()
t_lats = transport_df["lat"].to_numpy() if transport_df is not None else None
t_lons = transport_df["lon"].to_numpy() if transport_df is not None else None

# ── Ejecutar en segundo plano ─────────────────────────────────────────────────
task = get_task("associations")
params_hash = str(hash((
    min_support, min_confidence, dist_threshold_km,
    len(base), SAMPLE_N, TOP_OFFENSE_TYPES,
    tuple(sorted(df["year"].drop_nulls().unique().to_list())),
)))

if needs_recompute(task, params_hash):
    task.start(
        _compute_associations,
        crime_lats, crime_lons, offense_descs,
        p_lats, p_lons, t_lats, t_lons,
        dist_threshold_km * 1000,
        min_support, min_confidence,
    )

if not show_progress_or_result(task):
    st.stop()

# ── Resultados disponibles ────────────────────────────────────────────────────
itemsets_df, rules_df = task.result

# ── Resultados: Itemsets frecuentes ─────────────────────────────────────────
st.markdown("---")
st.subheader("Itemsets frecuentes")

if itemsets_df.empty:
    st.warning(
        "No se encontraron itemsets frecuentes con el soporte mínimo configurado. "
        "Intentá reducir el soporte mínimo."
    )
else:
    itemsets_display = (
        itemsets_df
        .assign(items=itemsets_df["itemsets"].apply(lambda x: ", ".join(sorted(x))))
        .sort_values("support", ascending=False)
        .head(30)[["items", "support"]]
        .reset_index(drop=True)
    )
    itemsets_display["support"] = itemsets_display["support"].round(4)
    st.dataframe(itemsets_display, width="stretch", hide_index=True)

# ── Resultados: Reglas de asociación ─────────────────────────────────────────
st.markdown("---")
st.subheader("Reglas de asociación")

if rules_df.empty:
    st.warning(
        "No se generaron reglas con la confianza mínima configurada. "
        "Intentá reducir la confianza mínima o el soporte."
    )
else:
    rules_display = (
        rules_df
        .assign(
            antecedent=rules_df["antecedents"].apply(lambda x: ", ".join(sorted(x))),
            consequent=rules_df["consequents"].apply(lambda x: ", ".join(sorted(x))),
        )
        .sort_values("confidence", ascending=False)
        [["antecedent", "consequent", "support", "confidence", "lift"]]
        .reset_index(drop=True)
    )
    rules_display[["support", "confidence", "lift"]] = (
        rules_display[["support", "confidence", "lift"]].round(4)
    )

    # ── KPIs ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Reglas encontradas", f"{len(rules_display):,}")
    with col2:
        high_lift = (rules_display["lift"] > 1.5).sum()
        st.metric("Reglas con lift > 1.5", f"{high_lift:,}")
    with col3:
        st.metric("Confianza máxima", f"{rules_display['confidence'].max():.3f}")

    # Highlight high-lift rules
    def _highlight_lift(row: pd.Series) -> list[str]:
        return ["background-color: #fff3cd" if row["lift"] > 1.5 else "" for _ in row]

    st.dataframe(
        rules_display.style.apply(_highlight_lift, axis=1),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Filas en amarillo: lift > 1.5. Un lift > 1 indica que antecedente "
        "y consecuente aparecen juntos más de lo esperado por azar."
    )

# ── Scatter de soporte vs confianza ──────────────────────────────────────────
if not rules_df.empty:
    st.markdown("---")
    st.subheader("Dispersión: soporte vs. confianza (tamaño = lift)")

    rules_plot = rules_display.head(50)
    fig_scatter = px.scatter(
        rules_plot,
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        hover_data=["antecedent", "consequent"],
        color_continuous_scale="YlOrRd",
        labels={"support": "Soporte", "confidence": "Confianza", "lift": "Lift"},
        title="Top 50 reglas: soporte vs. confianza",
    )
    st.plotly_chart(fig_scatter, width="stretch")
