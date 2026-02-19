#!/usr/bin/env python3
"""
gpio_skill.py — GPIO Skill for OpenClaw

Pins can be addressed by BCM number OR by registered name.
Names are stored in pin_config.json and can be changed at any time.

CLI:    python3 gpio_skill.py --json '{"command":"activate","device":"17"}'
        python3 gpio_skill.py --json '{"command":"activate","device":"kitchen_light"}'
Module: from gpio_skill import activate, deactivate, toggle, read, set_level, rename
"""

import json
import sys
import subprocess
import shutil
import argparse
import os
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
    valid_types = ("output", "relay", "input", "pwm")
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
            "Valid: activate, deactivate, toggle, read, set, rename, "
            "register, unregister, list_devices, list_backends"
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
