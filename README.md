# AI Chat - a normal chatbot with Flask, SQL, HTML, CSS and JavaScript

A ChatGPT-style app that runs on your own computer. Four pages, one database file.

| Page | URL | What it does |
|---|---|---|
| **Home** | `/` | Welcome, status of the AI connection, suggested prompts, recent chats |
| **Chat** | `/chat`, `/chat/<id>` | The conversation: markdown answers, code blocks with Copy, memory, retry on error |
| **History** | `/history` | Search every chat (titles and messages), rename, export (.md/.json), delete |
| **Settings** | `/settings` | **API key**, provider, model, assistant name, personality, creativity, answer length, memory, theme, reset/delete data |

![Home](docs/00_home.png)
![Chat](docs/03_chat.png)

## Run it

```bash
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000 -> **Settings** -> choose a provider -> paste your **API key** -> **Test connection** -> **Save**.
Then go to **Chat**.

Providers: Anthropic (Claude), OpenAI (GPT), Google (Gemini), or **Custom** = any OpenAI-compatible
server (OpenRouter, Groq, Together, or a local Ollama, which needs no key).

Optional: put `LLM_API_KEY=...` in a `.env` file instead of typing it in Settings.

## Tests

```bash
python -m unittest -v
```
39 tests. The AI network call is faked, so no key or internet is needed.

## Project structure

```
ai_chat/
├── run.py                  starts the app
├── requirements.txt  .env.example  .gitignore
├── app/
│   ├── __init__.py         create_app(): builds Flask, registers blueprints
│   ├── pages.py            the 4 HTML pages (blueprint)
│   ├── api.py              JSON endpoints used by JavaScript (blueprint)
│   ├── llm.py              talks to the AI providers (no Flask, no SQL)
│   ├── settings.py         load / validate / save settings
│   ├── db.py               all SQL in one place
│   ├── schema.sql          3 tables: settings, conversations, messages
│   ├── templates/          base (sidebar) + home, chat, history, settings, 404
│   └── static/
│       ├── css/style.css   light + dark theme with CSS variables, responsive
│       └── js/             common.js (helpers, markdown), chat.js, history.js, settings.js
├── tests/test_app.py
└── docs/                   screenshots
```

## How a message travels

```
You type  -->  chat.js: fetch POST /api/chat
              --> api.py: check input, load settings (SQL)
              --> llm.py: build the request for the chosen provider, call the model
              --> api.py: save question + answer (SQL), return JSON
chat.js draws the answer (markdown -> safe HTML)
```

## Security notes (good to teach)
- The API key is stored only in your local `chat.db` and is **never sent back to the browser**
  (pages get a hint like `•••• abcd`). `chat.db` and `.env` are in `.gitignore`.
- All SQL uses `?` placeholders (no SQL injection). History search escapes `%` and `_`.
- Model answers are HTML-escaped before the small markdown renderer adds formatting (no XSS).
- Server-side validation for every setting; a failed model call saves nothing.
- This is a single-user local app (no login). Do not put it on the internet as is.

## Student challenges
1. Add a "Regenerate answer" button. 2. Add a model-cost estimate. 3. Show tokens used.
4. Add "Pin" chats to the top of History. 5. Stream the answer word by word.
