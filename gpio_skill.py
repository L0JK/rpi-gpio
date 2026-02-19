#!/usr/bin/env python3
"""
gpio_skill.py — GPIO Skill for OpenClaw

Pins can be addressed by BCM number OR by registered name.
Names are stored in pin_config.json and can be changed at any time.

CLI:    python3 gpio_skill.py --json '{"command":"activate","device":"17"}'
        python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
Module: from gpio_skill import activate, deactivate, toggle, read, set_level,
                               blink, pulse, wait_for, set_angle, set_mode,
                               read_all, serial_write, serial_read, serial_readline,
                               rename
"""

import json
import sys
import subprocess
import shutil
import argparse
import os
import re
import time
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "pin_config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"devices": {}}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _resolve(identifier: str | int, config: dict) -> tuple[int, dict]:
    """
    Resolve a name or BCM pin number to (pin_number, device_dict).
    If the pin is not registered, returns a minimal device dict.
    Raises ValueError if identifier cannot be resolved.
    """
    devices = config.get("devices", {})

    # 1. Try by registered name
    if str(identifier) in devices:
        d = devices[str(identifier)]
        return d["pin"], d

    # 2. Try to parse as a pin number
    try:
        pin = int(identifier)
    except (ValueError, TypeError):
        raise ValueError(
            f"'{identifier}' is not a registered name and not a pin number. "
            "Use list_devices to see registered names."
        )

    # 3. Pin number given — check if it has a registered name
    for d in devices.values():
        if d["pin"] == pin:
            return pin, d

    # 4. Unregistered pin — return a default output device
    return pin, {"pin": pin, "type": "output", "description": f"Pin {pin} (not registered)"}


# ---------------------------------------------------------------------------
# Low-level GPIO
# ---------------------------------------------------------------------------

def _pinctrl_available() -> bool:
    return shutil.which("pinctrl") is not None


def _write_pin(pin: int, value: bool) -> dict:
    if _pinctrl_available():
        level = "dh" if value else "dl"
        try:
            subprocess.run(
                ["pinctrl", "set", str(pin), "op", level],
                check=True, capture_output=True, text=True,
            )
            return {"success": True, "pin": pin, "value": value, "backend": "pinctrl"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr.strip()}
    else:
        os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
        try:
            from gpiozero import LED
            d = LED(pin)
            d.on() if value else d.off()
            d.close()
            return {"success": True, "pin": pin, "value": value, "backend": "gpiozero"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def _read_pin(pin: int, pull_up: bool = False) -> dict:
    if _pinctrl_available():
        try:
            r = subprocess.run(
                ["pinctrl", "get", str(pin)],
                check=True, capture_output=True, text=True,
            )
            raw = r.stdout.strip()
            after_pipe = raw.split("|")[1].strip() if "|" in raw else ""
            token = after_pipe.split()[0].lower() if after_pipe else ""
            value = (token == "hi") if token in ("hi", "lo") else None
            return {"success": True, "pin": pin, "value": value, "backend": "pinctrl"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr.strip()}
    else:
        os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
        try:
            from gpiozero import Button
            d = Button(pin, pull_up=pull_up)
            value = bool(d.is_pressed)
            d.close()
            return {"success": True, "pin": pin, "value": value, "backend": "gpiozero"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def _set_mode_pinctrl(pin: int, mode: str) -> dict:
    """Set pin direction without changing level (pinctrl only)."""
    flag = "ip" if mode == "input" else "op"
    try:
        subprocess.run(
            ["pinctrl", "set", str(pin), flag],
            check=True, capture_output=True, text=True,
        )
        return {"success": True, "pin": pin, "mode": mode, "backend": "pinctrl"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.stderr.strip()}


def _write_pwm(pin: int, duty_cycle: float, frequency: float = 100.0) -> dict:
    if not 0.0 <= duty_cycle <= 1.0:
        return {"success": False, "error": "duty_cycle must be 0.0–1.0"}
    os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
    try:
        from gpiozero import PWMOutputDevice
        import time
        d = PWMOutputDevice(pin, frequency=frequency)
        d.value = duty_cycle
        time.sleep(0.05)
        d.close()
        return {"success": True, "pin": pin, "duty_cycle": duty_cycle,
                "frequency": frequency, "backend": "gpiozero"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def activate(identifier: str | int, config: dict | None = None) -> dict:
    """Turn on a pin — accepts name or BCM pin number."""
    config = config or load_config()
    try:
        pin, device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    value = not device.get("active_low", False)
    result = _write_pin(pin, value)
    result.update({"device": str(identifier), "description": device.get("description", "")})
    return result


def deactivate(identifier: str | int, config: dict | None = None) -> dict:
    """Turn off a pin — accepts name or BCM pin number."""
    config = config or load_config()
    try:
        pin, device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    value = device.get("active_low", False)
    result = _write_pin(pin, value)
    result.update({"device": str(identifier), "description": device.get("description", "")})
    return result


def toggle(identifier: str | int, config: dict | None = None) -> dict:
    """Toggle a pin (on→off, off→on) — accepts name or BCM pin number."""
    config = config or load_config()
    current = read(identifier, config)
    if not current.get("success"):
        return current
    if current.get("value"):
        return deactivate(identifier, config)
    return activate(identifier, config)


def read(identifier: str | int, config: dict | None = None) -> dict:
    """Read current state of a pin — accepts name or BCM pin number."""
    config = config or load_config()
    try:
        pin, device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    result = _read_pin(pin, device.get("pull_up", False))
    result.update({"device": str(identifier), "description": device.get("description", "")})
    return result


def set_level(identifier: str | int, level: float, config: dict | None = None) -> dict:
    """Set PWM level (0.0–1.0) — accepts name or BCM pin number."""
    config = config or load_config()
    try:
        pin, device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    result = _write_pwm(pin, level, device.get("frequency", 100.0))
    result.update({"device": str(identifier), "description": device.get("description", "")})
    return result


def blink(identifier: str | int, times: int = 3,
          on_ms: int = 500, off_ms: int = 500,
          config: dict | None = None) -> dict:
    """
    Blink a pin N times.
    on_ms / off_ms: milliseconds the pin stays HIGH / LOW per cycle.
    """
    config = config or load_config()
    try:
        pin, _ = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    for i in range(times):
        r = _write_pin(pin, True)
        if not r.get("success"):
            return {**r, "completed_cycles": i}
        time.sleep(on_ms / 1000)
        r = _write_pin(pin, False)
        if not r.get("success"):
            return {**r, "completed_cycles": i}
        if i < times - 1:
            time.sleep(off_ms / 1000)

    return {"success": True, "pin": pin, "device": str(identifier),
            "times": times, "on_ms": on_ms, "off_ms": off_ms}


def pulse(identifier: str | int, duration_ms: int = 1000,
          config: dict | None = None) -> dict:
    """
    Set a pin HIGH for duration_ms milliseconds, then LOW again.
    Useful for triggering relays, door openers, buzzers.
    """
    config = config or load_config()
    try:
        pin, device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    value_on  = not device.get("active_low", False)
    value_off = device.get("active_low", False)

    r = _write_pin(pin, value_on)
    if not r.get("success"):
        return r
    time.sleep(duration_ms / 1000)
    r = _write_pin(pin, value_off)
    if not r.get("success"):
        return r

    return {"success": True, "pin": pin, "device": str(identifier),
            "duration_ms": duration_ms}


def wait_for(identifier: str | int, state: bool = True,
             timeout_s: float = 30.0, poll_ms: int = 100,
             config: dict | None = None) -> dict:
    """
    Block until a pin reaches the desired state (True=HIGH, False=LOW),
    or until timeout_s seconds have passed.

    Ideal for sensors: wait_for("motion_sensor", state=True, timeout_s=60)
    Returns elapsed_s and whether the state was reached.
    """
    config = config or load_config()
    try:
        pin, device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    pull_up = device.get("pull_up", False)
    deadline = time.monotonic() + timeout_s
    interval = poll_ms / 1000

    while time.monotonic() < deadline:
        r = _read_pin(pin, pull_up)
        if not r.get("success"):
            return r
        if r.get("value") == state:
            elapsed = round(timeout_s - (deadline - time.monotonic()), 3)
            return {"success": True, "pin": pin, "device": str(identifier),
                    "value": state, "elapsed_s": elapsed,
                    "description": device.get("description", "")}
        time.sleep(interval)

    return {"success": False, "timed_out": True, "pin": pin,
            "device": str(identifier), "timeout_s": timeout_s,
            "error": f"Timed out after {timeout_s}s — pin never reached {'HIGH' if state else 'LOW'}"}


def set_angle(identifier: str | int, angle: float,
              config: dict | None = None) -> dict:
    """
    Set a servo to an angle (0–180 degrees).
    The device must be type 'servo' in pin_config.json (uses 50 Hz PWM).
    Duty cycle: 0° = 5% (1 ms pulse), 180° = 10% (2 ms pulse).
    """
    if not 0 <= angle <= 180:
        return {"success": False, "error": "angle must be 0–180 degrees"}

    config = config or load_config()
    try:
        pin, _ = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Standard servo: 50 Hz, 1–2 ms pulse within 20 ms period
    duty = (angle / 180.0 * 0.05) + 0.05   # maps 0° → 0.05, 180° → 0.10
    result = _write_pwm(pin, duty, frequency=50.0)
    result.update({"device": str(identifier), "angle": angle})
    return result


def set_mode(identifier: str | int, mode: str,
             config: dict | None = None) -> dict:
    """
    Explicitly set a pin as 'input' or 'output' without changing its level.
    Requires pinctrl (Raspberry Pi 5).
    """
    if mode not in ("input", "output"):
        return {"success": False, "error": "mode must be 'input' or 'output'"}
    if not _pinctrl_available():
        return {"success": False, "error": "set_mode requires pinctrl (Raspberry Pi 5 only)"}

    config = config or load_config()
    try:
        pin, _ = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    result = _set_mode_pinctrl(pin, mode)
    result["device"] = str(identifier)
    return result


def read_all(config: dict | None = None) -> dict:
    """
    Read all registered input/sensor pins in one call.
    Returns a dict of {device_name: value} for every input and sensor device.
    """
    config = config or load_config()
    results = {}
    errors = {}

    for name, device in config.get("devices", {}).items():
        if device.get("type") in ("input", "sensor"):
            r = _read_pin(device["pin"], device.get("pull_up", False))
            if r.get("success"):
                results[name] = {
                    "value": r.get("value"),
                    "pin": device["pin"],
                    "description": device.get("description", ""),
                }
            else:
                errors[name] = r.get("error")

    return {
        "success": True,
        "readings": results,
        **({"errors": errors} if errors else {}),
    }


def dht_read(identifier: str | int, sensor_type: str = "DHT22",
             config: dict | None = None) -> dict:
    """
    Read temperature and humidity from a DHT11 or DHT22 sensor.
    The sensor's data pin connects to a single GPIO pin.
    Requires: pip install adafruit-circuitpython-dht

    sensor_type: "DHT22" (default, more accurate) or "DHT11"
    """
    try:
        import adafruit_dht
        import board
    except ImportError:
        return {"success": False,
                "error": "Missing library. Run: pip install adafruit-circuitpython-dht"}

    config = config or load_config()
    try:
        pin, _ = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Map BCM pin number to board.GPIOXX attribute
    board_pin = getattr(board, f"D{pin}", None)
    if board_pin is None:
        return {"success": False, "error": f"BCM pin {pin} is not available as board.D{pin}"}

    sensor_cls = adafruit_dht.DHT22 if sensor_type.upper() == "DHT22" else adafruit_dht.DHT11
    dht = sensor_cls(board_pin, use_pulseio=False)
    try:
        temperature = dht.temperature   # Celsius
        humidity = dht.humidity         # %
        return {
            "success": True,
            "pin": pin,
            "device": str(identifier),
            "sensor_type": sensor_type.upper(),
            "temperature_c": round(temperature, 1),
            "temperature_f": round(temperature * 9 / 5 + 32, 1),
            "humidity_pct": round(humidity, 1),
        }
    except RuntimeError as e:
        # DHT sensors occasionally fail to read — caller should retry
        return {"success": False, "error": f"Read failed (retry): {e}",
                "pin": pin, "device": str(identifier)}
    finally:
        dht.exit()


def lcd_print(text: str, line: int = 1,
              cols: int = 16, rows: int = 2,
              mode: str = "i2c",
              i2c_address: int = 0x27,
              rs_pin: int | None = None,
              e_pin: int | None = None,
              data_pins: list[int] | None = None) -> dict:
    """
    Print text to an HD44780-compatible LCD screen (16x2, 20x4, etc.).

    mode="i2c"  — LCD with PCF8574 I2C backpack (most common, uses GPIO 2/3)
                  i2c_address is typically 0x27 or 0x3F
    mode="gpio" — LCD wired directly to GPIO pins
                  Requires rs_pin, e_pin, and data_pins=[D4,D5,D6,D7]

    Requires: pip install RPLCD smbus2
    """
    try:
        from RPLCD.i2c import CharLCD as I2CLCD
        from RPLCD.gpio import CharLCD as GPIOLCD
    except ImportError:
        return {"success": False,
                "error": "Missing library. Run: pip install RPLCD smbus2"}

    try:
        if mode == "i2c":
            lcd = I2CLCD(
                i2c_expander="PCF8574",
                address=i2c_address,
                cols=cols, rows=rows,
                dotsize=8,
            )
        elif mode == "gpio":
            if not all([rs_pin, e_pin, data_pins]) or len(data_pins) != 4:
                return {"success": False,
                        "error": "gpio mode requires rs_pin, e_pin, and data_pins=[D4,D5,D6,D7]"}
            lcd = GPIOLCD(
                numbering_mode="BCM",
                cols=cols, rows=rows,
                pin_rs=rs_pin, pin_e=e_pin,
                pins_data=data_pins,
            )
        else:
            return {"success": False, "error": "mode must be 'i2c' or 'gpio'"}

        # Truncate / pad text to fit the line width
        display_text = text[:cols].ljust(cols)
        lcd.cursor_pos = (line - 1, 0)
        lcd.write_string(display_text)
        lcd.close(clear=False)

        return {"success": True, "mode": mode, "line": line,
                "cols": cols, "rows": rows, "text": display_text.rstrip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lcd_clear(cols: int = 16, rows: int = 2,
              mode: str = "i2c", i2c_address: int = 0x27,
              rs_pin: int | None = None, e_pin: int | None = None,
              data_pins: list[int] | None = None) -> dict:
    """Clear all text from the LCD screen."""
    try:
        from RPLCD.i2c import CharLCD as I2CLCD
        from RPLCD.gpio import CharLCD as GPIOLCD
    except ImportError:
        return {"success": False,
                "error": "Missing library. Run: pip install RPLCD smbus2"}
    try:
        if mode == "i2c":
            lcd = I2CLCD("PCF8574", address=i2c_address, cols=cols, rows=rows, dotsize=8)
        else:
            if not all([rs_pin, e_pin, data_pins]):
                return {"success": False, "error": "gpio mode requires rs_pin, e_pin, data_pins"}
            lcd = GPIOLCD("BCM", cols=cols, rows=rows,
                          pin_rs=rs_pin, pin_e=e_pin, pins_data=data_pins)
        lcd.clear()
        lcd.close(clear=False)
        return {"success": True, "mode": mode}
    except Exception as e:
        return {"success": False, "error": str(e)}


def serial_write(data: str, port: str = "/dev/serial0",
                 baud: int = 9600, encoding: str = "utf-8") -> dict:
    """
    Send a string over UART (GPIO 14=TX, 15=RX).
    Default port is /dev/serial0 (hardware UART on all RPi models).
    Use /dev/ttyUSB0 for USB-serial adapters.
    """
    try:
        import serial
    except ImportError:
        return {"success": False,
                "error": "pyserial not installed. Run: pip install pyserial"}
    try:
        with serial.Serial(port, baudrate=baud, timeout=1) as ser:
            raw = data.encode(encoding)
            ser.write(raw)
        return {"success": True, "port": port, "baud": baud,
                "bytes_sent": len(raw), "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def serial_read(port: str = "/dev/serial0", baud: int = 9600,
                length: int = 256, timeout_s: float = 2.0,
                encoding: str = "utf-8") -> dict:
    """
    Read up to `length` bytes from UART within `timeout_s` seconds.
    Useful for receiving raw data from GPS modules, Arduino, etc.
    """
    try:
        import serial
    except ImportError:
        return {"success": False,
                "error": "pyserial not installed. Run: pip install pyserial"}
    try:
        with serial.Serial(port, baudrate=baud, timeout=timeout_s) as ser:
            raw = ser.read(length)
        text = raw.decode(encoding, errors="replace")
        return {"success": True, "port": port, "baud": baud,
                "bytes_received": len(raw), "data": text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def serial_readline(port: str = "/dev/serial0", baud: int = 9600,
                    timeout_s: float = 5.0, encoding: str = "utf-8") -> dict:
    """
    Read one complete line (up to newline) from UART.
    Ideal for NMEA GPS sentences, AT command responses, sensor strings.
    """
    try:
        import serial
    except ImportError:
        return {"success": False,
                "error": "pyserial not installed. Run: pip install pyserial"}
    try:
        with serial.Serial(port, baudrate=baud, timeout=timeout_s) as ser:
            raw = ser.readline()
        text = raw.decode(encoding, errors="replace").rstrip("\r\n")
        if not text:
            return {"success": False, "error": f"No line received within {timeout_s}s",
                    "port": port}
        return {"success": True, "port": port, "baud": baud,
                "data": text, "bytes_received": len(raw)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename(identifier: str | int, new_name: str, config: dict | None = None) -> dict:
    """
    Give a pin a new name (or rename an existing device).
    The old name is removed; the new name points to the same pin and keeps all settings.
    identifier can be a current name OR a BCM pin number.
    """
    save = config is None
    config = config or load_config()
    devices = config.setdefault("devices", {})

    try:
        pin, old_device = _resolve(identifier, config)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if new_name in devices and devices[new_name]["pin"] != pin:
        return {"success": False,
                "error": f"'{new_name}' is already used by pin {devices[new_name]['pin']}."}

    # Remove old entry (if it existed under a name)
    old_name = str(identifier)
    if old_name in devices:
        del devices[old_name]
    else:
        # Was referenced by number — remove whichever entry has this pin
        for k, v in list(devices.items()):
            if v["pin"] == pin:
                del devices[k]
                break

    # Write under new name
    updated = {**old_device, "pin": pin}
    devices[new_name] = updated

    if save:
        _save_config(config)

    return {"success": True, "renamed_to": new_name, "pin": pin,
            "description": updated.get("description", "")}


def register(name: str, pin: int, device_type: str = "output",
             description: str = "", **kwargs) -> dict:
    """Register a pin with a name and type. Overwrites if name already exists."""
    valid_types = ("output", "relay", "input", "sensor", "pwm", "servo")
    if device_type not in valid_types:
        return {"success": False,
                "error": f"type must be one of: {', '.join(valid_types)}"}
    config = load_config()
    config.setdefault("devices", {})[name] = {
        "pin": pin, "type": device_type, "description": description, **kwargs,
    }
    _save_config(config)
    return {"success": True, "registered": name, "pin": pin,
            "type": device_type, "description": description}


def unregister(identifier: str | int) -> dict:
    """Remove a pin's registration — accepts name or BCM pin number."""
    config = load_config()
    devices = config.get("devices", {})

    # By name
    if str(identifier) in devices:
        del devices[str(identifier)]
        _save_config(config)
        return {"success": True, "unregistered": str(identifier)}

    # By pin number
    try:
        pin = int(identifier)
        for name, d in list(devices.items()):
            if d["pin"] == pin:
                del devices[name]
                _save_config(config)
                return {"success": True, "unregistered": name, "pin": pin}
    except (ValueError, TypeError):
        pass

    return {"success": False, "error": f"'{identifier}' not found in config."}


def list_devices(config: dict | None = None) -> dict:
    """List all registered devices."""
    config = config or load_config()
    return {
        "success": True,
        "devices": [
            {"name": name, "pin": d["pin"], "type": d["type"],
             "description": d.get("description", "")}
            for name, d in config.get("devices", {}).items()
        ],
    }


# ---------------------------------------------------------------------------
# Sequence / routine engine
# ---------------------------------------------------------------------------

def _resolve_template(text: str, context: dict) -> str:
    """Replace {step_name.field} or {step_name} references with values from context."""
    def replacer(m):
        ref = m.group(1)
        parts = ref.split(".", 1)
        if len(parts) == 2:
            val = context.get(parts[0], {})
            if isinstance(val, dict):
                val = val.get(parts[1], m.group(0))
        else:
            val = context.get(parts[0], m.group(0))
        return str(val)
    return re.sub(r"\{([^}]+)\}", replacer, str(text))


def _eval_condition(condition: str, context: dict) -> bool:
    """
    Evaluate a simple comparison: '{ref} OP value'
    OP can be >, <, >=, <=, ==, !=
    Example: '{weather.humidity_pct} > 70'
    """
    resolved = _resolve_template(condition, context)
    for op_str, op_fn in [(">=", lambda a, b: a >= b),
                           ("<=", lambda a, b: a <= b),
                           ("!=", lambda a, b: str(a) != str(b)),
                           ("==", lambda a, b: str(a) == str(b)),
                           (">",  lambda a, b: a > b),
                           ("<",  lambda a, b: a < b)]:
        if op_str in resolved:
            left, right = resolved.split(op_str, 1)
            try:
                return op_fn(float(left.strip()), float(right.strip()))
            except ValueError:
                return str(left.strip()) == str(right.strip())
    # No operator — plain truthy check
    return resolved.strip().lower() not in ("false", "0", "none", "", "null")


def _apply_templates(obj, context: dict):
    """Recursively resolve {ref} templates in all string values of a dict/list."""
    if isinstance(obj, str):
        return _resolve_template(obj, context)
    if isinstance(obj, dict):
        return {k: _apply_templates(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_templates(v, context) for v in obj]
    return obj


def sequence(steps: list[dict]) -> dict:
    """
    Run a list of commands in order.

    Each step is a normal command payload, with two optional extra fields:
      "as": "name"     — store this step's result under 'name' for later references
      "on_error": "continue"  — keep running even if this step fails

    Use {name.field} in any string value to reference a previous step's result.

    Conditional step (if/then/else):
      {
        "if":   "{weather.humidity_pct} > 70",
        "then": { <command payload> },
        "else": { <command payload> }   ← optional
      }
    """
    context: dict = {}
    results = []

    for i, raw_step in enumerate(steps):
        raw_step = dict(raw_step)

        # --- if/then/else block ---
        if "if" in raw_step:
            condition_met = _eval_condition(raw_step["if"], context)
            branch_key = "then" if condition_met else "else"
            branch = raw_step.get(branch_key)
            results.append({
                "_step": i, "_type": "condition",
                "condition": raw_step["if"],
                "condition_met": condition_met,
                "branch_taken": branch_key if branch else "none",
            })
            if branch is None:
                continue
            raw_step = dict(branch)

        # --- resolve templates in this step ---
        step = _apply_templates(raw_step, context)
        step_name = raw_step.get("as", f"step_{i}")

        result = dispatch(step)
        context[step_name] = result
        results.append({**result, "_step": i, "_name": step_name})

        if not result.get("success") and raw_step.get("on_error") != "continue":
            return {
                "success": False,
                "stopped_at_step": i,
                "error": f"Step {i} ('{step_name}') failed: {result.get('error')}",
                "results": results,
            }

    return {"success": True, "steps_run": len(results), "results": results}


def save_routine(name: str, steps: list[dict], description: str = "") -> dict:
    """Save a sequence of steps as a named routine in pin_config.json."""
    config = load_config()
    config.setdefault("routines", {})[name] = {
        "description": description,
        "steps": steps,
    }
    _save_config(config)
    return {"success": True, "saved_routine": name, "steps": len(steps)}


def run_routine(name: str) -> dict:
    """Run a previously saved routine by name."""
    config = load_config()
    routine = config.get("routines", {}).get(name)
    if routine is None:
        saved = list(config.get("routines", {}).keys())
        return {"success": False,
                "error": f"Routine '{name}' not found.",
                "available_routines": saved}
    result = sequence(routine["steps"])
    result["routine"] = name
    return result


def delete_routine(name: str) -> dict:
    """Delete a saved routine."""
    config = load_config()
    if name not in config.get("routines", {}):
        return {"success": False, "error": f"Routine '{name}' not found."}
    del config["routines"][name]
    _save_config(config)
    return {"success": True, "deleted_routine": name}


def list_routines() -> dict:
    """List all saved routines."""
    config = load_config()
    routines = config.get("routines", {})
    return {
        "success": True,
        "routines": [
            {"name": name, "steps": len(r["steps"]),
             "description": r.get("description", "")}
            for name, r in routines.items()
        ],
    }


# ---------------------------------------------------------------------------
# CLI dispatcher
# ---------------------------------------------------------------------------

def dispatch(payload: dict) -> dict:
    cmd = payload.get("command", "")

    # Accepts "device" or "pin" as the identifier field
    identifier = payload.get("device") or payload.get("pin")

    if cmd == "activate":
        if identifier is None:
            return {"success": False, "error": "activate requires: device (name or pin number)"}
        return activate(identifier)

    if cmd == "deactivate":
        if identifier is None:
            return {"success": False, "error": "deactivate requires: device (name or pin number)"}
        return deactivate(identifier)

    if cmd == "toggle":
        if identifier is None:
            return {"success": False, "error": "toggle requires: device (name or pin number)"}
        return toggle(identifier)

    if cmd == "read":
        if identifier is None:
            return {"success": False, "error": "read requires: device (name or pin number)"}
        return read(identifier)

    if cmd == "set":
        level = payload.get("level")
        if identifier is None or level is None:
            return {"success": False, "error": "set requires: device (name or pin number), level (0.0–1.0)"}
        return set_level(identifier, float(level))

    if cmd == "blink":
        if identifier is None:
            return {"success": False, "error": "blink requires: device"}
        return blink(
            identifier,
            times=int(payload.get("times", 3)),
            on_ms=int(payload.get("on_ms", 500)),
            off_ms=int(payload.get("off_ms", 500)),
        )

    if cmd == "pulse":
        if identifier is None:
            return {"success": False, "error": "pulse requires: device"}
        return pulse(identifier, duration_ms=int(payload.get("duration_ms", 1000)))

    if cmd == "wait_for":
        if identifier is None:
            return {"success": False, "error": "wait_for requires: device"}
        raw_state = payload.get("state", True)
        if isinstance(raw_state, str):
            raw_state = raw_state.lower() in ("true", "1", "high", "on")
        return wait_for(
            identifier,
            state=bool(raw_state),
            timeout_s=float(payload.get("timeout_s", 30)),
            poll_ms=int(payload.get("poll_ms", 100)),
        )

    if cmd == "set_angle":
        angle = payload.get("angle")
        if identifier is None or angle is None:
            return {"success": False, "error": "set_angle requires: device, angle (0–180)"}
        return set_angle(identifier, float(angle))

    if cmd == "set_mode":
        mode = payload.get("mode", "")
        if identifier is None or not mode:
            return {"success": False, "error": "set_mode requires: device, mode ('input' or 'output')"}
        return set_mode(identifier, mode)

    if cmd == "read_all":
        return read_all()

    if cmd == "dht_read":
        if identifier is None:
            return {"success": False, "error": "dht_read requires: device (name or pin number)"}
        return dht_read(identifier, sensor_type=payload.get("sensor_type", "DHT22"))

    if cmd == "lcd_print":
        text = payload.get("text")
        if text is None:
            return {"success": False, "error": "lcd_print requires: text"}
        return lcd_print(
            text=str(text),
            line=int(payload.get("line", 1)),
            cols=int(payload.get("cols", 16)),
            rows=int(payload.get("rows", 2)),
            mode=payload.get("mode", "i2c"),
            i2c_address=int(payload.get("i2c_address", 0x27)),
            rs_pin=payload.get("rs_pin"),
            e_pin=payload.get("e_pin"),
            data_pins=payload.get("data_pins"),
        )

    if cmd == "lcd_clear":
        return lcd_clear(
            cols=int(payload.get("cols", 16)),
            rows=int(payload.get("rows", 2)),
            mode=payload.get("mode", "i2c"),
            i2c_address=int(payload.get("i2c_address", 0x27)),
            rs_pin=payload.get("rs_pin"),
            e_pin=payload.get("e_pin"),
            data_pins=payload.get("data_pins"),
        )

    if cmd == "serial_write":
        data = payload.get("data")
        if data is None:
            return {"success": False, "error": "serial_write requires: data"}
        return serial_write(
            data=str(data),
            port=payload.get("port", "/dev/serial0"),
            baud=int(payload.get("baud", 9600)),
            encoding=payload.get("encoding", "utf-8"),
        )

    if cmd == "serial_read":
        return serial_read(
            port=payload.get("port", "/dev/serial0"),
            baud=int(payload.get("baud", 9600)),
            length=int(payload.get("length", 256)),
            timeout_s=float(payload.get("timeout_s", 2.0)),
            encoding=payload.get("encoding", "utf-8"),
        )

    if cmd == "serial_readline":
        return serial_readline(
            port=payload.get("port", "/dev/serial0"),
            baud=int(payload.get("baud", 9600)),
            timeout_s=float(payload.get("timeout_s", 5.0)),
            encoding=payload.get("encoding", "utf-8"),
        )

    if cmd == "rename":
        old = payload.get("device") or payload.get("pin") or payload.get("old")
        new = payload.get("new_name") or payload.get("name")
        if not old or not new:
            return {"success": False,
                    "error": "rename requires: device (current name or pin number), new_name"}
        return rename(old, new)

    if cmd == "register":
        name = payload.get("name")
        pin = payload.get("pin")
        dtype = payload.get("type", "output")
        if not name or pin is None:
            return {"success": False, "error": "register requires: name, pin. Optional: type, description"}
        extras = {k: v for k, v in payload.items()
                  if k not in ("command", "name", "pin", "type", "description")}
        return register(name, int(pin), dtype, payload.get("description", ""), **extras)

    if cmd == "unregister":
        target = payload.get("name") or payload.get("device") or payload.get("pin")
        if not target:
            return {"success": False, "error": "unregister requires: name or pin"}
        return unregister(target)

    if cmd == "list_devices":
        return list_devices()

    if cmd == "sequence":
        steps = payload.get("steps")
        if not isinstance(steps, list) or len(steps) == 0:
            return {"success": False, "error": "sequence requires: steps (non-empty list of command payloads)"}
        return sequence(steps)

    if cmd == "save_routine":
        name = payload.get("name")
        steps = payload.get("steps")
        if not name or not isinstance(steps, list):
            return {"success": False, "error": "save_routine requires: name, steps"}
        return save_routine(name, steps, payload.get("description", ""))

    if cmd == "run_routine":
        name = payload.get("name")
        if not name:
            return {"success": False, "error": "run_routine requires: name"}
        return run_routine(name)

    if cmd == "delete_routine":
        name = payload.get("name")
        if not name:
            return {"success": False, "error": "delete_routine requires: name"}
        return delete_routine(name)

    if cmd == "list_routines":
        return list_routines()

    if cmd == "list_backends":
        return {
            "success": True,
            "pinctrl_available": _pinctrl_available(),
            "gpiozero_available": True,
            "recommended_backend": "pinctrl" if _pinctrl_available() else "gpiozero",
        }

    return {
        "success": False,
        "error": (
            f"Unknown command: '{cmd}'. "
            "Valid: activate, deactivate, toggle, read, read_all, set, "
            "blink, pulse, wait_for, set_angle, set_mode, "
            "dht_read, lcd_print, lcd_clear, "
            "serial_write, serial_read, serial_readline, "
            "sequence, save_routine, run_routine, delete_routine, list_routines, "
            "rename, register, unregister, list_devices, list_backends"
        ),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="GPIO Skill for OpenClaw — control Raspberry Pi GPIO by name or pin number"
    )
    parser.add_argument("--json", metavar="JSON",
                        help='JSON payload, e.g. \'{"command":"activate","device":"17"}\'')
    args = parser.parse_args()

    raw = args.json if args.json else sys.stdin.read().strip()

    if not raw:
        print(json.dumps({"success": False,
                          "error": "No input. Use --json '...' or pipe JSON to stdin."}))
        sys.exit(1)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    result = dispatch(payload)
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
