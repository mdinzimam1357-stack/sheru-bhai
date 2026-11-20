"""pages.py - the four HTML pages: Home, Chat, History, Settings."""
from flask import Blueprint, abort, render_template, request

from . import db, llm, settings

bp = Blueprint("pages", __name__)

PROMPTS = [
    "Explain how Flask routes work, with a small example",
    "Write a Python function that checks if a number is prime",
    "Make a 3-day study plan to learn SQL",
    "Help me write a polite email to my professor",
]


@bp.app_context_processor
def inject_settings():
    """Every template can use `cfg` (theme, bot name, is the AI ready ...)."""
    return {"cfg": settings.public(settings.load()), "prompts": PROMPTS}


@bp.route("/")
def home():
    return render_template("home.html", stats=db.stats(),
                           recent=db.list_conversations(limit=5))


@bp.route("/chat")
@bp.route("/chat/<int:conversation_id>")
def chat(conversation_id=None):
    conversation, messages = None, []
    if conversation_id is not None:
        conversation = db.get_conversation(conversation_id)
        if conversation is None:
            abort(404)
        messages = db.get_messages(conversation_id)
    return render_template("chat.html", conversation=conversation, messages=messages,
                           auto_prompt=request.args.get("prompt", "")[:300])


@bp.route("/history")
def history():
    query = request.args.get("q", "").strip()
    return render_template("history.html", conversations=db.list_conversations(query), query=query)


@bp.route("/settings")
def settings_page():
    return render_template("settings.html", providers=llm.PROVIDERS)


@bp.app_errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404
