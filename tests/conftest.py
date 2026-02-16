from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.api.lights.set_state = AsyncMock()
    bridge.api.groups.grouped_light.set_state = AsyncMock()
    bridge.api.groups.grouped_light.get_lights.return_value = []
    return bridge


@pytest.fixture
def mock_hass():
    return MagicMock()


def make_service_call(data):
    call = MagicMock()
    call.data = data
    return call


def make_entity_state(supported_color_modes=None, min_color_temp_kelvin=None, max_color_temp_kelvin=None):
    state = MagicMock()
    attrs = {}
    if supported_color_modes is not None:
        attrs["supported_color_modes"] = supported_color_modes
    if min_color_temp_kelvin is not None:
        attrs["min_color_temp_kelvin"] = min_color_temp_kelvin
    if max_color_temp_kelvin is not None:
        attrs["max_color_temp_kelvin"] = max_color_temp_kelvin
    state.attributes = attrs
    return state
