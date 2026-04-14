"""
Overview / Home page — KPI summary of the filtered dataset.
"""

from __future__ import annotations

import polars as pl
import streamlit as st

from app.components.filters import get_filtered_data

df = get_filtered_data()

st.title("NYC Crime Analysis Dashboard")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de registros", f"{len(df):,}")

with col2:
    felonies = len(df.filter(pl.col("offense_level") == "FELONY"))
    st.metric("Felonies", f"{felonies:,}")

with col3:
    st.metric("Boroughs", df["borough"].n_unique())

with col4:
    years = df["year"].drop_nulls().unique().sort().to_list()
    period = f"{years[0]}-{years[-1]}" if years else "N/A"
    st.metric("Periodo", period)

st.markdown("---")
st.markdown(
    """
    Usá el menú lateral para navegar entre las secciones:

    **Estadísticas Descriptivas** — Análisis puramente basado en distribuciones y conteos:
    - **Temporal**: Evolución mensual, patrones por día/hora, comparativa anual.
    - **Geoespacial**: Mapa de calor interactivo, densidad por borough.
    - **Demográfico**: Perfil de víctimas y sospechosos, tipos de premisa.

    **Análisis Avanzado** — Cruce de datos e inteligencia artificial:
    - **Comparativo**: Ratio crímenes/comisarías, densidad alrededor del transporte.
    - **Proximidad**: Boxplots de crímenes cerca vs. lejos de comisarías.
    - **Clustering K-Means**: Zonas de alta criminalidad identificadas por ML.
    - **Reglas de Asociación**: Patrones entre tipo de delito y proximidad a infraestructura.
    - **Predicción ML**: Random Forest y Gradient Boosting con validación cruzada.
    - **Anomalías**: Isolation Forest para detectar días con actividad criminal inusual.

    ---
    *Fuente: NYC Open Data — NYPD Complaint Data (2020-2025)*
    """
)
