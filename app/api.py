"""
api.py - the JSON endpoints. The JavaScript in the pages calls these with fetch().

    POST /api/chat                          send a message, get the model's answer
    GET  /api/conversations?q=              list / search chats
    PATCH/DELETE /api/conversations/<id>    rename / delete one chat
    DELETE /api/conversations               delete ALL chats
    GET  /api/conversations/<id>/export     download a chat (.md or .json)
    GET/POST /api/settings                  read / save settings
    POST /api/settings/test                 try the key before saving
    POST /api/settings/reset                back to default behaviour (keeps the API key)
"""
import re

from flask import Blueprint, Response, jsonify, request

from . import db, llm, settings

bp = Blueprint("api", __name__, url_prefix="/api")

MAX_MESSAGE = 4000
MAX_TITLE = 80


def make_title(text):
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= 50 else one_line[:47].rstrip() + "..."


def error(message, status, **extra):
    return jsonify(error=message, **extra), status


# ---------------------------------------------------------------------- chat
@bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    text = str(data.get("message", "")).strip()
    if not text:
        return error("Please type a message.", 400)
    if len(text) > MAX_MESSAGE:
        return error(f"Message is too long (max {MAX_MESSAGE} characters).", 400)

    s = settings.load()
    if not llm.is_ready(s):
        return error("Add your API key in Settings first.", 400, code="not_configured")

    conversation_id = data.get("conversation_id")
    history = []
    if conversation_id is not None:
        if not isinstance(conversation_id, int) or db.get_conversation(conversation_id) is None:
            return error("That chat does not exist.", 404)
        history = db.recent_messages(conversation_id, s["memory_messages"])

    try:                                                   # 1. ask the model
        messages = llm.build_messages(history, text, s["memory_messages"])
        reply = llm.chat(s, messages)
    except llm.LLMError as problem:
        return error(str(problem), 502, code=problem.code)

    created = conversation_id is None                      # 2. save everything (only on success)
    if created:
        conversation_id = db.create_conversation(make_title(text))
    model = llm.effective_model(s)
    db.add_message(conversation_id, "user", text)
    db.add_message(conversation_id, "assistant", reply, model)

    return jsonify(conversation_id=conversation_id, created=created, reply=reply, model=model,
                   title=db.get_conversation(conversation_id)["title"])


# ------------------------------------------------------------- conversations
@bp.get("/conversations")
def list_conversations():
    return jsonify(conversations=db.list_conversations(request.args.get("q", "").strip()))


@bp.patch("/conversations/<int:conversation_id>")
def rename_conversation(conversation_id):
    title = " ".join(str((request.get_json(silent=True) or {}).get("title", "")).split())
    if not title:
        return error("The title cannot be empty.", 400)
    if len(title) > MAX_TITLE:
        return error(f"Title is too long (max {MAX_TITLE} characters).", 400)
    if db.rename_conversation(conversation_id, title) == 0:
        return error("That chat does not exist.", 404)
    return jsonify(id=conversation_id, title=title)


@bp.delete("/conversations/<int:conversation_id>")
def delete_conversation(conversation_id):
    if db.delete_conversation(conversation_id) == 0:
        return error("That chat does not exist.", 404)
    return "", 204


@bp.delete("/conversations")
def delete_all():
    return jsonify(deleted=db.delete_all_conversations())


@bp.get("/conversations/<int:conversation_id>/export")
def export_conversation(conversation_id):
    conversation = db.get_conversation(conversation_id)
    if conversation is None:
        return error("That chat does not exist.", 404)
    messages = db.get_messages(conversation_id)
    slug = re.sub(r"[^a-z0-9]+", "-", conversation["title"].lower()).strip("-")[:40] or "chat"
    if request.args.get("format") == "json":
        body = jsonify(conversation=conversation, messages=messages).get_data(as_text=True)
        return Response(body, mimetype="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{slug}.json"'})
    lines = [f"# {conversation['title']}", ""]
    for m in messages:
        who = "You" if m["role"] == "user" else "Assistant"
        lines += [f"**{who}** ({m['created_at']})", "", m["content"], ""]
    return Response("\n".join(lines), mimetype="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="{slug}.md"'})


# ------------------------------------------------------------------ settings
@bp.get("/settings")
def get_settings():
    return jsonify(settings.public(settings.load()))


@bp.post("/settings")
def save_settings():
    errors = settings.save(request.get_json(silent=True) or {})
    if errors:
        return jsonify(error="Some values need fixing.", errors=errors), 400
    return jsonify(settings.public(settings.load()))


@bp.post("/settings/test")
def test_settings():
    """Try the values currently in the form (even if not saved yet) with a tiny question."""
    values = request.get_json(silent=True) or {}
    clean, errors = settings.validate(values)
    if errors:
        return jsonify(ok=False, error="Some values need fixing.", errors=errors)
    s = {**settings.load(), **clean}
    try:
        reply = llm.chat(s, [{"role": "user", "content": "Reply with the single word: OK"}], max_tokens=30)
    except llm.LLMError as problem:
        return jsonify(ok=False, error=str(problem), code=problem.code)
    return jsonify(ok=True, reply=reply[:80], model=llm.effective_model(s))


@bp.post("/settings/reset")
def reset_settings():
    db.delete_settings(keep=("api_key", "provider", "model", "base_url", "theme"))
    return jsonify(settings.public(settings.load()))
