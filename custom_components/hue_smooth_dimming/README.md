# Hue Smooth Dimming

**Hue Smooth Dimming** is a helper for the official Philips Hue integration that delivers **silky smooth dimming transitions** using the native Hue v2 API.

A common Home Assistant frustration is jumpy/steppy dimming transitions in automations that send repeated brightness changes (e.g., +10% or -10%) every few hundreds milliseconds while a button is held. This causes visual stuttering and often results in the light "overshooting" the target, due to flooding of the Zigbee network and processing lags.

**Hue Smooth Dimming** leverages the Hue bulbs' native transition capabilities, by sending a single "start" command when you press your button and a "stop" command when you release it. 

The result is the same premium, high-end feel that you get using Philips Hue's own dimmers, without network congestion and lags.

## Key Benefits

* **Silky Smooth UX:** No more stuttering lights and low family approval ratings. Transitions are fluid, continuous, and visually polished.
* **Intuitive Constant Speed:** Lights move at a predictable, natural pace that mirrors the behavior of a high-quality physical dimmer. E.g. with a 5s Sweep Time, the brightness changes at 20% per second.
* **Less Network Noise:** By sending only two commands (Start and Stop) instead of dozens of tiny updates, your Zigbee mesh remains responsive and clear.
* **Native Integration:** No duplicate entities or secondary logins. This helper "borrows" your existing connection to the official Hue integration to target your lights directly.

---

## Installation

### Method 1: HACS (Recommended)
1. Open **HACS** > **Integrations**.
2. Click the three dots (top right) > **Custom repositories**.
3. Paste this repository URL, select **Integration** as the category, and click **Add**.
4. Download "Hue Smooth Dimming" and **Restart Home Assistant**.

### Method 2: Manual
1. Copy the `hue_smooth_dimming` folder to your `/config/custom_components/` directory.
2. **Restart Home Assistant.**

---

## Services

### `hue_smooth_dimming.start_transition`
Initiates a smooth transition. This is typically mapped to a "Hold" or "Long Press" button trigger.

| Field | Range | Description |
| :--- | :--- | :--- |
| `target` | - | Hue light(s) or groups to control. |
| `direction` | `up` / `down` | The direction of the brightness change. |
| `sweep_time` | 1 - 3600 | Seconds to go from 0% to 100 (default 5s). |
| `limit` | 0 - 100 | Optional stop point (e.g. 1% when dimming down to keep a light turned on, as 0% is off). |

### `hue_smooth_dimming.stop_transition`
Stops an active transition. This is typically mapped to the "Release" trigger of a button.

---

## Example Usage

To achieve a "Pro" dimming experience with a button remote like the Aqara Opple or IKEA TRÅDFRI:

**Automation: Start Dimming on Hold**
```yaml
action:
  - service: hue_smooth_dimming.start_transition
    target:
      entity_id: light.living_room
    data:
      direction: "up"
      sweep_time: 4 # 4s for a full 0-100% transition
```

**Automation: Stop Dimming on Release**
```yaml
action:
  - service: hue_smooth_dimming.stop_transition
    target:
      entity_id: light.living_room