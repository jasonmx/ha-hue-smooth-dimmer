import time
import asyncio
import logging
from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from .const import (
    DOMAIN, 
    DEFAULT_SWEEP_TIME, 
    STALE_BRIGHTNESS_GUARD_SECONDS,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MIN_BRIGHTNESS,
    SERVICE_RAISE,
    SERVICE_LOWER,
    SERVICE_STOP
)

_LOGGER = logging.getLogger(__name__)

# Tracker: { resource_id: { "time": float, "bright": float, "target": float, "dir": str, "sweep": float } }
STATE_TRACKER = {}

async def get_bridge_and_id(hass: HomeAssistant, entity_id: str):
    """Retrieves the Hue Bridge instance and Resource UUID, ensuring it is V2."""
    from homeassistant.components.hue.const import DOMAIN as HUE_DOMAIN
    
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if not entry or entry.platform != HUE_DOMAIN:
        _LOGGER.error("Entity %s is not a Philips Hue entity.", entity_id)
        return None, None

    config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
    bridge = getattr(config_entry, "runtime_data", None)
    
    if not bridge:
        _LOGGER.error("Hue bridge runtime_data not found for %s", entity_id)
        return None, None

    # --- BRIDGE VERSION CHECK ---
    # bridge.api_version is an integer (1 or 2)
    if getattr(bridge, "api_version", 1) < 2:
        _LOGGER.error(
            "Hue Smooth Dimmer only works with Hue V2 (Square) Bridges. "
            "Bridge for %s is V1 (Legacy).", entity_id
        )
        return None, None
    # ----------------------------

    resource_id = entry.unique_id
    if "-" in resource_id and ":" in resource_id:
        resource_id = resource_id.split(":")[-1]
    
    return bridge, resource_id

# During transitions, Hue's reported brightness snaps to the target value (e.g. 100% when raising).
# If you stop a transition mid-flight (e.g. by releasing a dimmer button), the entity's actual brightness
# will differ from the reported brightness for several seconds until the API catches up. The resolver's
# job is to determine when Hue's reported brightness is likely to differ from actual, and to predict the
# actual brightness in such cases. This ensures dimming continues to operate smoothly during rapid 
# "start dimming, stop dimming, start dimming again" sequences.
def resolve_current_brightness(resource_id, api_bright):
    """
    Hybrid State Resolver: Detects and ignores 'Target Snaps'.
    Only overrides the Bridge if it claims we've hit the target during the guard window.
    """
    state = STATE_TRACKER.get(resource_id)
    if not state or state["dir"] == "none":
        return api_bright

    now = time.time()
    elapsed = now - state["time"]
    
    # 1. Calculate our predicted brightness
    change = (elapsed * 100.0) / state["sweep"]
    predicted = state["bright"] + (change if state["dir"] == "up" else -change)
    predicted = max(0.0, min(100.0, predicted))

    # 2. Logic: Is the Bridge reporting a "Snap"?
    # We define a 'snap' as the Bridge reporting the exact target value
    # while we are still within the stale guard window.
    is_at_target = (abs(api_bright - state["target"]) < 0.1)
    within_guard_window = (elapsed < STALE_BRIGHTNESS_GUARD_SECONDS)

    if within_guard_window and is_at_target:
        _LOGGER.debug(
            "[%s] Snap Detected: Bridge claims target %.1f%%, but we are still moving. Using Predicted %.1f%%", 
            resource_id, api_bright, predicted
        )
        return predicted

    # 3. If the Bridge value is NOT the target, it's likely an intentional 
    # manual override or a legitimate interim update. Trust it and update math.
    if abs(api_bright - state["bright"]) > 0.1: # If the value actually changed from our start
        state["bright"] = api_bright
        state["time"] = now
        
    return api_bright

async def start_transition(bridge, resource_id, direction, sweep, limit):
    """Executes transition and stores state metadata."""
    try:
        response = await bridge.api.request("get", f"clip/v2/resource/light/{resource_id}")
        real_data = response[0] if isinstance(response, list) else response
        api_bright = float(real_data.get("dimming", {}).get("brightness", 0.0))
    except Exception as e:
        _LOGGER.error("Failed to fetch state for %s: %s", resource_id, e)
        return

    current_bright = resolve_current_brightness(resource_id, api_bright)
    distance = abs(limit - current_bright)
    dur_ms = int(distance * sweep * 10)
    
    _LOGGER.info("CALC [%s]: %.1f%% -> %.1f%% (Dist: %.1f%%) | Duration: %dms", 
                 resource_id, current_bright, limit, distance, dur_ms)

    if distance <= 0.2:
        return

    STATE_TRACKER[resource_id] = {
        "time": time.time(),
        "bright": current_bright,
        "target": limit,
        "dir": direction,
        "sweep": sweep
    }
    
    payload = {
        "dimming": {"brightness": limit},
        "dynamics": {"duration": dur_ms}
    }

    # Simplified payload: only need to ensure light is 'on' when raising
    if direction == "up":
        payload["on"] = {"on": True}

    await bridge.api.request("put", f"clip/v2/resource/light/{resource_id}", json=payload)

# Garbage collector
def _prune_tracker():
    """Remove tracker entries older than the guard window to prevent memory leaks."""
    now = time.time()
    to_delete = [
        res_id for res_id, state in STATE_TRACKER.items()
        if (now - state["time"]) > STALE_BRIGHTNESS_GUARD_SECONDS
    ]
    for res_id in to_delete:
        del STATE_TRACKER[res_id]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Register services for the Hue Smooth Dimmer."""

    async def handle_raise(call: ServiceCall):
        _prune_tracker()  # Keep the tracker lean
        sweep = float(call.data.get("sweep_time", DEFAULT_SWEEP_TIME))
        limit = float(call.data.get("limit", DEFAULT_MAX_BRIGHTNESS))
        
        for entity_id in call.data.get("entity_id", []):
            bridge, resource_id = await get_bridge_and_id(hass, entity_id)
            if bridge and resource_id:
                # We pass the constants/defaults into the logic
                await start_transition(bridge, resource_id, "up", sweep, limit)

    async def handle_lower(call: ServiceCall):
        _prune_tracker()  # Keep the tracker lean
        sweep = float(call.data.get("sweep_time", DEFAULT_SWEEP_TIME))
        limit = float(call.data.get("limit", DEFAULT_MIN_BRIGHTNESS))
        
        for entity_id in call.data.get("entity_id", []):
            bridge, resource_id = await get_bridge_and_id(hass, entity_id)
            if bridge and resource_id:
                await start_transition(
                    bridge, 
                    resource_id, 
                    "down", 
                    sweep, 
                    limit
                )

    async def handle_stop(call: ServiceCall):
        _prune_tracker()  # Keep the tracker lean
        for entity_id in call.data.get("entity_id", []):
            bridge, resource_id = await get_bridge_and_id(hass, entity_id)
            if not bridge or not resource_id:
                continue
            
            # Physical stop command to Hue Bridge
            await bridge.api.request("put", f"clip/v2/resource/light/{resource_id}", 
                                      json={"dimming_delta": {"action": "stop"}})
            
            # Determine entity's current brightness and store the value 
            try:
                response = await bridge.api.request("get", f"clip/v2/resource/light/{resource_id}")
                api_bright = float(response[0].get("dimming", {}).get("brightness", 0.0))
            except Exception:
                api_bright = 0.0
                
            final_bright = resolve_current_brightness(resource_id, api_bright)
            old_state = STATE_TRACKER.get(resource_id, {})
            
            # Lock predicted position to prevent the "Target Snap" bug
            STATE_TRACKER[resource_id] = {
                "time": time.time(),
                "bright": final_bright,
                "target": old_state.get("target", final_bright),
                "dir": "none",
                "sweep": 1.0 # Static sweep for idle state
            }
            _LOGGER.info("STOP [%s]: Halted at predicted %.1f%%", resource_id, final_bright)

    # Register services using constants for the service names
    hass.services.async_register(DOMAIN, SERVICE_RAISE, handle_raise)
    hass.services.async_register(DOMAIN, SERVICE_LOWER, handle_lower)
    hass.services.async_register(DOMAIN, SERVICE_STOP, handle_stop)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload services when the integration is removed."""
    for svc in [SERVICE_RAISE, SERVICE_LOWER, SERVICE_STOP]:
        hass.services.async_remove(DOMAIN, svc)
    return True