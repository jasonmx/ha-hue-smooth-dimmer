import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import (
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_SWEEP_TIME,
    DOMAIN,
    SERVICE_LOWER,
    SERVICE_RAISE,
    SERVICE_STOP,
    STALE_BRIGHTNESS_GUARD_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

# Tracker: { (resource_type, resource_id):
#            { "time": float, "bright": float, "target": float, "dir": str, "sweep": float } }
STATE_TRACKER = {}


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


def resolve_current_brightness(tracker_key, api_brightness):
    # During a dimming transition, the Hue API reports the brightness as though the transition
    # happened instantaneously. If a transition stops mid-flight, the API takes ~10s to catch up
    # and correct its reporting.
    #
    # The resolver decides whether to trust the API brightness value or to predict its own, to
    # ensure dim-stop-dim sequences work smoothly. The STATE_TRACKER helper cache tracks
    # dimming actions and their estimated entry/exit brightnesses during periods when the API
    # is untrusted.

    # If tracker is empty, we trust the API
    state = STATE_TRACKER.get(tracker_key)
    if not state:
        return api_brightness

    now = time.time()
    elapsed = now - state["time"]  # Elapsed time since last tracker entry

    # If the guard window has expired, we trust the API and clear the tracker
    if elapsed > STALE_BRIGHTNESS_GUARD_SECONDS:
        STATE_TRACKER.pop(tracker_key, None)
        return api_brightness

    # During the guard window, we distrust the API and predict the brightness.

    # CASE 1: No active transition (Direction is 'none')
    if state["dir"] == "none":
        _LOGGER.debug(
            "TRACKER [%s]: Guard active (Stationary). Ignoring API %.1f%%. Staying at %.1f%%",
            tracker_key,
            api_brightness,
            state["bright"],
        )
        return state["bright"]

    # CASE 2: Active transition in progress
    safe_sweep = max(state["sweep"], 0.1)  # Input validation
    change = (100.0 / safe_sweep) * elapsed  # Estimate brightness change since last tracker entry

    if state["dir"] == "up":
        predicted = min(state["bright"] + change, state["target"])
    else:
        predicted = max(state["bright"] - change, state["target"])

    _LOGGER.debug(
        "TRACKER [%s]: Guard active (Moving). API: %.1f%%, Predicted: %.1f%%", tracker_key, api_brightness, predicted
    )

    return predicted


async def start_transition(bridge, resource_type, resource_id, direction, sweep, limit):
    tracker_key = (resource_type, resource_id)
    try:
        response = await bridge.api.request("get", f"clip/v2/resource/{resource_type}/{resource_id}")
        real_data = response[0] if isinstance(response, list) else response
        api_bright = float(real_data.get("dimming", {}).get("brightness", 0.0))
    except Exception as e:
        _LOGGER.error("Failed to fetch state for %s: %s", resource_id, e)
        return

    current_bright = resolve_current_brightness(tracker_key, api_bright)
    distance = abs(limit - current_bright)
    dur_ms = int(distance * sweep * 10)  # 1000ms / 100% = 10ms/%

    _LOGGER.info("CALC [%s]: %.1f%% -> %.1f%% | Dur: %dms", resource_id, current_bright, limit, dur_ms)

    if distance < 0.2:  # Min brightness step is 0.2%
        return

    STATE_TRACKER[tracker_key] = {
        "time": time.time(),
        "bright": current_bright,
        "target": limit,
        "dir": direction,
        "sweep": sweep,
    }

    payload = {"dimming": {"brightness": limit}, "dynamics": {"duration": dur_ms}}
    if direction == "up":
        payload["on"] = {"on": True}
    elif direction == "down" and limit == 0.0:
        payload["on"] = {"on": False}  # Turn off light after fading to 0% brightness

    await bridge.api.request("put", f"clip/v2/resource/{resource_type}/{resource_id}", json=payload)


async def _fetch_current_brightness(bridge, resource_type, resource_id):
    # Get brightness from Hue API
    try:
        response = await bridge.api.request("get", f"clip/v2/resource/{resource_type}/{resource_id}")
        response_data = response[0] if isinstance(response, list) else response
        return float(response_data.get("dimming", {}).get("brightness", 0.0))
    except Exception:
        return 0.0


def _prune_tracker():
    # Clean the tracker to prevent memory leaks.
    now = time.time()
    to_delete = [key for key, state in STATE_TRACKER.items() if (now - state["time"]) > STALE_BRIGHTNESS_GUARD_SECONDS]
    for key in to_delete:
        del STATE_TRACKER[key]


async def _handle_transition(hass: HomeAssistant, call: ServiceCall, direction: str, default_limit: float):
    _prune_tracker()

    sweep = float(call.data.get("sweep_time", DEFAULT_SWEEP_TIME))
    sweep = max(sweep, 0.1)  # Restricts user-supplied value to +ve numbers
    limit = float(call.data.get("limit", default_limit))

    for entity_id in call.data.get("entity_id", []):
        bridge, resource_type, resource_id = await get_bridge_and_id(hass, entity_id)
        if bridge and resource_id:
            await start_transition(
                bridge,
                resource_type,
                resource_id,
                direction,
                sweep,
                limit,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Register services for the Hue Smooth Dimmer.

    async def handle_raise(call: ServiceCall):
        await _handle_transition(hass, call, "up", DEFAULT_MAX_BRIGHTNESS)

    async def handle_lower(call: ServiceCall):
        await _handle_transition(hass, call, "down", DEFAULT_MIN_BRIGHTNESS)

    async def handle_stop(call: ServiceCall):
        _prune_tracker()
        for entity_id in call.data.get("entity_id", []):
            bridge, resource_type, resource_id = await get_bridge_and_id(hass, entity_id)
            if not bridge or not resource_id:
                continue

            await bridge.api.request(
                "put", f"clip/v2/resource/{resource_type}/{resource_id}", json={"dimming_delta": {"action": "stop"}}
            )

            api_bright = await _fetch_current_brightness(bridge, resource_type, resource_id)

            # Predict current brightness and cache it
            tracker_key = (resource_type, resource_id)
            final_bright = resolve_current_brightness(tracker_key, api_bright)
            old_state = STATE_TRACKER.get(tracker_key, {})
            STATE_TRACKER[tracker_key] = {
                "time": time.time(),
                "bright": final_bright,
                "target": old_state.get("target", final_bright),
                "dir": "none",
                "sweep": 1.0,
            }

            _LOGGER.info(
                "STOP [%s]: Halted at %.1f%% (Guarding against snap to %.1f%%)",
                resource_id,
                final_bright,
                STATE_TRACKER[tracker_key]["target"],
            )

    hass.services.async_register(DOMAIN, SERVICE_RAISE, handle_raise)
    hass.services.async_register(DOMAIN, SERVICE_LOWER, handle_lower)
    hass.services.async_register(DOMAIN, SERVICE_STOP, handle_stop)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    for svc in [SERVICE_RAISE, SERVICE_LOWER, SERVICE_STOP]:
        hass.services.async_remove(DOMAIN, svc)
    return True
