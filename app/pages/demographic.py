"""
Demographic Analysis Page.

Visualizations:
- Offense description distribution (top N)
- Victim demographics (age, race, sex)
- Suspect demographics
- Premise type breakdown
"""

from __future__ import annotations

import plotly.express as px
import polars as pl
import streamlit as st

from app.components.display import plotly_chart
from app.components.filters import get_filtered_data

st.header("Análisis Demográfico")

df = get_filtered_data()

# ---------------------------------------------------------------------------
# 1. Top offense types
# ---------------------------------------------------------------------------
st.subheader("Tipos de delito más frecuentes")

top_n = st.slider("Cantidad de tipos a mostrar", min_value=5, max_value=30, value=15)

offense_counts = (
    df.filter(pl.col("offense_description").is_not_null())
    .group_by("offense_description")
    .len()
    .sort("len", descending=True)
    .head(top_n)
)

fig_offenses = px.bar(
    offense_counts.to_pandas(),
    y="offense_description",
    x="len",
    orientation="h",
    labels={"len": "Cantidad", "offense_description": "Tipo de delito"},
    title=f"Top {top_n} tipos de delito",
    text="len",
)
fig_offenses.update_traces(texttemplate="%{text:,}")
fig_offenses.update_layout(yaxis=dict(autorange="reversed"))
plotly_chart(fig_offenses)


# ---------------------------------------------------------------------------
# 2. Victim demographics
# ---------------------------------------------------------------------------
st.subheader("Perfil de víctimas")

# ── Mappings for NYPD codes ──────────────────────────────────────────────────
# Valid age groups in NYPD data
_VALID_AGE_GROUPS = {"<18", "18-24", "25-44", "45-64", "65+", "UNKNOWN"}

# NYPD VIC_SEX codes (from NYC Open Data data dictionary)
_SEX_LABELS = {
    "F": "Female",
    "M": "Male",
    "D": "Business/Organization",
    "E": "PSNY (People of the State of NY)",
    "L": "Unknown (L)",
    "U": "Unknown",
}

col1, col2, col3 = st.columns(3)

with col1:
    vic_age = (
        df.filter(
            pl.col("victim_age_group").is_not_null()
            & pl.col("victim_age_group").is_in(list(_VALID_AGE_GROUPS))
        )
        .group_by("victim_age_group")
        .len()
        .sort("len", descending=True)
    )
    fig_age = px.pie(
        vic_age.to_pandas(),
        names="victim_age_group",
        values="len",
        title="Grupo etario de víctimas",
    )
    plotly_chart(fig_age)

with col2:
    vic_sex = (
        df.filter(pl.col("victim_sex").is_not_null())
        .with_columns(
            pl.col("victim_sex")
            .replace_strict(_SEX_LABELS, default="Other")
            .alias("victim_sex_label")
        )
        .group_by("victim_sex_label")
        .len()
        .sort("len", descending=True)
    )
    fig_sex = px.pie(
        vic_sex.to_pandas(),
        names="victim_sex_label",
        values="len",
        title="Sexo de víctimas",
    )
    plotly_chart(fig_sex)

with col3:
    vic_race = (
        df.filter(pl.col("victim_race").is_not_null())
        .group_by("victim_race")
        .len()
        .sort("len", descending=True)
    )
    fig_race = px.pie(
        vic_race.to_pandas(),
        names="victim_race",
        values="len",
        title="Raza de víctimas",
    )
    plotly_chart(fig_race)


# ---------------------------------------------------------------------------
# 3. Premise type
# ---------------------------------------------------------------------------
st.subheader("Tipo de premisa donde ocurren los crímenes")

premise_counts = (
    df.filter(pl.col("premise_type").is_not_null())
    .group_by("premise_type")
    .len()
    .sort("len", descending=True)
    .head(15)
)

fig_premise = px.bar(
    premise_counts.to_pandas(),
    y="premise_type",
    x="len",
    orientation="h",
    labels={"len": "Cantidad", "premise_type": "Tipo de premisa"},
    title="Top 15 tipos de premisa",
    text="len",
)
fig_premise.update_traces(texttemplate="%{text:,}")
fig_premise.update_layout(yaxis=dict(autorange="reversed"))
plotly_chart(fig_premise)
