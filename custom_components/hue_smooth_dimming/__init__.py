import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)
DOMAIN = "hue_smooth_dimming"

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hue Smooth Dimming services."""
    registry = er.async_get(hass)

    async def handle_transition(call: ServiceCall):
        for entity_id in call.data.get("entity_id", []):
            if not (entry := registry.async_get(entity_id)) or entry.platform != "hue":
                continue
            
            bridge = hass.data["hue"].get(entry.config_entry_id)
            if not bridge: continue

            if call.service == "stop_transition":
                cmd = {"dimming_delta": {"action": "stop"}}
            else:
                # Logic for start_transition
                state = hass.states.get(entity_id)
                cur = (state.attributes.get("brightness", 0) / 255) * 100 if state else 0
                
                direction = call.data.get("direction")
                limit = call.data.get("limit")
                sweep = float(call.data.get("sweep_time", 5))
                
                target = float(limit) if limit is not None else (100.0 if direction == "up" else 0.0)
                # Duration in seconds: (distance / 100) * sweep_time
                dur = abs(target - cur) * sweep / 100
                cmd = {"dimming": {"brightness": target}, "dynamics": {"duration": int(dur * 1000)}, "on": True if target > 0 else None}

            await bridge.async_request_call(bridge.api.lights.set_state, id=entry.unique_id, **cmd)

    hass.services.async_register(DOMAIN, "start_transition", handle_transition)
    hass.services.async_register(DOMAIN, "stop_transition", handle_transition)
    return True