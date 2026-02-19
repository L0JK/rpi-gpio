# rpi-gpio — GPIO Skill for OpenClaw

Control Raspberry Pi GPIO pins by **name or pin number** through the OpenClaw AI agent.

Define what is connected to each pin once. After that the AI can say
_"turn on the kitchen light"_ or _"give power to pin 17"_ — both work.

---

## Files

| File | Purpose |
|------|---------|
| `gpio_skill.py` | Main script — call via CLI or import as a module |
| `pin_config.json` | Your pin names and descriptions (edit this) |
| `SKILL.md` | OpenClaw reads this to understand how to use the skill |
| `requirements.txt` | Python dependencies |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/rpi-gpio.git
cd rpi-gpio

# 2. Install dependencies (only needed on non-RPi-5 boards)
pip install gpiozero lgpio

# 3. Edit pin_config.json to describe your wiring
#    (or let the AI register pins for you at runtime)

# 4. Test
python3 gpio_skill.py --json '{"command":"list_devices"}'
python3 gpio_skill.py --json '{"command":"activate","device":"17"}'
```

---

## Addressing pins

Every command accepts either a **registered name** or a **BCM pin number**:

```bash
# These do the same thing:
python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"activate","device":"17"}'
```

---

## Naming a pin

```bash
# "Pin 17 is the kitchen light"
python3 gpio_skill.py --json '{"command":"rename","device":"17","new_name":"kitchen_light"}'
```

The name is saved to `pin_config.json` immediately.

---

## All commands

| Command | What it does |
|---------|-------------|
| `activate` | Set pin HIGH (give power) |
| `deactivate` | Set pin LOW (cut power) |
| `toggle` | Flip current state |
| `read` | Read current pin state |
| `set` | Set PWM level (0.0–1.0) |
| `rename` | Give a pin a friendly name |
| `register` | Add a pin with type + options |
| `unregister` | Remove a pin's registration |
| `list_devices` | Show all named pins |

See [`SKILL.md`](SKILL.md) for full documentation with examples.

---

## Use as a Python module

```python
from gpio_skill import activate, deactivate, read, set_level, rename

activate("kitchen_light")   # by name
activate(17)                # by pin number

rename(22, "bedroom_lamp")
read("motion_sensor")       # {"success": true, "value": false, ...}
set_level("cooling_fan", 0.6)
```

---

## GPIO backend

| Board | Backend | Pin state after script exits |
|-------|---------|------------------------------|
| Raspberry Pi 5 | `pinctrl` (auto-detected) | **Persists** |
| Older Pi | `gpiozero` + `lgpio` | Resets |

---

## pin_config.json format

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
      "description": "Relay controlling front door lock (active LOW)"
    },
    "motion_sensor": {
      "pin": 4,
      "type": "input",
      "pull_up": false,
      "description": "PIR sensor in hallway — HIGH when motion detected"
    },
    "cooling_fan": {
      "pin": 18,
      "type": "pwm",
      "frequency": 100,
      "description": "PWM cooling fan — use set command with level 0.0–1.0"
    }
  }
}
```

**Device types:**

| type | Use for | Extra options |
|------|---------|---------------|
| `output` | LEDs, buzzers | — |
| `relay` | Relays | `active_low: true` |
| `input` | Buttons, PIR sensors | `pull_up: true/false` |
| `pwm` | Fans, dimmers, servos | `frequency` (Hz) |
