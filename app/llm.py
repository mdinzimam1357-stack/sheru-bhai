"""
llm.py - talks to the AI model. It knows NOTHING about Flask or the database.

Input : the settings (provider, api key, model ...) + a list of messages
Output: the model's answer as text

Supported providers: Anthropic (Claude), OpenAI (GPT), Google Gemini, and "custom"
(any OpenAI-compatible server: OpenRouter, Groq, Together, a local Ollama ...).
"""
from datetime import datetime

import requests

PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "default_model": "claude-sonnet-5-5",
        "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"],
        "key_url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o"],
        "key_url": "https://platform.openai.com/api-keys",
    },
    "gemini": {
        "label": "Google (Gemini)",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash"],
        "key_url": "https://aistudio.google.com/apikey",
    },
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "default_model": "",
        "models": [],
        "key_url": "",
    },
}


class LLMError(Exception):
    """Something went wrong while asking the model. `code` helps the page react."""

    def __init__(self, message, code="provider"):
        super().__init__(message)
        self.code = code


def effective_model(s):
    return s.get("model") or PROVIDERS[s["provider"]]["default_model"]


def is_ready(s):
    """Can we send a question right now?"""
    if s["provider"] == "custom":                       # local servers (Ollama) need no key
        return bool(s.get("base_url")) and bool(effective_model(s))
    return s["provider"] in PROVIDERS and bool(s.get("api_key"))


def build_system_prompt(s):
    today = datetime.now().astimezone().strftime("%A, %d %B %Y")
    return f"{s['system_prompt']}\n\nYour name is {s['bot_name']}. Today's date is {today}."


def build_messages(history, user_text, memory):
    """
    history = earlier messages [{'role','content'}, ...]; memory = how many to send again.
    Models want roles that alternate and start with 'user', so we tidy the list.
    """
    items = (history[-memory:] if memory > 0 else []) + [{"role": "user", "content": user_text}]
    merged = []
    for item in items:
        if merged and merged[-1]["role"] == item["role"]:
            merged[-1]["content"] += "\n\n" + item["content"]
        else:
            merged.append({"role": item["role"], "content": item["content"]})
    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    return merged


# ------------------------------------------- one request-builder per provider
def build_request(s, messages, max_tokens):
    """Return (url, headers, json_body, function_that_reads_the_answer)."""
    provider, key, model = s["provider"], s.get("api_key", ""), effective_model(s)
    system = build_system_prompt(s)
    temperature = s["temperature"]

    if provider == "anthropic":
        return (
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            {"model": model, "max_tokens": max_tokens, "temperature": temperature,
             "system": system, "messages": messages},
            lambda d: "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text"),
        )
    if provider == "gemini":
        contents = [{"role": "user" if m["role"] == "user" else "model",
                     "parts": [{"text": m["content"]}]} for m in messages]
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": key, "content-type": "application/json"},
            {"system_instruction": {"parts": [{"text": system}]}, "contents": contents,
             "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
            lambda d: "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]),
        )
    # openai + custom share the same "chat completions" format
    headers = {"content-type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    base = "https://api.openai.com/v1" if provider == "openai" else s["base_url"].rstrip("/")
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, *messages]}
    body["max_completion_tokens" if provider == "openai" else "max_tokens"] = max_tokens
    return (f"{base}/chat/completions", headers, body,
            lambda d: d["choices"][0]["message"]["content"])


def _friendly_error(response):
    """Turn an HTTP error into a short message a student can act on (never includes the key)."""
    code = response.status_code
    try:
        data = response.json()
        err = data.get("error", data) if isinstance(data, dict) else data
        detail = err.get("message") if isinstance(err, dict) else str(err)
    except ValueError:
        detail = response.text
    detail = (detail or "").strip()[:220]
    if code in (401, 403):
        return "The provider rejected the API key. Check it in Settings.", "auth"
    if code == 404:
        return f"Model or address not found. Check the model name in Settings. ({detail})", "model"
    if code == 429:
        return f"Rate limit or quota reached. Wait a moment or check your billing. ({detail})", "quota"
    return f"The provider returned HTTP {code}: {detail}", "provider"


def chat(s, messages, max_tokens=None):
    """Send the messages to the model and return the answer text. Raises LLMError."""
    if not is_ready(s):
        raise LLMError("Add your API key in Settings first.", "not_configured")
    url, headers, body, read_answer = build_request(s, messages, max_tokens or s["max_tokens"])
    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
    except requests.RequestException as error:
        raise LLMError(f"Could not reach the provider ({error.__class__.__name__}). "
                       "Check your internet connection and the address.", "network") from error
    if response.status_code != 200:
        message, code = _friendly_error(response)
        raise LLMError(message, code)
    try:
        answer = read_answer(response.json()).strip()
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMError("The provider sent an answer in an unexpected format.", "format") from error
    if not answer:
        raise LLMError("The model sent an empty answer. Try again.", "empty")
    return answer
