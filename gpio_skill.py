#!/usr/bin/env python3
"""
gpio_skill.py — GPIO Skill for OpenClaw
Devices are defined in pin_config.json.
The AI uses device names (e.g. "kitchen_light") — not pin numbers.

Can be used as:
  CLI:    python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
  Module: from gpio_skill import activate, read, list_devices
"""

import json
import sys
import subprocess
import shutil
import argparse
import os
from pathlib import Path
from typing import Any

CONFIG_FILE = Path(__file__).parent / "pin_config.json"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"devices": {}}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _get_device(name: str, config: dict) -> dict | None:
    return config.get("devices", {}).get(name)


# ---------------------------------------------------------------------------
# Low-level GPIO backends
# ---------------------------------------------------------------------------

def _pinctrl_available() -> bool:
    return shutil.which("pinctrl") is not None


def _write_pin(pin: int, value: bool) -> dict:
    """Write HIGH/LOW to a pin. Uses pinctrl (persistent) on RPi 5, else gpiozero."""
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
    """Read current value of a pin."""
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


def _write_pwm(pin: int, duty_cycle: float, frequency: float = 100.0) -> dict:
    """Set PWM duty cycle on a pin (0.0–1.0)."""
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
# Public API — callable as functions from other Python scripts
# ---------------------------------------------------------------------------

def activate(device_name: str, config: dict | None = None) -> dict:
    """Turn on a named output/relay device."""
    config = config or load_config()
    device = _get_device(device_name, config)
    if device is None:
        return {"success": False, "error": f"Unknown device: '{device_name}'. Call list_devices() to see all."}
    if device["type"] not in ("output", "relay"):
        return {"success": False, "error": f"'{device_name}' is type '{device['type']}', not output/relay."}
    value = not device.get("active_low", False)
    result = _write_pin(device["pin"], value)
    result.update({"device": device_name, "description": device.get("description", "")})
    return result


def deactivate(device_name: str, config: dict | None = None) -> dict:
    """Turn off a named output/relay device."""
    config = config or load_config()
    device = _get_device(device_name, config)
    if device is None:
        return {"success": False, "error": f"Unknown device: '{device_name}'. Call list_devices() to see all."}
    if device["type"] not in ("output", "relay"):
        return {"success": False, "error": f"'{device_name}' is type '{device['type']}', not output/relay."}
    value = device.get("active_low", False)
    result = _write_pin(device["pin"], value)
    result.update({"device": device_name, "description": device.get("description", "")})
    return result


def toggle(device_name: str, config: dict | None = None) -> dict:
    """Toggle a named output/relay device (on→off, off→on)."""
    config = config or load_config()
    current = read(device_name, config)
    if not current.get("success"):
        return current
    if current.get("value"):
        return deactivate(device_name, config)
    return activate(device_name, config)


def read(device_name: str, config: dict | None = None) -> dict:
    """Read current state of a named device (any type)."""
    config = config or load_config()
    device = _get_device(device_name, config)
    if device is None:
        return {"success": False, "error": f"Unknown device: '{device_name}'. Call list_devices() to see all."}
    pull_up = device.get("pull_up", False)
    result = _read_pin(device["pin"], pull_up)
    result.update({"device": device_name, "description": device.get("description", "")})
    return result


def set_level(device_name: str, level: float, config: dict | None = None) -> dict:
    """Set PWM level (0.0–1.0) for a named PWM device (fan speed, LED brightness, servo)."""
    config = config or load_config()
    device = _get_device(device_name, config)
    if device is None:
        return {"success": False, "error": f"Unknown device: '{device_name}'. Call list_devices() to see all."}
    if device["type"] != "pwm":
        return {"success": False, "error": f"'{device_name}' is type '{device['type']}', not pwm."}
    result = _write_pwm(device["pin"], level, device.get("frequency", 100.0))
    result.update({"device": device_name, "description": device.get("description", "")})
    return result


def list_devices(config: dict | None = None) -> dict:
    """Return all registered devices with their pin, type and description."""
    config = config or load_config()
    return {
        "success": True,
        "devices": [
            {
                "name": name,
                "pin": d["pin"],
                "type": d["type"],
                "description": d.get("description", ""),
            }
            for name, d in config.get("devices", {}).items()
        ],
    }


def register(name: str, pin: int, device_type: str,
             description: str = "", **kwargs) -> dict:
    """
    Add or update a device in pin_config.json.

    device_type: "output" | "relay" | "input" | "pwm"
    Extra kwargs: active_low, pull_up, frequency, etc.
    """
    valid_types = ("output", "relay", "input", "pwm")
    if device_type not in valid_types:
        return {"success": False, "error": f"type must be one of: {', '.join(valid_types)}"}
    config = load_config()
    config.setdefault("devices", {})[name] = {
        "pin": pin,
        "type": device_type,
        "description": description,
        **kwargs,
    }
    _save_config(config)
    return {"success": True, "registered": name, "pin": pin,
            "type": device_type, "description": description}


def unregister(name: str) -> dict:
    """Remove a device from pin_config.json."""
    config = load_config()
    if name not in config.get("devices", {}):
        return {"success": False, "error": f"Device '{name}' not found."}
    del config["devices"][name]
    _save_config(config)
    return {"success": True, "unregistered": name}


# ---------------------------------------------------------------------------
# CLI dispatcher
# ---------------------------------------------------------------------------

def _coerce_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "on", "high")
    raise ValueError(f"Cannot convert {val!r} to bool")


def dispatch(payload: dict) -> dict:
    cmd = payload.get("command", "")
    device = payload.get("device", "")

    if cmd == "activate":
        return activate(device)

    if cmd == "deactivate":
        return deactivate(device)

    if cmd == "toggle":
        return toggle(device)

    if cmd == "read":
        return read(device)

    if cmd == "set":
        level = payload.get("level")
        if level is None:
            return {"success": False, "error": "set requires: device, level (0.0–1.0)"}
        return set_level(device, float(level))

    if cmd == "list_devices":
        return list_devices()

    if cmd == "register":
        name = payload.get("name")
        pin = payload.get("pin")
        dtype = payload.get("type")
        if not all([name, pin is not None, dtype]):
            return {"success": False, "error": "register requires: name, pin, type. Optional: description, active_low, pull_up, frequency"}
        extras = {k: v for k, v in payload.items()
                  if k not in ("command", "name", "pin", "type", "description")}
        return register(name, int(pin), dtype, payload.get("description", ""), **extras)

    if cmd == "unregister":
        name = payload.get("name")
        if not name:
            return {"success": False, "error": "unregister requires: name"}
        return unregister(name)

    # Raw pin access (kept for advanced use)
    if cmd == "digital_write":
        pin = payload.get("pin")
        val = payload.get("value")
        if pin is None or val is None:
            return {"success": False, "error": "digital_write requires: pin, value"}
        return _write_pin(int(pin), _coerce_bool(val))

    if cmd == "digital_read":
        pin = payload.get("pin")
        if pin is None:
            return {"success": False, "error": "digital_read requires: pin"}
        return _read_pin(int(pin), bool(payload.get("pull_up", False)))

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
            "Valid commands: activate, deactivate, toggle, read, set, "
            "list_devices, register, unregister, digital_write, digital_read, list_backends"
        ),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="GPIO Skill for OpenClaw — control named devices on Raspberry Pi GPIO"
    )
    parser.add_argument("--json", metavar="JSON",
                        help='JSON payload, e.g. \'{"command":"activate","device":"kitchen_light"}\'')
    args = parser.parse_args()

    raw = args.json if args.json else sys.stdin.read().strip()

    if not raw:
        result = {"success": False,
                  "error": "No input. Use --json '...' or pipe JSON to stdin."}
        print(json.dumps(result))
        sys.exit(1)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        result = {"success": False, "error": f"Invalid JSON: {e}"}
        print(json.dumps(result))
        sys.exit(1)

    result = dispatch(payload)
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
