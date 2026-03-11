"""
core/smart_home.py — Alexa/Smart Home integration for Ember AI.

How it works:
  1. User speaks a smart home command (e.g. "أطفئي النور في الغرفة")
  2. DeepSeek is given a tool definition for `control_device`
  3. LLM returns a tool call JSON instead of plain text
  4. execute_command() handles the actual Alexa API call
  5. Ember confirms the action verbally
"""

import asyncio
import os

# ── Config (set in .env) ──────────────────────────────────────────────────────
ALEXA_EMAIL    = os.getenv("ALEXA_EMAIL", "")
ALEXA_PASSWORD = os.getenv("ALEXA_PASSWORD", "")
ALEXA_URL      = os.getenv("ALEXA_URL", "amazon.com")   # or amazon.co.uk etc.

# ── Tool schema (passed to DeepSeek function calling) ─────────────────────────
SMART_HOME_TOOL = {
    "type": "function",
    "function": {
        "name": "control_device",
        "description": (
            "Control a smart home device connected to the user's Amazon Echo/Alexa. "
            "Use this when the user asks to turn on/off lights, adjust settings, "
            "or query device state."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["turn_on", "turn_off", "toggle", "set_brightness", "set_temperature", "query"],
                    "description": "The action to perform on the device.",
                },
                "device": {
                    "type": "string",
                    "description": "The device to control, e.g. 'lights', 'tv', 'ac', 'fan', 'plug'.",
                },
                "room": {
                    "type": "string",
                    "description": "Room name, e.g. 'living room', 'bedroom', 'kitchen', or 'all'.",
                    "default": "all",
                },
                "value": {
                    "type": "number",
                    "description": "Optional numeric value (e.g. brightness 0-100 or temperature).",
                },
            },
            "required": ["action", "device"],
        },
    },
}

# ── Alexa client (lazy-loaded) ────────────────────────────────────────────────
_alexa_login  = None
_alexa_ready  = False


def _get_login():
    """Lazily authenticate with Amazon Alexa. Returns AlexaLogin or None."""
    global _alexa_login, _alexa_ready
    if _alexa_ready:
        return _alexa_login
    if not ALEXA_EMAIL or not ALEXA_PASSWORD:
        print("[SmartHome] ALEXA_EMAIL / ALEXA_PASSWORD not set in .env — smart home disabled.")
        return None
    try:
        from alexapy import AlexaLogin
        login = AlexaLogin(
            url=ALEXA_URL,
            email=ALEXA_EMAIL,
            password=ALEXA_PASSWORD,
            outputpath="",
            debug=False,
        )
        asyncio.get_event_loop().run_until_complete(login.login())
        _alexa_login = login
        _alexa_ready = True
        print("[SmartHome] Alexa login successful.")
        return login
    except ImportError:
        print("[SmartHome] alexapy not installed. Run: pip install alexapy")
        return None
    except Exception as e:
        print(f"[SmartHome] Alexa login failed: {e}")
        return None


def execute_command(action: str, device: str, room: str = "all", value=None) -> str:
    """
    Execute a smart home command via Alexa API.
    Returns a human-readable result string for Ember to speak.
    """
    login = _get_login()
    if login is None:
        return "Smart home is not configured. Please add your Alexa credentials to the .env file."

    # Build a friendly command description
    room_str   = f"in the {room}" if room and room.lower() != "all" else ""
    pretty_cmd = f"{action.replace('_', ' ')} {device} {room_str}".strip()

    try:
        from alexapy import AlexaAPI

        async def _run():
            devices = await AlexaAPI.get_devices(login)
            if not devices:
                return "No Alexa devices found."

            # Try to find the target device
            target = None
            for d in devices:
                name = (d.get("accountName") or "").lower()
                if device.lower() in name or room.lower() in name:
                    target = d
                    break
            if target is None:
                target = devices[0]   # fallback to first device

            api = AlexaAPI(target, login)

            if action in ("turn_on", "turn_off", "toggle"):
                state = action == "turn_on"
                await api.set_smarthome_device_state(target.get("entityId", ""), state)
                return f"Done! I {action.replace('_', ' ')}ed the {device} {room_str}."

            elif action == "set_brightness" and value is not None:
                await api.set_smarthome_device_state(
                    target.get("entityId", ""), True, brightness=int(value)
                )
                return f"Set {device} brightness to {int(value)}% {room_str}."

            elif action == "query":
                state = await api.get_smarthome_device_state(target.get("entityId", ""))
                return f"The {device} {room_str} is currently {state}."

            else:
                return f"I tried to {pretty_cmd}, but this action isn't fully supported yet."

        return asyncio.get_event_loop().run_until_complete(_run())

    except Exception as e:
        print(f"[SmartHome] command error: {e}")
        return f"I couldn't execute that command right now. Error: {e}"
