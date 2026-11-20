/* common.js - small helpers used on every page */

const $ = (selector, root = document) => root.querySelector(selector);

/** fetch() wrapper for our JSON API. Always returns {ok, status, data}. */
async function api(path, options = {}) {
  const init = {headers: {"Content-Type": "application/json"}, ...options};
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  try {
    const response = await fetch(path, init);
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    return {ok: response.ok, status: response.status, data};
  } catch (error) {
    return {ok: false, status: 0, data: {error: "Cannot reach the server. Is Flask running?"}};
  }
}

let toastTimer;
function toast(message, bad = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("bad", bad);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

/** Show UTC timestamps in the visitor's own time zone. */
function localizeTimes(root = document) {
  root.querySelectorAll("time[data-utc]").forEach((el) => {
    const date = new Date(el.dataset.utc);
    if (isNaN(date)) return;
    el.textContent = date.toLocaleString([], {day: "numeric", month: "short", hour: "numeric", minute: "2-digit"});
    el.title = date.toLocaleString();
  });
}

/** Two-step button: first click asks "Sure?", second click within 3 s runs the action. */
function confirmClick(button, action) {
  let armed = false, timer;
  const label = button.textContent;
  button.addEventListener("click", () => {
    if (!armed) {
      armed = true;
      button.textContent = "Sure?";
      timer = setTimeout(() => { armed = false; button.textContent = label; }, 3000);
      return;
    }
    clearTimeout(timer);
    armed = false;
    button.textContent = label;
    action();
  });
}

// ---------------------------------------------------------------- markdown
function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Inline formatting. Everything is escaped FIRST, so model text can never inject HTML. */
function inlineMarkdown(text) {
  return text.split(/(`[^`\n]+`)/).map((part, i) => {
    if (i % 2 === 1) return "<code>" + escapeHtml(part.slice(1, -1)) + "</code>";
    let s = escapeHtml(part);
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*(?!\s)([^*\n]+?)\*(?!\w)/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
                  '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return s;
  }).join("");
}

/** A tiny, safe Markdown renderer: code blocks, lists, headings, bold, italic, links. */
function renderMarkdown(source) {
  const blocks = [];
  const text = source.replace(/```([\w+#.-]*)[ \t]*\n?([\s\S]*?)(```|$)/g, (m, lang, code) => {
    blocks.push({lang, code: code.replace(/\n$/, "")});
    return `\n\u0000${blocks.length - 1}\u0000\n`;
  });

  let html = "", paragraph = [], list = null;
  const flushParagraph = () => { if (paragraph.length) html += "<p>" + paragraph.join("<br>") + "</p>"; paragraph = []; };
  const flushList = () => { if (list) html += `</${list}>`; list = null; };
  const openList = (tag) => { flushParagraph(); if (list !== tag) { flushList(); html += `<${tag}>`; list = tag; } };

  for (const line of text.split("\n")) {
    let m;
    if ((m = line.match(/^\u0000(\d+)\u0000$/))) {
      flushParagraph(); flushList();
      const {lang, code} = blocks[Number(m[1])];
      html += `<div class="code"><div class="code-head"><span>${escapeHtml(lang || "code")}</span>` +
              `<button type="button" class="copy">Copy</button></div><pre><code>${escapeHtml(code)}</code></pre></div>`;
    } else if ((m = line.match(/^#{1,4}\s+(.*)$/))) {
      flushParagraph(); flushList(); html += `<h4>${inlineMarkdown(m[1])}</h4>`;
    } else if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) {
      openList("ul"); html += `<li>${inlineMarkdown(m[1])}</li>`;
    } else if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      openList("ol"); html += `<li>${inlineMarkdown(m[1])}</li>`;
    } else if (line.trim() === "") {
      flushParagraph(); flushList();
    } else {
      flushList(); paragraph.push(inlineMarkdown(line));
    }
  }
  flushParagraph(); flushList();
  return html;
}

// "Copy" buttons inside code blocks (one listener for the whole page)
document.addEventListener("click", async (event) => {
  const button = event.target.closest(".copy");
  if (!button) return;
  const code = button.closest(".code").querySelector("code").innerText;
  try { await navigator.clipboard.writeText(code); button.textContent = "Copied!"; }
  catch (error) { button.textContent = "Press Ctrl+C"; }
  setTimeout(() => (button.textContent = "Copy"), 1500);
});

// ------------------------------------------------------------- theme button
$("#theme-toggle").addEventListener("click", async () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  const select = $("#theme");                       // keep the Settings page in step
  if (select) select.value = next;
  await api("/api/settings", {method: "POST", body: {theme: next}});
});

localizeTimes();
