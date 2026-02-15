import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids

from .const import (
    API_SETTLE_SECONDS,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_SWEEP_TIME,
    DIR_DOWN,
    DIR_NONE,
    DIR_UP,
    DOMAIN,
    SERVICE_GET_ATTRIBUTES,
    SERVICE_LOWER,
    SERVICE_RAISE,
    SERVICE_SET_ATTRIBUTES,
    SERVICE_STOP,
)

_LOGGER = logging.getLogger(__name__)

# { entity_id: { "time": float, "bright": float, "target": float, "dir": str, "sweep": float } }
_brightness_cache = {}


async def get_bridge_and_id(hass: HomeAssistant, entity_id: str):
    # Retrieves the Hue Bridge instance and Resource UUID, ensuring it supports V2 API.
    from homeassistant.components.hue.const import DOMAIN as HUE_DOMAIN

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)

    if not entry:
        _LOGGER.error("Entity %s not found in entity registry.", entity_id)
        return None, None, None

    config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
    if not config_entry or config_entry.domain != HUE_DOMAIN:
        _LOGGER.error("Entity %s is not a Philips Hue entity.", entity_id)
        return None, None, None

    bridge = getattr(config_entry, "runtime_data", None)

    if not bridge:
        _LOGGER.error("Hue bridge runtime_data not found for %s", entity_id)
        return None, None, None

    # V2 Bridge Check
    if getattr(bridge, "api_version", 1) < 2:
        _LOGGER.error("Hue Smooth Dimmer requires a Bridge V2 or Bridge Pro for %s", entity_id)
        return None, None, None

    resource_id = entry.unique_id

    if ":" in resource_id:
        resource_id = resource_id.split(":")[-1]

    state = hass.states.get(entity_id)
    is_group = bool(state and state.attributes.get("is_hue_group"))
    resource_type = "grouped_light" if is_group else "light"

    return bridge, resource_type, resource_id


def _get_ha_brightness(hass: HomeAssistant, entity_id: str):
    # Read brightness from HA entity state (0-255) and convert to Hue percentage (0-100).
    state = hass.states.get(entity_id)
    if not state:
        return 0.0
    ha_bright = state.attributes.get("brightness")
    return (ha_bright / 255 * 100) if ha_bright is not None else 0.0


def resolve_brightness(hass: HomeAssistant, entity_id: str):
    # During a dimming transition, the Hue API (and therefore HA's entity state) reports
    # brightness as though the transition happened instantaneously. If a transition stops
    # mid-flight, it takes ~10s to correct its reporting.
    #
    # The resolver decides whether to trust the reported brightness or predict its own, to
    # ensure dim-stop-dim sequences work smoothly. Expired cache entries are pruned inline.

    reported = _get_ha_brightness(hass, entity_id)
    cached = _brightness_cache.get(entity_id)
    if not cached:
        return reported

    now = time.time()
    elapsed = now - cached["time"]

    # Dynamic guard window: sweep duration + API settle buffer for active transitions,
    # just the settle buffer for stopped entries.
    guard_seconds = cached["sweep"] + API_SETTLE_SECONDS if cached["dir"] != DIR_NONE else API_SETTLE_SECONDS

    # Guard expired — trust the reported brightness and prune the cache entry
    if elapsed > guard_seconds:
        _brightness_cache.pop(entity_id, None)
        return reported

    # Guard active — predict brightness instead of trusting the report.

    # Stopped: return the cached brightness from when we stopped
    if cached["dir"] == DIR_NONE:
        _LOGGER.debug(
            "CACHE [%s]: Guard active (Stationary). Ignoring reported %.1f%%. Staying at %.1f%%",
            entity_id,
            reported,
            cached["bright"],
        )
        return cached["bright"]

    # Moving: extrapolate brightness based on elapsed time
    safe_sweep = max(cached["sweep"], 0.1)
    change = (100.0 / safe_sweep) * elapsed

    if cached["dir"] == DIR_UP:
        predicted = min(cached["bright"] + change, cached["target"])
    else:
        predicted = max(cached["bright"] - change, cached["target"])

    _LOGGER.debug(
        "CACHE [%s]: Guard active (Moving). Ignoring reported: %.1f%%, Predicted: %.1f%%",
        entity_id,
        reported,
        predicted,
    )

    return predicted


async def start_transition(hass, bridge, resource_type, resource_id, entity_id, direction, sweep, limit):
    current_bright = resolve_brightness(hass, entity_id)
    distance = abs(limit - current_bright)
    dur_ms = int(distance * sweep * 10)  # 1000ms / 100% = 10ms/%

    _LOGGER.debug("CALC [%s]: %.1f%% -> %.1f%% | Dur: %dms", entity_id, current_bright, limit, dur_ms)

    if distance < 0.4:  # Min brightness step is 0.4% (1/254)
        return

    _brightness_cache[entity_id] = {
        "time": time.time(),
        "bright": current_bright,
        "target": limit,
        "dir": direction,
        "sweep": sweep,
    }

    payload = {"dimming": {"brightness": limit}, "dynamics": {"duration": dur_ms}}
    if direction == DIR_UP:
        payload["on"] = {"on": True}
    elif direction == DIR_DOWN and limit == 0.0:
        payload["on"] = {"on": False}  # Turn off light after fading to 0% brightness

    try:
        await bridge.api.request("put", f"clip/v2/resource/{resource_type}/{resource_id}", json=payload)
    except Exception as exc:
        _LOGGER.debug("Transition command ignored for %s: %s", resource_id, exc)


async def _handle_transition(hass: HomeAssistant, call: ServiceCall, direction: str, default_limit: float):
    sweep = float(call.data.get("sweep_time", DEFAULT_SWEEP_TIME))
    sweep = max(sweep, 0.1)  # Restricts user-supplied value to +ve numbers
    limit = float(call.data.get("limit", default_limit))

    entity_ids = await async_extract_entity_ids(call)
    for entity_id in entity_ids:
        if not entity_id.startswith("light."):
            continue
        bridge, resource_type, resource_id = await get_bridge_and_id(hass, entity_id)
        if bridge and resource_id:
            await start_transition(hass, bridge, resource_type, resource_id, entity_id, direction, sweep, limit)


async def _handle_stop(hass: HomeAssistant, call: ServiceCall):
    entity_ids = await async_extract_entity_ids(call)
    for entity_id in entity_ids:
        if not entity_id.startswith("light."):
            continue
        bridge, resource_type, resource_id = await get_bridge_and_id(hass, entity_id)
        if not bridge or not resource_id:
            continue

        try:
            await bridge.api.request(
                "put", f"clip/v2/resource/{resource_type}/{resource_id}", json={"dimming_delta": {"action": "stop"}}
            )
        except Exception as exc:
            _LOGGER.debug("Stop command ignored for %s: %s", resource_id, exc)

        current_bright = resolve_brightness(hass, entity_id)
        _brightness_cache[entity_id] = {
            "time": time.time(),
            "bright": current_bright,
            "target": current_bright,
            "dir": DIR_NONE,
            "sweep": 1.0,
        }

        _LOGGER.debug("STOP [%s]: Halted at %.1f%%", entity_id, current_bright)


async def _resolve_group_light_ids(bridge, grouped_light_id):
    # Resolve a grouped_light to its member light resource IDs via Hue REST API.
    # Chain: grouped_light → owner (room/zone) → children → collect light IDs
    grouped_light = bridge.api.groups.grouped_light.get(grouped_light_id)
    if not grouped_light or not grouped_light.owner:
        return []

    owner_rid = grouped_light.owner.rid
    owner_rtype = grouped_light.owner.rtype.value  # "room" or "zone"

    resp = await bridge.api.request("get", f"clip/v2/resource/{owner_rtype}/{owner_rid}")
    if not resp:
        return []

    # aiohue returns the data array directly (not wrapped in {"data": [...]})
    item = resp[0] if isinstance(resp, list) else resp
    children = item.get("children", [])
    light_ids = []
    device_ids = []

    for child in children:
        if child["rtype"] == "light":
            light_ids.append(child["rid"])
        elif child["rtype"] == "device":
            device_ids.append(child["rid"])

    # For device children, find their light services
    for device_id in device_ids:
        dev_resp = await bridge.api.request("get", f"clip/v2/resource/device/{device_id}")
        if dev_resp:
            dev_item = dev_resp[0] if isinstance(dev_resp, list) else dev_resp
            for svc in dev_item.get("services", []):
                if svc["rtype"] == "light":
                    light_ids.append(svc["rid"])

    return light_ids


async def _fetch_api_brightness(bridge, resource_type, resource_id):
    # Fetch brightness directly from the Hue CLIP V2 API.
    # Used as fallback when HA state is null (light off, cache expired).
    try:
        resp = await bridge.api.request("get", f"clip/v2/resource/{resource_type}/{resource_id}")
        item = resp[0] if isinstance(resp, list) else resp
        return float(item.get("dimming", {}).get("brightness", 0.0))
    except Exception as exc:
        _LOGGER.debug("Failed to fetch brightness from API for %s: %s", resource_id, exc)
        return 0.0


def _build_set_attributes_payload(hass, entity_id, brightness, color_temp_kelvin):
    payload = {}

    if brightness is not None:
        payload["dimming"] = {"brightness": float(brightness)}

    if color_temp_kelvin is not None:
        state = hass.states.get(entity_id)
        supported_modes = state.attributes.get("supported_color_modes", []) if state else []

        if "color_temp" not in supported_modes:
            _LOGGER.warning(
                "Entity %s does not support color temperature. Skipping CT, sending other attributes.",
                entity_id,
            )
        else:
            min_k = state.attributes.get("min_color_temp_kelvin", 2000)
            max_k = state.attributes.get("max_color_temp_kelvin", 6535)
            clamped_k = max(min_k, min(max_k, color_temp_kelvin))
            payload["color_temperature"] = {"mirek": round(1_000_000 / clamped_k)}

    return payload


async def _send_set_attributes(bridge, resource_type, resource_id, payload):
    # For groups, send to each individual light so attributes apply even when off.
    if resource_type == "grouped_light":
        light_ids = await _resolve_group_light_ids(bridge, resource_id)
        if not light_ids:
            _LOGGER.warning("No lights found in group %s", resource_id)
            return
    else:
        light_ids = [resource_id]

    for light_id in light_ids:
        try:
            await bridge.api.request("put", f"clip/v2/resource/light/{light_id}", json=payload)
        except Exception as exc:
            _LOGGER.error("set_attributes failed for light %s: %s", light_id, exc)


def _clamp_brightness(current, min_brightness, max_brightness):
    clamped = current
    if min_brightness is not None:
        clamped = max(float(min_brightness), clamped)
    if max_brightness is not None:
        clamped = min(float(max_brightness), clamped)
    return clamped if abs(clamped - current) > 0.1 else None


def _positive_or_none(value):
    return float(value) if value is not None and float(value) > 0 else None


async def _handle_set_attributes(hass: HomeAssistant, call: ServiceCall):
    brightness = call.data.get("brightness")
    min_brightness = _positive_or_none(call.data.get("min_brightness"))
    max_brightness = _positive_or_none(call.data.get("max_brightness"))
    color_temp_kelvin = _positive_or_none(call.data.get("color_temp_kelvin"))

    has_explicit = brightness is not None
    has_clamp = min_brightness is not None or max_brightness is not None
    has_ct = color_temp_kelvin is not None

    if not has_explicit and not has_clamp and not has_ct:
        _LOGGER.warning("set_attributes called with no attributes to set.")
        return

    entity_ids = await async_extract_entity_ids(call)
    for entity_id in entity_ids:
        if not entity_id.startswith("light."):
            continue
        bridge, resource_type, resource_id = await get_bridge_and_id(hass, entity_id)
        if not bridge or not resource_id:
            continue

        # Resolve brightness from min/max clamping (explicit brightness takes priority)
        if not has_explicit and has_clamp:
            current = resolve_brightness(hass, entity_id)
            if current < 0.1:
                current = await _fetch_api_brightness(bridge, resource_type, resource_id)
            brightness = _clamp_brightness(current, min_brightness, max_brightness)

        payload = _build_set_attributes_payload(hass, entity_id, brightness, color_temp_kelvin if has_ct else None)
        if payload:
            await _send_set_attributes(bridge, resource_type, resource_id, payload)


async def _fetch_light_attributes(bridge, light_id):
    # Fetch brightness and CT for a single light from the Hue API.
    try:
        resp = await bridge.api.request("get", f"clip/v2/resource/light/{light_id}")
        item = resp[0] if isinstance(resp, list) else resp
        brightness = float(item.get("dimming", {}).get("brightness", 0.0))
        mirek = item.get("color_temperature", {}).get("mirek")
        color_temp_kelvin = round(1_000_000 / mirek) if mirek else None
        return brightness, color_temp_kelvin
    except Exception as exc:
        _LOGGER.debug("Failed to fetch attributes from API for %s: %s", light_id, exc)
        return 0.0, None


async def _fetch_group_attributes(bridge, grouped_light_id):
    # Aggregate brightness and CT from individual lights in a group.
    # Groups don't report CT, and report brightness as 0 when off.
    light_ids = await _resolve_group_light_ids(bridge, grouped_light_id)
    if not light_ids:
        return 0.0, None

    brightnesses = []
    mireks = []
    for light_id in light_ids:
        try:
            resp = await bridge.api.request("get", f"clip/v2/resource/light/{light_id}")
            item = resp[0] if isinstance(resp, list) else resp
            bright = item.get("dimming", {}).get("brightness")
            if bright is not None:
                brightnesses.append(float(bright))
            mirek = item.get("color_temperature", {}).get("mirek")
            if mirek:
                mireks.append(mirek)
        except Exception as exc:
            _LOGGER.debug("Failed to fetch attributes for light %s: %s", light_id, exc)

    avg_brightness = sum(brightnesses) / len(brightnesses) if brightnesses else 0.0
    if mireks:
        avg_mirek = round(sum(mireks) / len(mireks))
        avg_ct_kelvin = round(1_000_000 / avg_mirek)
    else:
        avg_ct_kelvin = None
    return avg_brightness, avg_ct_kelvin


async def _handle_get_attributes(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    result = {}
    entity_ids = await async_extract_entity_ids(call)
    for entity_id in entity_ids:
        if not entity_id.startswith("light."):
            continue
        bridge, resource_type, resource_id = await get_bridge_and_id(hass, entity_id)
        if not bridge or not resource_id:
            continue

        if resource_type == "grouped_light":
            brightness, color_temp_kelvin = await _fetch_group_attributes(bridge, resource_id)
        else:
            # Brightness: cache/HA first, API fallback
            brightness = resolve_brightness(hass, entity_id)
            if brightness < 0.1:
                brightness = await _fetch_api_brightness(bridge, resource_type, resource_id)
            # CT: always from API (HA doesn't retain CT when off)
            _, color_temp_kelvin = await _fetch_light_attributes(bridge, resource_id)

        result[entity_id] = {
            "brightness": round(brightness, 1),
            "color_temp_kelvin": color_temp_kelvin,
        }

    return result


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Register services for the Hue Smooth Dimmer.

    async def handle_raise(call: ServiceCall):
        await _handle_transition(hass, call, DIR_UP, DEFAULT_MAX_BRIGHTNESS)

    async def handle_lower(call: ServiceCall):
        await _handle_transition(hass, call, DIR_DOWN, DEFAULT_MIN_BRIGHTNESS)

    async def handle_stop(call: ServiceCall):
        await _handle_stop(hass, call)

    async def handle_set_attributes(call: ServiceCall):
        await _handle_set_attributes(hass, call)

    async def handle_get_attributes(call: ServiceCall) -> ServiceResponse:
        return await _handle_get_attributes(hass, call)

    hass.services.async_register(DOMAIN, SERVICE_RAISE, handle_raise)
    hass.services.async_register(DOMAIN, SERVICE_LOWER, handle_lower)
    hass.services.async_register(DOMAIN, SERVICE_STOP, handle_stop)
    hass.services.async_register(DOMAIN, SERVICE_SET_ATTRIBUTES, handle_set_attributes)
    hass.services.async_register(
        DOMAIN, SERVICE_GET_ATTRIBUTES, handle_get_attributes, supports_response=SupportsResponse.ONLY
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    for svc in [SERVICE_RAISE, SERVICE_LOWER, SERVICE_STOP, SERVICE_SET_ATTRIBUTES, SERVICE_GET_ATTRIBUTES]:
        hass.services.async_remove(DOMAIN, svc)
    return True
