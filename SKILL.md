# GPIO Control Skill

Control Raspberry Pi GPIO pins by **name or pin number**.
Pins can be named at any time — names are stored in `pin_config.json`.

## Requirements

- Raspberry Pi (optimised for RPi 5 with `pinctrl`)
- Python 3.11+
- `pip install gpiozero lgpio` (fallback on older boards)

---

## How pins are addressed

Every command that targets a pin accepts either:
- A **registered name**: `"kitchen_light"`, `"fan"`, `"door_sensor"`
- A **BCM pin number** (as string or integer): `"17"`, `17`

Unregistered pins work fine with their number — you can name them later.

> **When the user tells you what is connected to a pin, always call `rename` or `register` immediately so the name is saved for future sessions.**

---

## How to call the skill

```bash
python3 gpio_skill.py --json '<JSON>'
```

All output is a single JSON object on stdout.
`"success": true` = OK, `"success": false` = error (see `"error"` field).

---

## Commands

### `activate` — Give power to a pin (set HIGH)

```bash
python3 gpio_skill.py --json '{"command":"activate","device":"17"}'
python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
```
```json
{"success": true, "pin": 17, "value": true, "device": "kitchen_light", "backend": "pinctrl"}
```

---

### `deactivate` — Cut power to a pin (set LOW)

```bash
python3 gpio_skill.py --json '{"command":"deactivate","device":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"deactivate","device":"17"}'
```

---

### `toggle` — Flip a pin (on→off or off→on)

```bash
python3 gpio_skill.py --json '{"command":"toggle","device":"kitchen_light"}'
```

---

### `read` — Read the current state of a pin

Returns `"value": true` (HIGH / 3.3 V) or `"value": false` (LOW / GND).

```bash
python3 gpio_skill.py --json '{"command":"read","device":"motion_sensor"}'
python3 gpio_skill.py --json '{"command":"read","device":"4"}'
```
```json
{"success": true, "pin": 4, "value": true, "device": "motion_sensor", "description": "PIR sensor in hallway"}
```

---

### `set` — Set PWM level (fan speed, LED brightness)

`level` is a float from `0.0` (off) to `1.0` (full).

```bash
python3 gpio_skill.py --json '{"command":"set","device":"cooling_fan","level":0.7}'
python3 gpio_skill.py --json '{"command":"set","device":"18","level":0.5}'
```
```json
{"success": true, "pin": 18, "duty_cycle": 0.7, "frequency": 100.0, "device": "cooling_fan"}
```

---

### `rename` — Give a pin a name (or change its name)

Use this when the user says what something is connected to.
`device` can be the current name OR just the pin number.

```bash
# Name an unnamed pin
python3 gpio_skill.py --json '{"command":"rename","device":"17","new_name":"kitchen_light"}'

# Rename an existing device
python3 gpio_skill.py --json '{"command":"rename","device":"kitchen_light","new_name":"counter_strip"}'
```
```json
{"success": true, "renamed_to": "kitchen_light", "pin": 17}
```

After renaming, the old name no longer works — use the new name.

---

### `register` — Add a pin with full configuration

Use when you need to set the type or extra options (e.g. relay, sensor, PWM).

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Friendly name |
| `pin` | yes | BCM pin number |
| `type` | no | `output` (default), `relay`, `input`, `pwm` |
| `description` | no | Human-readable note |
| `active_low` | no | `true` for relays wired active-LOW |
| `pull_up` | no | `true` to enable pull-up resistor (inputs) |
| `frequency` | no | PWM frequency in Hz (default `100`) |

```bash
python3 gpio_skill.py --json '{
  "command": "register",
  "name": "front_door_relay",
  "pin": 27,
  "type": "relay",
  "active_low": true,
  "description": "Relay controlling front door lock"
}'
```

---

### `unregister` — Remove a name

```bash
python3 gpio_skill.py --json '{"command":"unregister","name":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"unregister","pin":"17"}'
```

---

### `list_devices` — Show all named pins

Call this to see what is currently registered before taking action.

```bash
python3 gpio_skill.py --json '{"command":"list_devices"}'
```
```json
{
  "success": true,
  "devices": [
    {"name": "kitchen_light",   "pin": 17, "type": "output", "description": "LED strip over kitchen counter"},
    {"name": "motion_sensor",   "pin": 4,  "type": "input",  "description": "PIR sensor in hallway"},
    {"name": "cooling_fan",     "pin": 18, "type": "pwm",    "description": "PWM cooling fan"}
  ]
}
```

---

## Decision guide for the AI agent

| User says | Action |
|-----------|--------|
| "Skru på pin 17" | `activate`, device `"17"` |
| "Gi strøm til kjøkkenlyset" | `activate`, device `"kitchen_light"` |
| "Slå av viften" | `deactivate`, device `"cooling_fan"` |
| "Sett viften til 70%" | `set`, device `"cooling_fan"`, level `0.7` |
| "Les bevegelsessensoren" | `read`, device `"motion_sensor"` |
| "Jeg koblet til en LED på pin 22" | `rename`, device `"22"`, new_name (ask user for name) |
| "Kall pin 17 for kjøkkenlys" | `rename`, device `"17"`, new_name `"kitchen_light"` |
| "Hva er koblet til?" | `list_devices` |
| "Fjern kjøkkenlyset fra lista" | `unregister`, name `"kitchen_light"` |

---

## Use as a Python module

```python
from gpio_skill import activate, deactivate, toggle, read, set_level, rename, list_devices

activate("kitchen_light")      # by name
activate(17)                   # by pin number — same result

rename(22, "bedroom_lamp")     # give pin 22 a name
deactivate("bedroom_lamp")

result = read("motion_sensor")
if result["value"]:
    print("Motion detected!")

set_level("cooling_fan", 0.6)  # 60% speed
```
