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
* **Hardware:** Philips Hue Bridge V2 or Pro (V3).
* **[Philips Hue integration](https://www.home-assistant.io/integrations/hue)** installed and configured.

## Installation

1. Open HACS repository

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonmx&repository=philips-hue-smooth-dimmer&category=integration)

3. Click **Download**
4. Restart Home Assistant.
5. Go to **Settings > Devices & Services**, click **Add Integration** and choose "Philips Hue Smooth Dimmer".

---

## Usage

Add these 3 actions to your automations.

### `hue_dimmer.raise`
<details>
<summary> Starts increasing the brightness. </summary>

| Field | Default | Description |
| :--- | :---: | :--- |
| `target` | (Required) | Hue light(s) or Hue group(s) |
| `sweep_time` | `5` | Duration (seconds) of a full 0-100% sweep |
| `limit` | `100` | Maximum brightness limit (%) |

To dim multiple lights, target a Hue Group instead of separate entities. Your bridge then syncs them via a single Zigbee broadcast.

</details>

### `hue_dimmer.lower`
<details>
<summary> Starts decreasing the brightness. Light turns off at 0%. </summary>

| Field | Default | Description |
| :--- | :---: | :--- |
| `target` | (Required) | Hue light(s) or Hue group(s) |
| `sweep_time` | `5` | Duration (seconds) of a full 100-0% sweep  |
| `limit` | `0` | Minimum brightness limit (%). Choose 0.2%+ to keep a light turned on (2.0%+ for Hue Essential). |

To dim multiple lights, target a Hue Group instead of separate entities. Your bridge then syncs them via a single Zigbee broadcast.

</details>

### `hue_dimmer.stop`
<details>
<summary> Stops an active transition. </summary>

| Field | Description |
| :--- | :--- |
| `target` | Hue light(s) or Hue group(s) |

</details>

---

Automation Example

To dim your Hue lights smoothly with a two-button remote:

```yaml
actions:
  - choose:
      - conditions: # Hold left button to lower brightness
          - condition: trigger
            id: long_press_left
        sequence:
          - action: hue_dimmer.lower
            target:
              entity_id: light.living_room
      - conditions: # Hold right button to raise brightness
          - condition: trigger
            id: long_press_right
        sequence:
          - action: hue_dimmer.raise
            target:
              entity_id: light.living_room
      - conditions: # Release button to stop brightness transition
          - condition: trigger
            id:
              - release_left
              - release_right
        sequence:
          - action: hue_dimmer.stop
            target:
              entity_id: light.living_room
```
