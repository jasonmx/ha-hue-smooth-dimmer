# Philips Hue Smooth Dimmer

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/) ![Version](https://img.shields.io/github/v/release/jasonmx/philips-hue-smooth-dimmer)

Dim your Hue bulbs smoothly in "press to dim, release to stop" automations.

This integration eliminates the visual stuttering in HA "stepped" dimming loops, using the Hue API's dim-stop methods.

## Key Benefits 🔅💡🔆

* **Silky Smooth:** No more jumpy brightness changes or overshoots in "press to dim" automations. Dimming is continuous and precise, mirroring a high-quality physical dimmer.
* **Zero Setup:** Connects to your Hue bridge automatically via the core Philips Hue integration.
* **Network Friendly:** With less chatter between HA and your lights, your home network and Hue mesh remain responsive and clear.

---

## Requirements:
* **[Philips Hue integration](https://www.home-assistant.io/integrations/hue)** installed and configured.
* **Hardware:** Philips Hue Bridge V2 or Pro (V3).

> [!NOTE]
> Bridge V1 is unsupported, as the V1 API uses different methods.

## Installation

1. Open HACS repository

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonmx&repository=philips-hue-smooth-dimmer&category=integration)

3. Click **Download**
4. Restart Home Assistant.
5. Go to **Settings > Devices & Services**, click **Add Integration** and choose "Philips Hue Smooth Dimmer".

---

## Usage

After installation, you'll find 3 new automation actions in the Actions list.

> [!TIP]
> To dim multiple lights perfectly, target a **Hue Group** instead of individual Hue lights. The Hue Bridge will then keep them in sync via a single Zigbee broadcast.

### `hue_dimmer.raise`
Starts increasing the brightness up to the limit.

| Field | Default | Description |
| :--- | :--- | :--- |
| `target` | (Required) | Hue light(s) or Hue group(s) |
| `sweep_time` | `5` | Duration (seconds) of a full 0-100% sweep |
| `limit` | `100` | Maximum brightness limit (%) |

### `hue_dimmer.lower`
Starts decreasing the brightness down to the limit. Light turns off at 0%.

| Field | Default | Description |
| :--- | :--- | :--- |
| `target` | (Required) | Hue light(s) or Hue group(s) |
| `sweep_time` | `5` | Duration (seconds) of a full 100-0% sweep  |
| `limit` | `0` | Minimum brightness limit (%). Choose 0.2%+ to keep a light turned on (see note). |

> [!NOTE]
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
