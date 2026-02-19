# GPIO Control Skill

Control Raspberry Pi GPIO pins by name or BCM pin number.
Devices are defined in `pin_config.json`. The AI works with names — never raw pin numbers — once a pin is registered.

Supports: digital output, digital input, PWM, servo control, PIR motion sensors, DHT11/DHT22 temperature+humidity sensors, HD44780 LCD screens, UART serial communication, and timed pulses.

---

## Setup

Install Python dependencies if not on RPi 5:
```bash
pip install gpiozero lgpio
```

On Raspberry Pi 5, `pinctrl` is used automatically (pre-installed) — no extra packages needed.

---

## Addressing pins

All commands accept **either** a registered name **or** a BCM pin number:

```
"device": "kitchen_light"   ← registered name
"device": "17"              ← BCM pin number (works even without registration)
```

> When the user mentions what something is connected to, immediately call `rename` or `register` to save the name for future sessions.

---

## How to invoke

```bash
python3 gpio_skill.py --json '<JSON payload>'
```

Returns a single JSON object. Always check `"success"` first.

---

## Commands

### `activate` — Set a pin HIGH (give power)

Works with types: `output`, `relay`

```bash
python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"activate","device":"17"}'
```
```json
{"success": true, "pin": 17, "value": true, "device": "kitchen_light", "backend": "pinctrl"}
```

---

### `deactivate` — Set a pin LOW (cut power)

```bash
python3 gpio_skill.py --json '{"command":"deactivate","device":"kitchen_light"}'
```

---

### `toggle` — Flip current state (on→off, off→on)

```bash
python3 gpio_skill.py --json '{"command":"toggle","device":"kitchen_light"}'
```

---

### `blink` — Blink a pin N times

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `device` | string | required | Name or pin number |
| `times` | int | `3` | Number of blink cycles |
| `on_ms` | int | `500` | Milliseconds HIGH per cycle |
| `off_ms` | int | `500` | Milliseconds LOW per cycle |

```bash
python3 gpio_skill.py --json '{"command":"blink","device":"status_led","times":5,"on_ms":200,"off_ms":200}'
```
```json
{"success": true, "pin": 17, "device": "status_led", "times": 5, "on_ms": 200, "off_ms": 200}
```

---

### `pulse` — Set HIGH for N milliseconds, then LOW

Useful for relays, door openers, and buzzers that only need a brief trigger.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `device` | string | required | Name or pin number |
| `duration_ms` | int | `1000` | Time to stay HIGH (ms) |

```bash
python3 gpio_skill.py --json '{"command":"pulse","device":"front_door_relay","duration_ms":500}'
```
```json
{"success": true, "pin": 27, "device": "front_door_relay", "duration_ms": 500}
```

---

### `set` — Set PWM duty cycle (fans, dimmers)

`level` is `0.0` (off) to `1.0` (full power).

```bash
python3 gpio_skill.py --json '{"command":"set","device":"cooling_fan","level":0.7}'
```
```json
{"success": true, "pin": 18, "duty_cycle": 0.7, "frequency": 100.0, "device": "cooling_fan"}
```

---

### `set_angle` — Set servo position (0–180 degrees)

Device should be registered as type `servo`. Uses standard 50 Hz PWM (1–2 ms pulse).

```bash
python3 gpio_skill.py --json '{"command":"set_angle","device":"camera_servo","angle":90}'
```
```json
{"success": true, "pin": 12, "device": "camera_servo", "angle": 90, "duty_cycle": 0.075}
```

---

### `read` — Read current state of a pin

Returns `"value": true` for HIGH (3.3 V), `"value": false` for LOW (GND).
Works with all device types.

```bash
python3 gpio_skill.py --json '{"command":"read","device":"motion_sensor"}'
python3 gpio_skill.py --json '{"command":"read","device":"4"}'
```
```json
{"success": true, "pin": 4, "value": true, "device": "motion_sensor", "description": "PIR sensor in hallway"}
```

---

### `read_all` — Read every input and sensor pin at once

Returns readings for all devices registered as type `input` or `sensor`.

```bash
python3 gpio_skill.py --json '{"command":"read_all"}'
```
```json
{
  "success": true,
  "readings": {
    "motion_sensor": {"value": false, "pin": 4,  "description": "PIR sensor in hallway"},
    "door_contact":  {"value": true,  "pin": 23, "description": "Reed switch on front door"}
  }
}
```

---

### `wait_for` — Block until a pin reaches a state

The primary command for reacting to sensor events. Polls the pin until it reaches `state`, or until the timeout expires.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `device` | string | required | Name or pin number |
| `state` | bool | `true` | `true` = wait for HIGH, `false` = wait for LOW |
| `timeout_s` | float | `30` | Maximum seconds to wait |
| `poll_ms` | int | `100` | Polling interval in milliseconds |

```bash
# Wait up to 60 seconds for motion
python3 gpio_skill.py --json '{"command":"wait_for","device":"motion_sensor","state":true,"timeout_s":60}'
```
```json
{"success": true, "pin": 4, "device": "motion_sensor", "value": true, "elapsed_s": 3.2}
```

On timeout:
```json
{"success": false, "timed_out": true, "timeout_s": 60, "error": "Timed out after 60s — pin never reached HIGH"}
```

---

### `rename` — Give a pin a name or change an existing name

`device` can be the current name or a raw pin number.
Old name is removed. New name is saved immediately to `pin_config.json`.

```bash
python3 gpio_skill.py --json '{"command":"rename","device":"17","new_name":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"rename","device":"kitchen_light","new_name":"counter_strip"}'
```
```json
{"success": true, "renamed_to": "kitchen_light", "pin": 17}
```

---

### `register` — Add a pin with full configuration

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Friendly name |
| `pin` | yes | BCM pin number |
| `type` | no | `output` (default), `relay`, `input`, `sensor`, `pwm`, `servo` |
| `description` | no | What is connected |
| `active_low` | no | `true` for relays wired active-LOW |
| `pull_up` | no | `true` to enable pull-up resistor |
| `frequency` | no | PWM frequency in Hz (default `100`) |

```bash
python3 gpio_skill.py --json '{
  "command": "register",
  "name": "door_bell",
  "pin": 23,
  "type": "input",
  "pull_up": true,
  "description": "Doorbell button at front door"
}'
```

---

### `unregister` — Remove a pin registration

```bash
python3 gpio_skill.py --json '{"command":"unregister","name":"kitchen_light"}'
python3 gpio_skill.py --json '{"command":"unregister","pin":"17"}'
```

---

### `list_devices` — Show all registered pins

Always call this first when unsure what devices exist.

```bash
python3 gpio_skill.py --json '{"command":"list_devices"}'
```

---

### `dht_read` — Read temperature and humidity (DHT11 / DHT22)

The sensor's data wire connects to a single GPIO pin.
Requires: `pip install adafruit-circuitpython-dht`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `device` | name or pin | required | GPIO data pin of the sensor |
| `sensor_type` | string | `"DHT22"` | `"DHT22"` (accurate) or `"DHT11"` (cheaper) |

```bash
python3 gpio_skill.py --json '{"command":"dht_read","device":"humidity_sensor","sensor_type":"DHT22"}'
python3 gpio_skill.py --json '{"command":"dht_read","device":"4"}'
```
```json
{
  "success": true,
  "pin": 4,
  "device": "humidity_sensor",
  "sensor_type": "DHT22",
  "temperature_c": 21.4,
  "temperature_f": 70.5,
  "humidity_pct": 58.2
}
```

> DHT sensors occasionally fail to return data. If `success` is `false` with "retry" in the error, simply call `dht_read` again.

---

### `lcd_print` — Write text to an HD44780 LCD screen

Supports 16x2, 20x4, and other sizes. Works via I2C backpack (most common) or direct GPIO wiring.
Requires: `pip install RPLCD smbus2`

**I2C mode** (LCD with PCF8574 backpack — uses GPIO 2/3):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string | required | Text to display |
| `line` | int | `1` | Screen line (1-indexed) |
| `cols` | int | `16` | Screen width in characters |
| `rows` | int | `2` | Screen height in lines |
| `mode` | string | `"i2c"` | `"i2c"` or `"gpio"` |
| `i2c_address` | int | `0x27` | I2C address (try `0x3F` if `0x27` doesn't work) |

```bash
python3 gpio_skill.py --json '{"command":"lcd_print","text":"Hello world!","line":1}'
python3 gpio_skill.py --json '{"command":"lcd_print","text":"Temp: 21.4C","line":2}'
```
```json
{"success": true, "mode": "i2c", "line": 1, "cols": 16, "text": "Hello world!"}
```

**GPIO mode** (LCD wired directly — 6 pins):

```bash
python3 gpio_skill.py --json '{
  "command": "lcd_print",
  "text": "Hello!",
  "mode": "gpio",
  "rs_pin": 26,
  "e_pin": 19,
  "data_pins": [13, 6, 5, 11]
}'
```

---

### `lcd_clear` — Clear the LCD screen

Same parameters as `lcd_print` (mode, i2c_address, etc.), no `text` or `line` needed.

```bash
python3 gpio_skill.py --json '{"command":"lcd_clear"}'
```

---

### Motion sensors (PIR)

PIR motion sensors output a simple HIGH/LOW digital signal — use the standard `read` and `wait_for` commands. Register the pin as type `sensor`.

```bash
# Check right now
python3 gpio_skill.py --json '{"command":"read","device":"motion_sensor"}'

# Block until motion is detected (up to 60 s)
python3 gpio_skill.py --json '{"command":"wait_for","device":"motion_sensor","state":true,"timeout_s":60}'
```

Register a PIR sensor:
```bash
python3 gpio_skill.py --json '{
  "command": "register",
  "name": "motion_sensor",
  "pin": 4,
  "type": "sensor",
  "description": "PIR motion sensor in hallway — HIGH when motion detected"
}'
```

---

### `serial_write` — Send data over UART

GPIO 14 = TX, GPIO 15 = RX. Default port is `/dev/serial0` (hardware UART).
Use `/dev/ttyUSB0` for USB-to-serial adapters.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data` | string | required | Text to send |
| `port` | string | `/dev/serial0` | Serial port |
| `baud` | int | `9600` | Baud rate |

```bash
python3 gpio_skill.py --json '{"command":"serial_write","data":"HELLO\n","baud":9600}'
```
```json
{"success": true, "port": "/dev/serial0", "baud": 9600, "bytes_sent": 6, "data": "HELLO\n"}
```

---

### `serial_readline` — Read one line from UART

Reads until newline or timeout. Ideal for GPS (NMEA), AT commands, sensor strings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `port` | string | `/dev/serial0` | Serial port |
| `baud` | int | `9600` | Baud rate |
| `timeout_s` | float | `5.0` | Max seconds to wait for a line |

```bash
python3 gpio_skill.py --json '{"command":"serial_readline","baud":9600}'
```
```json
{"success": true, "port": "/dev/serial0", "baud": 9600, "data": "$GPRMC,123519,A,4807.038,N,..."}
```

---

### `serial_read` — Read raw bytes from UART

Reads up to `length` bytes within `timeout_s` seconds.

```bash
python3 gpio_skill.py --json '{"command":"serial_read","length":64,"timeout_s":2}'
```
```json
{"success": true, "port": "/dev/serial0", "bytes_received": 12, "data": "sensor_value"}
```

---

### `set_mode` — Set pin direction (RPi 5 only)

Set a pin explicitly as `input` or `output` without changing its level.

```bash
python3 gpio_skill.py --json '{"command":"set_mode","device":"17","mode":"output"}'
```

---

## Error format

```json
{"success": false, "error": "Unknown device: 'oven'. Call list_devices() to see all."}
```

---

---

## Combining commands — sequences and routines

### `sequence` — Run multiple commands in one call

Steps run in order. Use `"as": "name"` to store a step's result, then reference it with `{name.field}` in later steps.

Add `"if"` / `"then"` / `"else"` for conditional logic.

**Example — read humidity, show on LCD, signal a pin:**
```bash
python3 gpio_skill.py --json '{
  "command": "sequence",
  "steps": [
    {
      "command": "dht_read",
      "device": "humidity_sensor",
      "as": "weather"
    },
    {
      "command": "lcd_print",
      "text": "Temp: {weather.temperature_c}C",
      "line": 1
    },
    {
      "command": "lcd_print",
      "text": "Hum:  {weather.humidity_pct}%",
      "line": 2
    },
    {
      "if":   "{weather.humidity_pct} > 70",
      "then": {"command": "activate",   "device": "warning_led"},
      "else": {"command": "deactivate", "device": "warning_led"}
    }
  ]
}'
```

**Reference syntax:** `{step_name.field}` — any field from the named step's JSON result.
**Operators in `if`:** `>`, `<`, `>=`, `<=`, `==`, `!=`

Add `"on_error": "continue"` to a step to keep running even if it fails.

---

### `save_routine` — Save a sequence with a name

```bash
python3 gpio_skill.py --json '{
  "command": "save_routine",
  "name": "humidity_check",
  "description": "Read humidity, show on LCD, warn if above 70%",
  "steps": [
    {"command": "dht_read",  "device": "humidity_sensor", "as": "weather"},
    {"command": "lcd_print", "text": "Temp: {weather.temperature_c}C", "line": 1},
    {"command": "lcd_print", "text": "Hum:  {weather.humidity_pct}%",  "line": 2},
    {
      "if":   "{weather.humidity_pct} > 70",
      "then": {"command": "activate",   "device": "warning_led"},
      "else": {"command": "deactivate", "device": "warning_led"}
    }
  ]
}'
```
```json
{"success": true, "saved_routine": "humidity_check", "steps": 4}
```

---

### `run_routine` — Run a saved routine by name

```bash
python3 gpio_skill.py --json '{"command":"run_routine","name":"humidity_check"}'
```
```json
{
  "success": true,
  "routine": "humidity_check",
  "steps_run": 4,
  "results": [...]
}
```

---

### `list_routines` — See all saved routines

```bash
python3 gpio_skill.py --json '{"command":"list_routines"}'
```
```json
{
  "success": true,
  "routines": [
    {"name": "humidity_check", "steps": 4, "description": "Read humidity, show on LCD, warn if above 70%"}
  ]
}
```

---

### `delete_routine` — Remove a saved routine

```bash
python3 gpio_skill.py --json '{"command":"delete_routine","name":"humidity_check"}'
```

---

## Decision guide

| User says | Command to use |
|-----------|----------------|
| "Turn on pin 17" | `activate`, device `"17"` |
| "Turn off the kitchen light" | `deactivate`, device `"kitchen_light"` |
| "Toggle the fan" | `toggle`, device name |
| "Blink the LED 3 times" | `blink`, device + `times: 3` |
| "Trigger the door relay for 1 second" | `pulse`, device + `duration_ms: 1000` |
| "Set the fan to 60%" | `set`, device + `level: 0.6` |
| "Point the servo at 45 degrees" | `set_angle`, device + `angle: 45` |
| "Is there motion?" | `read`, device `"motion_sensor"` |
| "Wait until motion is detected" | `wait_for`, device + `state: true` + `timeout_s` |
| "Check all sensors" | `read_all` |
| "I connected a buzzer to pin 22" | Ask for a name, then `rename` device `"22"` |
| "Call pin 17 'kitchen light'" | `rename`, device `"17"`, new_name `"kitchen_light"` |
| "What is connected?" | `list_devices` |
| "Remove the kitchen light" | `unregister`, name `"kitchen_light"` |
| "Read humidity and show on screen" | `sequence` with `dht_read` + `lcd_print` steps |
| "If humidity is high, turn on fan" | `sequence` with `if`/`then`/`else` block |
| "Save this as a routine" | `save_routine` with name + steps |
| "Run the humidity check" | `run_routine`, name `"humidity_check"` |
| "What routines are saved?" | `list_routines` |
| "What is the temperature?" | `dht_read`, device (data pin or name) |
| "What is the humidity?" | `dht_read` — returns both temp and humidity |
| "Show text on the screen" | `lcd_print`, text + line |
| "Clear the display" | `lcd_clear` |
| "Is there motion?" | `read`, device `"motion_sensor"` |
| "Wait until motion is detected" | `wait_for`, device + `state: true` + `timeout_s` |
| "Send 'ON' over serial" | `serial_write`, data `"ON\n"` |
| "Read a line from GPS module" | `serial_readline`, baud `9600` |
| "Read data from Arduino" | `serial_readline` or `serial_read` |
