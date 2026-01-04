# Philips Hue Smooth Dimmer

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Dim your Hue bulbs smoothly like a pro in automations and with non-Hue buttons.

This integration eliminates the visual stuttering and network congestion caused by traditional "stepped" dimming loops, by leveraging the Philips Hue V2 API's native dimming commands.

## Key Benefits 🔅💡🔆

* **Silky Smooth:** No more jumpy brightness changes or overshoots in "press to dim, release to stop" automations. Brightness transitions are predictable, continuous and visually polished, mirroring the behavior of a high-quality physical dimmer.
* **Network Friendly:** By sending only two Hue API commands instead of lots of small brightness steps, your home LAN and Hue meshes remain responsive and clear.
* **One-click configuration:** This helper piggybacks on HA's core Hue integration, so there's no fiddly post-installation setup.

---

## Requirements:
* **Hardware:** Philips Hue Bridge V2. Legacy V1 bridges are not supported.
* **[Philips Hue integration](https://www.home-assistant.io/integrations/hue)** installed.

## Installation

### Method 1: HACS (Recommended)

1. Click the button below:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonmx&repository=ha-hue-smooth-dimmer&category=integration)

2. Click the **Download** button on the repository page.
3. Restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for "Hue Smooth Dimmer".

### Method 2: Manual
1. Copy the `hue_smooth_dimmer` folder to your `/config/custom_components/` directory.
2. **Restart Home Assistant.**
3. Go to **Settings > Devices & Services > Add Integration** and search for "Hue Smooth Dimmer".

---

## Services

After installation, you'll find 3 new services in the automation Actions list. You can also use them in Developer Tools -> Actions. 

### `hue_smooth_dimmer.raise`
Initiates a smooth transition toward a higher brightness level.

| Field | Default | Description |
| :--- | :--- | :--- |
| `target` | (Required) | The Hue light(s) or group(s) to control. |
| `sweep_time` | `5` | Seconds for a full 0-100% transition. |
| `limit` | `100` | Brightness limit (e.g., stop at 80%). |

### `hue_smooth_dimmer.lower`
Initiates a smooth transition toward a lower brightness level, and turns off at 0%.

| Field | Default | Description |
| :--- | :--- | :--- |
| `target` | (Required) | The Hue light(s) or group(s) to control. |
| `sweep_time` | `5` | Seconds for a full 100-0% transition (s). |
| `limit` | `0` | Brightness limit. Use 0.2% to keep a Hue bulb turned on. |

> [!TIP]
> The minimum brighness of Hue bulbs is 0.2% for regular bulbs and 2% for Essential bulbs. Source: [this blog post](https://hueblog.com/2025/09/18/new-hue-bulbs-cannot-be-dimmed-any-lower/).

### `hue_smooth_dimmer.stop`
Stops an active transition.

---

## Example Usage

To dim your Hue lights smoothly with a button remote like the Aqara Opple or IKEA TRÅDFRI:

**Automation: Start Dimming Up on Button Hold**
```yaml
action:
  - service: hue_smooth_dimmer.raise
    target:
      entity_id: light.living_room
```

**Automation: Stop Dimming on Button Release**
```yaml
action:
  - service: hue_smooth_dimmer.stop
    target:
      entity_id: light.living_room
```

> [!TIP]
> For the best performance and perfect synchronization, target **Hue Groups** rather than HA groups or multiple bulbs. This allows the Hue Bridge to send a single Zigbee broadcast, ensuring every light starts and stops at the same moment.
