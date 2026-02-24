from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "comparador_workspace"

_comparador_workspace_component = components.declare_component(
    "comparador_workspace_v1",
    path=str(_COMPONENT_DIR),
)


def render_comparador_workspace(payload: dict[str, Any], key: str = "comparador_workspace_v1") -> dict[str, Any]:
    """Render the filter+map workspace component and return interaction payload."""
    default_value: dict[str, Any] = {
        "action": "init",
        "filters": payload.get("selectedFilters") or {
            "empreendimentos": [],
            "cidades": [],
            "tipologias": [],
            "status": [],
        },
    }

    response = _comparador_workspace_component(payload=payload, key=key, default=default_value)
    if isinstance(response, dict):
        return response
    return default_value
