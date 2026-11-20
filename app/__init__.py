"""
AI Chat - a normal chatbot with Home, Chat, History and Settings pages.

create_app() is the "application factory": it builds the Flask app, connects the
database and registers the two blueprints:
    pages.py -> the HTML pages
    api.py   -> the JSON endpoints that the JavaScript calls
"""
import os

from flask import Flask

from . import db

try:                                   # optional: read a .env file (LLM_API_KEY=...)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def create_app(test_config=None):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__)
    # Vercel's filesystem is read-only except /tmp, so the SQLite file must live there.
    default_db = "/tmp/chat.db" if os.environ.get("VERCEL") else os.path.join(root, "chat.db")
    app.config.from_mapping(DATABASE=os.environ.get("DATABASE_PATH", default_db))
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from . import api, pages
    app.register_blueprint(pages.bp)
    app.register_blueprint(api.bp)

    with app.app_context():
        db.init_db()
    return app
