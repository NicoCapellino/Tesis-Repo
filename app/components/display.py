"""Compatibility wrappers for Streamlit display APIs."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import cache
from typing import Any

import streamlit as st


@cache
def _supports_width_stretch(func: Callable[..., Any]) -> bool:
    """Return whether a Streamlit function accepts string width values."""
    try:
        width_param = inspect.signature(func).parameters.get("width")
    except (TypeError, ValueError):
        return False
    return isinstance(width_param.default, str) if width_param is not None else False


def plotly_chart(figure_or_data: Any, **kwargs: Any) -> Any:
    """Render a Plotly chart full-width across supported Streamlit versions."""
    if _supports_width_stretch(st.plotly_chart):
        return st.plotly_chart(figure_or_data, width="stretch", **kwargs)
    return st.plotly_chart(figure_or_data, use_container_width=True, **kwargs)


def dataframe(data: Any, **kwargs: Any) -> Any:
    """Render a dataframe full-width across supported Streamlit versions."""
    if _supports_width_stretch(st.dataframe):
        return st.dataframe(data, width="stretch", **kwargs)
    return st.dataframe(data, use_container_width=True, **kwargs)
