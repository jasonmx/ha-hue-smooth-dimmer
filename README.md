# Philips Hue Smooth Dimmer

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/) ![Installs](https://img.shields.io/badge/dynamic/json?color=blue&label=Installs&query=hue_dimmer.total&url=https://analytics.home-assistant.io/custom_integrations.json) ![Latest Version](https://img.shields.io/github/v/release/jasonmx/philips-hue-smooth-dimmer)

This integration extends the core Philips Hue integration and lets you:
* Use third-party buttons to dim your Hue lights smoothly.
* Set a light's turn-on brightness and color temp while it's turned off.

## Key Benefits 🔅💡🔆

* **Silky Smooth:** Dimming is continuous and precise. No more jittery repeat loops and dimming overshoots.
* **Predictable Turn_On:** Prepare your lights to turn on how you want them. No more unexpected flashes and blackouts when lights turn on.
* **Zero Setup:** Connects to your lights automatically via the core Philips Hue integration.

---

## Requirements:
* **Hardware:** Philips Hue Bridge V2 or Pro (V3)
* **[Philips Hue integration](https://www.home-assistant.io/integrations/hue)** installed and configured

## Installation

1. Open the Philips Hue Smooth Dimmer HACS repository

[![Open the Philips Hue Smooth Dimmer HACS repository in your Home Assistant instance.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonmx&repository=philips-hue-smooth-dimmer&category=integration)

2. Click **Download**
3. Restart Home Assistant
4. Add the integration

[![Add Philips Hue Smooth Dimmer to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hue_dimmer)

***

## Usage

### Smooth Dimmer

Use these 3 actions in the Home Assistant automation editor:

<details>
<summary><b>hue_dimmer.raise</b>: Start raising the brightness when you long-press an 'up' button. </summary>

| Field | Description |
| :--- | :--- |
| `target` | Hue lights & Hue groups |
| `sweep_time` | Duration of 0-100% sweep (default 5s) |
| `limit` | Maximum brightness limit (default 100%) |

</details>

<details>
<summary><b>hue_dimmer.lower</b>: Start lowering the brightness when you long-press a 'down' button.</summary>

| Field | Description |
| :--- | :--- |
| `target` | Hue lights and groups |
| `sweep_time` | Duration of 100-0% sweep (default 5s)  |
| `limit` | Minimum brightness limit (default 0%). Light turns off at 0%. Choose 0.4%+ to keep standard Hue lights on, and 2%+ for Essential series. |

</details>

<details>
<summary> <b>hue_dimmer.stop</b>: Freeze the brightness when you release a button. </summary>

| Field | Description |
| :--- | :--- |
| `target` | Hue lights and groups |

</details>

To dim multiple lights perfectly, target a **Hue Group** instead of separate lights. This enables your Hue Bridge to sync them via a single broadcast message at the start and end of each dimming transition.

#### YAML Example

<details>
<summary>Two-button dimmer</summary>

```yaml
actions:
  - choose:

      # Hold left button to lower brightness
      - conditions:
          - condition: trigger
            id: long_press_left
        sequence:
          - action: hue_dimmer.lower
            target:
              entity_id: light.living_room
            data:
              sweep_time: 4
              limit: 0.4

      # Hold right button to raise brightness
      - conditions:
          - condition: trigger
            id: long_press_right
        sequence:
          - action: hue_dimmer.raise
            target:
              entity_id: light.living_room
            data:
              sweep_time: 4

      # Release button to stop
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
</details>

---

### Set Brightness / Color Temp While Light Is Off

Example use cases:
* Set lights to a helpful turn-on brightness after being dimmed to zero.
* Avoid dazzle from lights that were turned off bright.
* Pre-stage turn-on behavior across automations.

<details>
<summary><b>hue_dimmer.set_attributes</b>: Set brightness or color temperature without turning on.</summary>

| Field | Description |
| :--- | :--- |
| `target` | Hue lights and groups |
| `brightness` | Brightness level, 0.4–100% |
| `color_temp_kelvin` | Color temperature in Kelvin (CT lights only) |

</details>

#### YAML Example

<details>
<summary>If a light turns off below 10% brightness, set to 50% for next turn-on</summary>

```yaml
triggers:
  - trigger: light.turned_off
    target:
      entity_id: light.kitchen
conditions:
  # HA forgets brightness when light turns off, so use pre turn-off brightness.
  # HA attributes use 0-255 scale, so 10% equates roughly to 25
  - condition: template
    value_template: "{{ trigger.from_state.attributes.get('brightness') | int(0) < 25 }}"
actions:
  - action: hue_dimmer.set_attributes
    target:
      entity_id: light.kitchen
    data:
      brightness: 50
```
</details>

***

## Uninstall

This integration follows standard integration removal.

1. Open the integration

[![Open the Philips Hue Smooth Dimmer integration in your Home Assistant instance.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=hue_dimmer)

2. Click the ⋮ menu and choose **Delete**
