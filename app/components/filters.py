"""
Reusable filter components for Streamlit pages.

These helpers read from ``st.session_state`` and provide common
filter widgets that can be used across multiple pages.
"""

from __future__ import annotations

import polars as pl
import streamlit as st


def get_filtered_data() -> pl.DataFrame:
    """Return the globally filtered DataFrame from session state.

    The main page (``app/main.py``) applies sidebar filters and stores
    the result in ``st.session_state["filtered"]``.
    """
    if "filtered" not in st.session_state:
        if "complaints" not in st.session_state:
            # Data not loaded yet — force main.py to run again
            st.rerun()
        st.error("No hay datos filtrados. Seleccioná filtros en la barra lateral.")
        st.stop()
    return st.session_state["filtered"]


def get_usgs_healthcare_v2() -> pl.DataFrame | None:
    """Return USGS V2 healthcare facility data from session state."""
    return st.session_state.get("usgs_healthcare_v2")


def get_usgs_police_v2() -> pl.DataFrame | None:
    """Return USGS V2 police station data (FCode 74034) from session state."""
    return st.session_state.get("usgs_police_v2")


def get_usgs_fire_v2() -> pl.DataFrame | None:
    """Return USGS V2 fire station data (FCode 74026) from session state."""
    return st.session_state.get("usgs_fire_v2")


def get_usgs_v2_layers() -> dict[str, pl.DataFrame]:
    """Return all loaded USGS V2 infrastructure layers.

    Labels are intentionally prefixed with ``USGS V2`` so analysis pages make
    the authoritative data source explicit.
    """
    candidates = {
        "USGS V2 - Policia": get_usgs_police_v2(),
        "USGS V2 - Bomberos": get_usgs_fire_v2(),
        "USGS V2 - Salud": get_usgs_healthcare_v2(),
    }
    return {label: df for label, df in candidates.items() if df is not None and not df.is_empty()}


def offense_type_filter(df: pl.DataFrame, *, key: str = "offense_filter") -> list[str]:
    """Render a multi-select for offense description and return selected values.

    Args:
        df: DataFrame with an ``offense_description`` column.
        key: Unique Streamlit widget key.

    Returns:
        List of selected offense descriptions.
    """
    options = sorted(df["offense_description"].drop_nulls().unique().to_list())
    return st.multiselect(
        "Tipo de delito",
        options=options,
        default=options[:10] if len(options) > 10 else options,
        key=key,
    )
