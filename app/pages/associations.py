"""
Association Rules Page V2.

FP-Growth discovers frequent patterns between offense type and proximity to
USGS V2 police, fire, and healthcare facilities.
"""

from __future__ import annotations

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
from app.components.distances import nearest_distances
from app.components.filters import get_filtered_data, get_usgs_v2_layers
from app.components.utils import slugify as _slug

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

SAMPLE_N = 10_000
TOP_OFFENSE_TYPES = 15


def _compute_associations_v2(
    task: BackgroundTask,
    crime_lats: np.ndarray,
    crime_lons: np.ndarray,
    offense_descriptions: list[str],
    layers_payload: list[tuple[str, np.ndarray, np.ndarray]],
    threshold_m: float,
    support: float,
    confidence: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute FP-Growth in a background thread. No Streamlit API calls."""
    n = len(crime_lats)
    transactions = [[f"TIPO={desc}"] for desc in offense_descriptions]

    for idx, (label, layer_lats, layer_lons) in enumerate(layers_payload, start=1):
        task.update(
            0.10 + 0.35 * (idx - 1) / max(len(layers_payload), 1),
            f"Calculando distancias V2 a {label}...",
        )
        distances = nearest_distances(
            crime_lats,
            crime_lons,
            layer_lats,
            layer_lons,
        )
        slug = _slug(label)
        near_item = f"CERCA_{slug}"
        far_item = f"LEJOS_{slug}"
        for i, distance in enumerate(distances):
            transactions[i].append(near_item if distance < threshold_m else far_item)
        del distances

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
        return itemsets, pd.DataFrame()

    task.update(0.88, "Generando reglas de asociacion V2...")
    rules = association_rules(
        itemsets,
        metric="confidence",
        min_threshold=confidence,
        num_itemsets=num_transactions,
    )

    return itemsets, rules


base = df.filter(
    pl.col("latitude").is_not_null()
    & pl.col("longitude").is_not_null()
    & pl.col("offense_description").is_not_null()
)

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

st.caption(f"Transacciones V2 a procesar: {len(base):,} (muestra de hasta {SAMPLE_N:,})")

crime_lats = base["latitude"].to_numpy()
crime_lons = base["longitude"].to_numpy()
offense_descs = base["offense_description"].to_list()
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
    )

if not show_progress_or_result(task):
    st.stop()

itemsets_df, rules_df = task.result

st.markdown("---")
st.subheader("V2: itemsets frecuentes")

if itemsets_df.empty:
    st.warning("No se encontraron itemsets frecuentes. Proba reducir el soporte minimo.")
else:
    itemsets_display = (
        itemsets_df.assign(items=itemsets_df["itemsets"].apply(lambda x: ", ".join(sorted(x))))
        .sort_values("support", ascending=False)
        .head(30)[["items", "support"]]
        .reset_index(drop=True)
    )
    itemsets_display["support"] = itemsets_display["support"].round(4)
    dataframe(itemsets_display, hide_index=True)

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
        .sort_values("confidence", ascending=False)[
            ["antecedent", "consequent", "support", "confidence", "lift"]
        ]
        .reset_index(drop=True)
    )
    rules_display[["support", "confidence", "lift"]] = rules_display[
        ["support", "confidence", "lift"]
    ].round(4)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Reglas V2", f"{len(rules_display):,}")
    with col2:
        st.metric("Lift > 1.5", f"{int((rules_display['lift'] > 1.5).sum()):,}")
    with col3:
        st.metric("Confianza maxima", f"{rules_display['confidence'].max():.3f}")

    def _highlight_lift(row: pd.Series) -> list[str]:
        # Set both background and text colour so the highlight stays readable in
        # both light and dark themes (the previous pale yellow left the theme's
        # white text unreadable). Dark green = strong association (lift > 1.5).
        style = "background-color: #1b5e20; color: #ffffff; font-weight: bold"
        return [style if row["lift"] > 1.5 else "" for _ in row]

    dataframe(
        rules_display.style.apply(_highlight_lift, axis=1),
        hide_index=True,
    )
    st.caption(
        "Filas resaltadas: lift > 1.5. Un lift mayor a 1 indica que la relacion "
        "aparece mas de lo esperado por azar."
    )

    st.markdown("---")
    st.subheader("V2: soporte vs. confianza")
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
        title="V2: top 50 reglas USGS",
    )
    plotly_chart(fig_scatter)
