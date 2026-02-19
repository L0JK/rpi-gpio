# rpi-gpio — GPIO Skill for OpenClaw

A GPIO control skill for the [OpenClaw](https://github.com/openclaw) AI agent running on Raspberry Pi.

Control any GPIO pin by **name or pin number** — no need to remember BCM numbers once a pin is named. The AI can turn things on and off, read sensors, wait for events, blink LEDs, drive servos, and more.

---

## What it covers

| Category | Commands |
|----------|----------|
| Digital output | `activate`, `deactivate`, `toggle`, `blink`, `pulse` |
| Digital input / sensors | `read`, `read_all`, `wait_for` |
| PWM | `set` (0.0–1.0 duty cycle) |
| Servo | `set_angle` (0–180 °) |
| UART / Serial | `serial_write`, `serial_read`, `serial_readline` |
| Pin management | `rename`, `register`, `unregister`, `set_mode`, `list_devices` |

> **Not included:** I2C, SPI, and 1-Wire — these are bus protocols with their own addressing and timing that belong in separate skill files.

---

## Requirements

- Raspberry Pi (optimised for **RPi 5** with `pinctrl`)
- Python 3.11+
- `pip install gpiozero lgpio pyserial` — only needed as a fallback on older boards (`pyserial` needed for serial commands on all boards)

---

## Installation

```bash
git clone https://github.com/L0JK/rpi-gpio.git
cd rpi-gpio
pip install gpiozero lgpio   # skip on RPi 5
```

---

## Quick start

```bash
# Check what backend is available
python3 gpio_skill.py --json '{"command":"list_backends"}'

# Turn pin 17 on (no setup needed)
python3 gpio_skill.py --json '{"command":"activate","device":"17"}'

# Give it a name
python3 gpio_skill.py --json '{"command":"rename","device":"17","new_name":"kitchen_light"}'

# Now use the name
python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"blink","device":"kitchen_light","times":3}'
```

---

## Addressing pins

Every command accepts either a **registered name** or a **BCM pin number**:

```bash
{"command": "activate", "device": "kitchen_light"}   # by name
{"command": "activate", "device": "17"}              # by pin number — same result
```

Unregistered pins work immediately by number. Name them whenever it makes sense.

---

## Device configuration (`pin_config.json`)

Edit this file to describe what is wired to each pin:

```json
{
  "devices": {
    "kitchen_light": {
      "pin": 17,
      "type": "output",
      "description": "LED strip above kitchen counter"
    },
    "front_door_relay": {
      "pin": 27,
      "type": "relay",
      "active_low": true,
      "description": "Relay controlling front door lock (active LOW)"
    },
    "motion_sensor": {
      "pin": 4,
      "type": "sensor",
      "pull_up": false,
      "description": "PIR motion sensor in hallway — HIGH when motion detected"
    },
    "cooling_fan": {
      "pin": 18,
      "type": "pwm",
      "frequency": 100,
      "description": "PWM cooling fan — use set command with level 0.0–1.0"
    },
    "camera_servo": {
      "pin": 12,
      "type": "servo",
      "description": "Pan servo for camera mount"
    }
  }
}
```

**Device types:**

| type | Use for | Key options |
|------|---------|-------------|
| `output` | LEDs, buzzers | — |
| `relay` | Relays | `active_low: true` |
| `input` | Buttons, reed switches | `pull_up: true/false` |
| `sensor` | PIR, distance sensors — included in `read_all` | `pull_up` |
| `pwm` | Fans, dimmable LEDs | `frequency` (Hz) |
| `servo` | Servo motors — use `set_angle` | — |

---

## All commands

### Output

```bash
# Turn on / off
python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"deactivate","device":"kitchen_light"}'

# Flip current state
python3 gpio_skill.py --json '{"command":"toggle","device":"kitchen_light"}'

# Blink 5 times, 200 ms on / 200 ms off
python3 gpio_skill.py --json '{"command":"blink","device":"kitchen_light","times":5,"on_ms":200,"off_ms":200}'

# Pulse HIGH for 500 ms then LOW (relay trigger, door opener)
python3 gpio_skill.py --json '{"command":"pulse","device":"front_door_relay","duration_ms":500}'

# Fan at 70%
python3 gpio_skill.py --json '{"command":"set","device":"cooling_fan","level":0.7}'

# Servo to 90 degrees
python3 gpio_skill.py --json '{"command":"set_angle","device":"camera_servo","angle":90}'
```

### Input / sensors

```bash
# Read a single pin
python3 gpio_skill.py --json '{"command":"read","device":"motion_sensor"}'

# Read ALL input and sensor pins at once
python3 gpio_skill.py --json '{"command":"read_all"}'

# Block until motion is detected (up to 60 s)
python3 gpio_skill.py --json '{"command":"wait_for","device":"motion_sensor","state":true,"timeout_s":60}'

# Block until a button is released (goes LOW)
python3 gpio_skill.py --json '{"command":"wait_for","device":"button","state":false,"timeout_s":30}'
```

### Pin management

```bash
# List all named pins
python3 gpio_skill.py --json '{"command":"list_devices"}'

# Give pin 22 a name
python3 gpio_skill.py --json '{"command":"rename","device":"22","new_name":"bedroom_lamp"}'

# Register with full options (type, description, etc.)
python3 gpio_skill.py --json '{"command":"register","name":"door_bell","pin":23,"type":"input","pull_up":true,"description":"Front door button"}'

# Remove a registration
python3 gpio_skill.py --json '{"command":"unregister","name":"bedroom_lamp"}'

# Set pin direction explicitly (RPi 5 / pinctrl only)
python3 gpio_skill.py --json '{"command":"set_mode","device":"17","mode":"output"}'
```

---

## Use as a Python module

```python
from gpio_skill import (
    activate, deactivate, toggle,
    blink, pulse,
    read, read_all, wait_for,
    set_level, set_angle,
    rename, register, list_devices,
)

activate("kitchen_light")
activate(17)                        # same result, by pin number

blink("status_led", times=3)
pulse("door_relay", duration_ms=500)

result = wait_for("motion_sensor", state=True, timeout_s=60)
if result["success"]:
    print(f"Motion detected after {result['elapsed_s']}s")

set_level("cooling_fan", 0.6)       # 60% speed
set_angle("camera_servo", 45)       # 45 degrees

rename(22, "bedroom_lamp")
readings = read_all()               # all sensor/input pins

# Serial / UART (GPIO 14=TX, 15=RX)
serial_write("ON\n", baud=9600)
line = serial_readline(baud=9600)   # e.g. NMEA GPS sentence
```

---

## Response format

Every call returns a single JSON object:

```json
{"success": true,  "pin": 17, "value": true, "device": "kitchen_light"}
{"success": false, "error": "Unknown device: 'oven'. Call list_devices() to see all."}
```

Exit code `0` = success, `1` = error.

---

## GPIO backend

| Board | Backend | Pin state persists after script exits |
|-------|---------|---------------------------------------|
| Raspberry Pi 5 | `pinctrl` (auto-detected) | Yes |
| Older Raspberry Pi | `gpiozero` + `lgpio` | No |

On RPi 5, `pinctrl` is used automatically. Output pins stay HIGH or LOW after the script exits — no daemon needed.
