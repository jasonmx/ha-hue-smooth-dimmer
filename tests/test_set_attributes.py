from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hue_dimmer import _handle_set_attributes
from tests.conftest import make_entity_state, make_service_call

RESOURCE_ID = "abc-123"
ENTITY_ID = "light.kitchen"


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.api.lights.set_state = AsyncMock()
    bridge.api.groups.grouped_light.get_lights.return_value = []
    return bridge


@pytest.fixture
def mock_hass():
    return MagicMock()


@pytest.fixture(autouse=True)
def patch_extract_entity_ids():
    async def _extract(call):
        return set(call.data.get("entity_id", []))

    with patch(
        "custom_components.hue_dimmer.async_extract_entity_ids",
        side_effect=_extract,
    ):
        yield


def patch_bridge(bridge, resource_type="light"):
    return patch(
        "custom_components.hue_dimmer.resolve_entity",
        return_value=(bridge, resource_type, RESOURCE_ID),
    )


@pytest.mark.asyncio
async def test_brightness_only(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "brightness": 42.5})

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    mock_bridge.api.lights.set_state.assert_called_once_with(
        RESOURCE_ID,
        brightness=42.5,
        color_temp=None,
    )


@pytest.mark.asyncio
async def test_ct_only_on_ct_light(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "color_temp_kelvin": 3000})
    mock_hass.states.get.return_value = make_entity_state(
        supported_color_modes=["color_temp"],
        min_color_temp_kelvin=2202,
        max_color_temp_kelvin=6535,
    )

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    mock_bridge.api.lights.set_state.assert_called_once_with(
        RESOURCE_ID,
        brightness=None,
        color_temp=333,
    )


@pytest.mark.asyncio
async def test_brightness_and_ct(mock_hass, mock_bridge):
    call = make_service_call({
        "entity_id": [ENTITY_ID],
        "brightness": 75,
        "color_temp_kelvin": 4000,
    })
    mock_hass.states.get.return_value = make_entity_state(
        supported_color_modes=["color_temp"],
        min_color_temp_kelvin=2202,
        max_color_temp_kelvin=6535,
    )

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    mock_bridge.api.lights.set_state.assert_called_once_with(
        RESOURCE_ID,
        brightness=75.0,
        color_temp=250,
    )


@pytest.mark.asyncio
async def test_ct_on_non_ct_light_with_brightness(mock_hass, mock_bridge):
    call = make_service_call({
        "entity_id": [ENTITY_ID],
        "brightness": 50,
        "color_temp_kelvin": 3000,
    })
    mock_hass.states.get.return_value = make_entity_state(
        supported_color_modes=["brightness"],
    )

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    # CT skipped, brightness still sent
    mock_bridge.api.lights.set_state.assert_called_once_with(
        RESOURCE_ID,
        brightness=50.0,
        color_temp=None,
    )


@pytest.mark.asyncio
async def test_ct_only_on_non_ct_light(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "color_temp_kelvin": 3000})
    mock_hass.states.get.return_value = make_entity_state(
        supported_color_modes=["brightness"],
    )

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    # No attributes to send — set_state should not be called
    mock_bridge.api.lights.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_no_fields_provided(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID]})

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    mock_bridge.api.lights.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_ct_clamped_to_min(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "color_temp_kelvin": 1000})
    mock_hass.states.get.return_value = make_entity_state(
        supported_color_modes=["color_temp"],
        min_color_temp_kelvin=2202,
        max_color_temp_kelvin=6535,
    )

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    # 1000K clamped to min 2202K → mirek = round(1_000_000 / 2202) = 454
    mock_bridge.api.lights.set_state.assert_called_once_with(
        RESOURCE_ID,
        brightness=None,
        color_temp=454,
    )


@pytest.mark.asyncio
async def test_ct_clamped_to_max(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "color_temp_kelvin": 9000})
    mock_hass.states.get.return_value = make_entity_state(
        supported_color_modes=["color_temp"],
        min_color_temp_kelvin=2202,
        max_color_temp_kelvin=6535,
    )

    with patch_bridge(mock_bridge):
        await _handle_set_attributes(mock_hass, call)

    # 9000K clamped to max 6535K → mirek = round(1_000_000 / 6535) = 153
    mock_bridge.api.lights.set_state.assert_called_once_with(
        RESOURCE_ID,
        brightness=None,
        color_temp=153,
    )


@pytest.mark.asyncio
async def test_api_error_handled(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "brightness": 50})
    mock_bridge.api.lights.set_state.side_effect = Exception("Connection refused")

    with patch_bridge(mock_bridge):
        # Should not raise
        await _handle_set_attributes(mock_hass, call)

    mock_bridge.api.lights.set_state.assert_called_once()


@pytest.mark.asyncio
async def test_group_resolves_to_individual_lights(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "brightness": 80})

    # Mock get_lights to return Light-like objects with .id attributes
    light1 = MagicMock()
    light1.id = "light-1"
    light2 = MagicMock()
    light2.id = "light-2"
    mock_bridge.api.groups.grouped_light.get_lights.return_value = [light1, light2]

    with patch_bridge(mock_bridge, resource_type="grouped_light"):
        await _handle_set_attributes(mock_hass, call)

    # 2 set_state calls for individual lights
    assert mock_bridge.api.lights.set_state.call_count == 2
    calls = mock_bridge.api.lights.set_state.call_args_list
    called_ids = {c.args[0] for c in calls}
    assert called_ids == {"light-1", "light-2"}
    for c in calls:
        assert c.kwargs["brightness"] == 80.0
        assert c.kwargs["color_temp"] is None


@pytest.mark.asyncio
async def test_group_no_lights_found(mock_hass, mock_bridge):
    call = make_service_call({"entity_id": [ENTITY_ID], "brightness": 50})
    mock_bridge.api.groups.grouped_light.get_lights.return_value = []

    with patch_bridge(mock_bridge, resource_type="grouped_light"):
        await _handle_set_attributes(mock_hass, call)

    mock_bridge.api.lights.set_state.assert_not_called()
