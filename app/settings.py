"""
settings.py - load, validate and save the settings page values (stored in the SQL settings table).

The API key is stored on YOUR computer only, in chat.db. It is never sent back to the
browser: the pages only receive a hint such as "•••• 9xYz".
"""
import os
import re

from . import db, llm

DEFAULT_PROMPT = (
    "You are a helpful, friendly AI assistant. Answer clearly and honestly. "
    "Use short paragraphs, bullet points and code blocks when they help. "
    "If you are not sure about something, say so instead of guessing."
)

DEFAULTS = {
    "provider": "anthropic",
    "api_key": "",
    "model": "",                 # empty = use the provider's default model
    "base_url": "",              # only for the "custom" provider
    "temperature": 0.7,
    "max_tokens": 1024,
    "memory_messages": 20,       # how many earlier messages the model sees
    "system_prompt": DEFAULT_PROMPT,
    "bot_name": "AI Assistant",
    "theme": "light",
}


def load():
    """Saved settings merged with defaults (and the LLM_API_KEY environment variable as a fallback)."""
    s = {**DEFAULTS, **db.read_settings()}
    s["temperature"] = float(s["temperature"])
    s["max_tokens"] = int(s["max_tokens"])
    s["memory_messages"] = int(s["memory_messages"])
    s["key_from_env"] = False
    if not s["api_key"] and os.environ.get("LLM_API_KEY"):
        s["api_key"], s["key_from_env"] = os.environ["LLM_API_KEY"].strip(), True
    return s


def public(s):
    """The settings that are safe to give to the browser (no secret key)."""
    key = s["api_key"]
    safe = {k: v for k, v in s.items() if k != "api_key"}
    safe.update(has_key=bool(key), api_key_hint=("•••• " + key[-4:]) if len(key) >= 8 else "••••" if key else "",
                ready=llm.is_ready(s), effective_model=llm.effective_model(s),
                provider_label=llm.PROVIDERS[s["provider"]]["label"])
    return safe


def validate(values):
    """Check what the user sent. Returns (clean_values_to_save, errors_by_field)."""
    clean, errors = {}, {}

    def text(field, max_length, required=False):
        value = str(values[field]).strip()
        if required and not value:
            errors[field] = "This cannot be empty."
        elif len(value) > max_length:
            errors[field] = f"Maximum {max_length} characters."
        else:
            clean[field] = value

    def number(field, low, high, cast):
        try:
            value = cast(values[field])
        except (TypeError, ValueError):
            errors[field] = "Enter a number."
            return
        if not low <= value <= high:
            errors[field] = f"Must be between {low} and {high}."
        else:
            clean[field] = value

    if "provider" in values:
        if values["provider"] in llm.PROVIDERS:
            clean["provider"] = values["provider"]
        else:
            errors["provider"] = "Unknown provider."
    if "model" in values:
        text("model", 100)
    if "bot_name" in values:
        text("bot_name", 40, required=True)
    if "system_prompt" in values:
        text("system_prompt", 4000, required=True)
    if "base_url" in values:
        text("base_url", 300)
        url = clean.get("base_url", "")
        if url and not re.match(r"^https?://", url):
            errors["base_url"] = "Must start with http:// or https://"
    if "temperature" in values:
        number("temperature", 0, 1, float)
    if "max_tokens" in values:
        number("max_tokens", 50, 8000, int)
    if "memory_messages" in values:
        number("memory_messages", 0, 50, int)
    if "theme" in values:
        if values["theme"] in ("light", "dark"):
            clean["theme"] = values["theme"]
        else:
            errors["theme"] = "Choose light or dark."

    # The key: an empty box means "keep the saved key". Use clear_api_key to remove it.
    key = str(values.get("api_key") or "").strip()
    if key:
        if re.search(r"\s", key) or len(key) > 300:
            errors["api_key"] = "A key has no spaces. Copy it again."
        else:
            clean["api_key"] = key
    elif values.get("clear_api_key"):
        clean["api_key"] = ""
    return clean, errors


def save(values):
    clean, errors = validate(values)
    if not errors and clean:
        db.write_settings(clean)
    return errors
