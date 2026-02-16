# Philips Hue Smooth Dimmer

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/) ![Installs](https://img.shields.io/badge/dynamic/json?color=blue&label=Installs&query=hue_dimmer.total&url=https://analytics.home-assistant.io/custom_integrations.json) ![Latest Version](https://img.shields.io/github/v/release/jasonmx/philips-hue-smooth-dimmer)

This integration extends the core Philips Hue integration and lets you:
* Use third-party buttons to dim your Hue lights smoothly.
* Control brightness and color temp while Hue lights are turned off.

## Key Benefits 🔅💡🔆

* **Silky Smooth:** Dimming is continuous and precise. No more jittery repeat loops and dimming overshoots.
* **Predictable:** Prepare your lights to turn on how you want them. Fewer dazzles and fumbles in the dark when lights turn on.
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

### Smooth Dimming

Use these 3 actions in the Home Assistant automation editor:

| Action | Description |
| :--- | :--- |
| `hue_dimmer.raise` | Start raising brightness |
| `hue_dimmer.lower` | Start lowering brightness |
| `hue_dimmer.stop` | Freeze brightness |

| Field | Actions | Description |
| :--- | :--- | :--- |
| `target` | all | Hue lights and groups |
| `sweep_time` | raise, lower | Duration of a full 0–100% sweep (default 5s) |
| `limit` | raise | Max brightness (default 100%) |
| `limit` | lower | Min brightness (default 0%). Light turns off at 0%. Use 0.4%+ for standard Hue, 2%+ for Essential series. |

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

* Avoid dazzle from lights that were turned off bright.
* Skip fumbling in the dark after lights were dimmed to zero.
* Consistent turn-on behavior across your home.

| Action | Description |
| :--- | :--- |
| `hue_dimmer.set_attributes` | Set brightness or color temperature without turning on |
| `hue_dimmer.get_attributes` | Read brightness and color temperature while off or on |

| Field | Description |
| :--- | :--- |
| `target` | Hue lights and groups |
| `brightness` | Set exact brightness, 0.4–100% (set_attributes only) |
| `min_brightness` | Clamp brightness to at least this level (set_attributes only) |
| `max_brightness` | Clamp brightness to at most this level (set_attributes only) |
| `color_temp_kelvin` | Color temperature in Kelvin, CT-capable lights only (set_attributes only) |

`hue_dimmer.get_attributes` returns `brightness` (%) and `color_temp_kelvin` per entity.

#### GUI Automation Example: Set turn-on brightness

![Set turn-on behavior](examples/update-lights-after-turn-off--step-2.png)

To set up this automation:

1. Go to **Settings > Automations**
2. Click **Create automation** and choose **Create new automation**
3. Open the ⋮ menu and switch to **Edit in YAML** view
4. Copy the YAML below and paste it into the YAML editor (replacing the existing YAML)
5. Switch back to **Edit in visual editor** view
6. Click the ["When something changes" entry](examples/update-lights-after-turn-off--step-1.png?raw=true) and select your Hue light(s).
7. Click the "Set turn-on behavior" entry and edit the brightness/CT settings. Don't touch the Targets section.
8. Click **Save**

```yaml
description: >
  When lights turn off, set brightness and/or color temperature for next turn-on.
triggers:
  - trigger: state
    entity_id: []
    from:
      - "on"
    to:
      - "off"
    for:
      hours: 0
      minutes: 0
      seconds: 1
actions:
  - action: hue_dimmer.set_attributes
    target:
      entity_id: "{{ trigger.entity_id }}"
    data:
      max_brightness: 80
      min_brightness: 25
      alias: Set turn-on behavior for the lights
mode: parallel
max: 10
```

If you add more than 10 lights, increase "max: 10" accordingly.

</details>

***

## Uninstall

This integration follows standard integration removal.

1. Open the integration

[![Open the Philips Hue Smooth Dimmer integration in your Home Assistant instance.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=hue_dimmer)

2. Click the ⋮ menu and choose **Delete**
