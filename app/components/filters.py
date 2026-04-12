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
        st.error(
            "No hay datos filtrados. Seleccioná filtros en la barra lateral."
        )
        st.stop()
    return st.session_state["filtered"]


def get_police_stations() -> pl.DataFrame | None:
    """Return police station data from session state."""
    return st.session_state.get("police_stations")


def get_transport_stations() -> pl.DataFrame | None:
    """Return transport station data from session state."""
    return st.session_state.get("transport_stations")


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
