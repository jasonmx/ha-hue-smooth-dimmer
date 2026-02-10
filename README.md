# Philips Hue Smooth Dimmer

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Dim your Hue bulbs smoothly in "press to dim, release to stop" automations.

This integration eliminates the visual stuttering in HA "stepped" dimming loops, by using Hue's native API dimming methods.

## Key Benefits 🔅💡🔆

* **Silky Smooth:** No more jumpy brightness changes or overshoots in "press to dim" automations. Brightness transitions are continuous, predictable and polished, mirroring the behavior of a high-quality physical dimmer.
* **Instant setup:** The integration works with the lights you've already added to the core HA Hue integration. 
* **Network Friendly:** With less chatter between HA and your lights, your home network and Hue mesh remain responsive and clear.

---

## Requirements:
* **[Philips Hue integration](https://www.home-assistant.io/integrations/hue)** installed and configured.
* **Hardware:** Philips Hue Bridge V2.

> [!NOTE]
> The original Bridge V1 is unsupported as it uses different API methods and I didn't have a V1 to test.

## Installation

1. Open HACS repository

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonmx&repository=philips-hue-smooth-dimmer&category=integration)

3. Click **Download**
4. Restart Home Assistant.
5. Go to **Settings > Devices & Services**, click **Add Integration** and choose "Philips Hue Smooth Dimmer".

---

## Automation Actions

After installation, you'll find 3 new automation actions in the Actions list. 

### `hue_dimmer.raise`
Starts increasing the brightness up to the limit.

| Field | Default | Description |
| :--- | :--- | :--- |
| `target` | (Required) | Hue light(s) or Hue group(s) |
| `sweep_time` | `5` | Duration (seconds) of a full 0-100% transition |
| `limit` | `100` | Maximum brightness limit (%) |

### `hue_dimmer.lower`
Starts decreasing the brightness down to the limit. Turns light off if brightness falls to 0%.

| Field | Default | Description |
| :--- | :--- | :--- |
| `target` | (Required) | Hue light(s) or Hue group(s) |
| `sweep_time` | `5` | Duration (seconds) of a full 100-0% transition  |
| `limit` | `0` | Minimum brightness limit (%). Choose 0.2%+ to keep a light turned on (see tip). |

> [!TIP]
> Hue's minimum supported brightness is 0.2% for regular bulbs and 2.0% for Essential bulbs. Source: [Hueblog post](https://hueblog.com/2025/09/18/new-hue-bulbs-cannot-be-dimmed-any-lower/).

### `hue_dimmer.stop`
Stops an active transition.

| Field | Description |
| :--- | :--- |
| `target` | Hue light(s) or Hue group(s) |

---

## Example Usage

To dim your Hue lights smoothly with a two-button remote:

```yaml
actions:
  - choose:
      - conditions:
          - condition: trigger
            id:
              - long_press_left
        sequence:
          - action: hue_dimmer.lower
            target:
              entity_id: light.living_room
      - conditions:
          - condition: trigger
            id:
              - long_press_right
        sequence:
          - action: hue_dimmer.raise
            target:
              entity_id: light.living_room
      - conditions:
          - condition: trigger
            id:
              - release_left
              - release_right
        sequence:
          - action: hue_dimmer.stop
            target:
              entity_id: light.living_room
```

> [!TIP]
> To control multiple lights, target a **Hue Group** rather than multiple individual lights. This allows the Hue Bridge to send a single Zigbee broadcast, which dims all the lights together perfectly.
