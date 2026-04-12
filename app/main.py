"""
NYC Crime Analysis Dashboard — Entry point.

Defines the two-section navigation structure and runs shared logic
(data loading + global sidebar filters) before handing control to
the selected page via ``st.navigation()``.

Run with::

    streamlit run app/main.py
"""

from __future__ import annotations

import polars as pl
import streamlit as st

from config.settings import DEFAULT_CITY, PROCESSED_DIR, REFERENCE_DIR

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NYC Crime Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Sectioned navigation
# ---------------------------------------------------------------------------
pages = {
    "Estadísticas Descriptivas": [
        st.Page("pages/overview.py",     title="Resumen General",  icon="📊"),
        st.Page("pages/temporal.py",     title="Temporal",         icon="🕐"),
        st.Page("pages/geospatial.py",   title="Geoespacial",      icon="🗺️"),
        st.Page("pages/demographic.py",  title="Demográfico",      icon="👥"),
    ],
    "Análisis Avanzado": [
        st.Page("pages/comparative.py",  title="Comparativo",          icon="⚖️"),
        st.Page("pages/proximity.py",    title="Proximidad",           icon="📍"),
        st.Page("pages/clustering.py",   title="Clustering K-Means",   icon="🔵"),
        st.Page("pages/associations.py", title="Reglas de Asociación", icon="🔗"),
        st.Page("pages/prediction.py",   title="Predicción ML",        icon="🎯"),
        st.Page("pages/anomalies.py",    title="Anomalías",            icon="🔴"),
    ],
}

nav = st.navigation(pages)


# ---------------------------------------------------------------------------
# Columns used across the dashboard — load only what we need to save RAM.
# Full dataset is ~3M rows; loading all columns doubles memory usage.
# ---------------------------------------------------------------------------
_CORE_COLUMNS = [
    "year", "month", "day_of_week", "hour",
    "borough", "offense_level", "offense_description",
    "latitude", "longitude",
    "premise_type",
    "victim_age_group", "victim_sex", "victim_race",
    "crime_start_date",
]


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_complaints() -> pl.DataFrame:
    """Load processed complaint Parquet files (selected columns only)."""
    data_dir = PROCESSED_DIR / "complaints"
    if not data_dir.exists():
        st.error(
            f"Datos procesados no encontrados en `{data_dir}`. "
            "Ejecutá el pipeline: `docker-compose run --rm pipeline`"
        )
        st.stop()

    files = sorted(data_dir.glob("*.parquet"))
    if not files:
        st.error("No se encontraron archivos Parquet en el directorio procesado.")
        st.stop()

    # Read only the columns we need — saves ~50% memory
    frames = []
    for f in files:
        schema = pl.read_parquet_schema(f)
        use_cols = [c for c in _CORE_COLUMNS if c in schema]
        frames.append(pl.read_parquet(f, columns=use_cols))

    return pl.concat(frames, how="diagonal_relaxed")


@st.cache_data(ttl=3600)
def load_police_stations() -> pl.DataFrame | None:
    path = REFERENCE_DIR / DEFAULT_CITY / "police_stations.parquet"
    return pl.read_parquet(path) if path.exists() else None


@st.cache_data(ttl=3600)
def load_transport_stations() -> pl.DataFrame | None:
    path = REFERENCE_DIR / DEFAULT_CITY / "transport_stations.parquet"
    return pl.read_parquet(path) if path.exists() else None


# ---------------------------------------------------------------------------
# Load data and populate session state (only once per session)
# ---------------------------------------------------------------------------
if "complaints" not in st.session_state:
    with st.spinner("Cargando datos..."):
        st.session_state["complaints"]         = load_complaints()
        st.session_state["police_stations"]    = load_police_stations()
        st.session_state["transport_stations"] = load_transport_stations()

df_all = st.session_state["complaints"]


# ---------------------------------------------------------------------------
# Sidebar — Global filters (run before nav.run() so every page sees them)
# ---------------------------------------------------------------------------
st.sidebar.title("Filtros globales")

available_years = sorted(df_all["year"].drop_nulls().unique().to_list())
selected_years = st.sidebar.multiselect("Año(s)", available_years, default=available_years)

available_boroughs = sorted(df_all["borough"].drop_nulls().unique().to_list())
selected_boroughs = st.sidebar.multiselect("Borough(s)", available_boroughs, default=available_boroughs)

available_levels = sorted(df_all["offense_level"].drop_nulls().unique().to_list())
selected_levels = st.sidebar.multiselect("Nivel de ofensa", available_levels, default=available_levels)

filtered = df_all.filter(
    pl.col("year").is_in(selected_years)
    & pl.col("borough").is_in(selected_boroughs)
    & pl.col("offense_level").is_in(selected_levels)
)

st.session_state["filtered"] = filtered

# ---------------------------------------------------------------------------
# Run selected page (con protección global contra caídas)
# ---------------------------------------------------------------------------
try:
    nav.run()
except MemoryError:
    st.error(
        "**Error de memoria.** La operación requiere más RAM de la disponible. "
        "Intentá reducir los filtros (menos años o boroughs) o usá parámetros "
        "más conservadores en la página actual."
    )
except Exception as exc:
    st.error(
        f"**Error inesperado en la página actual:**\n\n`{type(exc).__name__}: {exc}`\n\n"
        "Podés navegar a otra pestaña o ajustar los filtros para intentar de nuevo."
    )
