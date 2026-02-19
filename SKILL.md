# GPIO Control Skill

Control named devices connected to Raspberry Pi GPIO pins.
Devices are defined in `pin_config.json` — the AI works with device names, not pin numbers.

## Requirements

- Raspberry Pi (optimised for RPi 5 with `pinctrl`)
- Python 3.11+
- `pip install gpiozero lgpio` (only needed as fallback on non-RPi-5 boards)

---

## Step 1 — Define your devices

Edit `pin_config.json` to describe what is connected to each pin.
You can also register devices at runtime using the `register` command (see below).

```json
{
  "devices": {
    "kitchen_light": {
      "pin": 17,
      "type": "output",
      "description": "LED strip over kitchen counter"
    },
    "front_door_relay": {
      "pin": 27,
      "type": "relay",
      "active_low": true,
      "description": "Relay that controls the front door lock"
    },
    "motion_sensor": {
      "pin": 4,
      "type": "input",
      "pull_up": false,
      "description": "PIR motion sensor in hallway"
    },
    "cooling_fan": {
      "pin": 18,
      "type": "pwm",
      "frequency": 100,
      "description": "PWM-controlled cooling fan"
    }
  }
}
```

**Device types:**
| type | Use for |
|------|---------|
| `output` | LEDs, buzzers, simple switches |
| `relay` | Relays (supports `active_low: true`) |
| `input` | Buttons, PIR sensors, reed switches |
| `pwm` | Fans, dimmable LEDs, servos |

---

## Step 2 — Call the skill

```bash
python3 gpio_skill.py --json '<JSON payload>'
```

Or pipe from stdin:

```bash
echo '<JSON>' | python3 gpio_skill.py
```

All responses are JSON. Always check `"success": true/false` first.

---

## Commands

### `list_devices` — See all registered devices

Always call this first if you are unsure what devices exist.

```bash
python3 gpio_skill.py --json '{"command":"list_devices"}'
```
```json
{
  "success": true,
  "devices": [
    {"name": "kitchen_light", "pin": 17, "type": "output", "description": "LED strip over kitchen counter"},
    {"name": "cooling_fan",   "pin": 18, "type": "pwm",    "description": "PWM-controlled cooling fan"}
  ]
}
```

---

### `activate` — Turn a device ON

Works with type `output` and `relay`.

```bash
python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
```
```json
{"success": true, "device": "kitchen_light", "pin": 17, "value": true, "backend": "pinctrl"}
```

---

### `deactivate` — Turn a device OFF

```bash
python3 gpio_skill.py --json '{"command":"deactivate","device":"kitchen_light"}'
```
```json
{"success": true, "device": "kitchen_light", "pin": 17, "value": false, "backend": "pinctrl"}
```

---

### `toggle` — Flip a device (on→off, off→on)

```bash
python3 gpio_skill.py --json '{"command":"toggle","device":"kitchen_light"}'
```
```json
{"success": true, "device": "kitchen_light", "pin": 17, "value": false, "backend": "pinctrl"}
```

---

### `read` — Read current state of a device

Works with all types. Returns `"value": true` for HIGH, `false` for LOW.

```bash
python3 gpio_skill.py --json '{"command":"read","device":"motion_sensor"}'
```
```json
{"success": true, "device": "motion_sensor", "pin": 4, "value": true, "description": "PIR motion sensor in hallway"}
```

---

### `set` — Set PWM level (fans, dimmers, servos)

| Field | Type | Description |
|-------|------|-------------|
| `device` | string | Name of a `pwm` device |
| `level` | float | `0.0` = off, `1.0` = full speed/brightness |

```bash
python3 gpio_skill.py --json '{"command":"set","device":"cooling_fan","level":0.6}'
```
```json
{"success": true, "device": "cooling_fan", "pin": 18, "duty_cycle": 0.6, "frequency": 100.0}
```

---

### `register` — Add a new device at runtime

```bash
python3 gpio_skill.py --json '{
  "command": "register",
  "name": "bedroom_lamp",
  "pin": 22,
  "type": "output",
  "description": "Bedside lamp in bedroom"
}'
```
```json
{"success": true, "registered": "bedroom_lamp", "pin": 22, "type": "output"}
```

The device is saved to `pin_config.json` immediately and available for all future calls.

---

### `unregister` — Remove a device

```bash
python3 gpio_skill.py --json '{"command":"unregister","name":"bedroom_lamp"}'
```
```json
{"success": true, "unregistered": "bedroom_lamp"}
```

---

## Error responses

```json
{"success": false, "error": "Unknown device: 'oven'. Call list_devices() to see all."}
```

---

## Common tasks for the AI agent

| User says | Command to use |
|-----------|---------------|
| "Turn on the kitchen light" | `activate`, device `kitchen_light` |
| "Turn off the fan" | `deactivate`, device `cooling_fan` |
| "Dim the light to 30%" | `set`, device + `level: 0.3` |
| "Is there motion in the hallway?" | `read`, device `motion_sensor` |
| "I connected a buzzer to pin 23" | `register` with name, pin, type |
| "What devices are available?" | `list_devices` |
| "Toggle the relay" | `toggle`, device name |

---

## Use as a Python module

```python
from gpio_skill import activate, deactivate, read, set_level, list_devices, register

# Turn on a device
activate("kitchen_light")

# Read a sensor
result = read("motion_sensor")
print(result["value"])  # True if motion detected

# Add a new device programmatically
register("garage_door", pin=23, device_type="relay", description="Garage door opener")
```
