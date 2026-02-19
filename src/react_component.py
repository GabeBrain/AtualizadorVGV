from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "react_workspace"

_react_workspace_component = components.declare_component(
    "react_workspace_poc_local",
    path=str(_COMPONENT_DIR),
)


def render_react_workspace(payload: dict[str, Any], key: str = "react_workspace_poc") -> dict[str, Any]:
    """Render the React workspace POC and return interaction payload."""
    default_value: dict[str, Any] = {
        "action": "init",
        "selectedEmpreendimento": payload.get("selectedEmpreendimento") or "",
    }
    response = _react_workspace_component(payload=payload, key=key, default=default_value)
    if isinstance(response, dict):
        return response
    return default_value
