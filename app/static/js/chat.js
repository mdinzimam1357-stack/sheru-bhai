/* chat.js - the Chat page.
   Flow: Send -> POST /api/chat -> Flask asks the model -> JSON answer -> draw it. */

const initial = JSON.parse($("#initial").textContent);
const state = {conversationId: initial.conversation_id, busy: false};
const messagesBox = $("#messages");
const input = $("#input");
const sendButton = $("#send");

function scrollToBottom() { messagesBox.scrollTop = messagesBox.scrollHeight; }

function formatTime(iso) {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
}

/** Build one message row. role = "user" | "assistant" | "error". */
function addMessage(role, text, {time, model, retry} = {}) {
  $("#empty-state").hidden = true;
  const row = document.createElement("div");
  row.className = "msg " + (role === "user" ? "user" : "assistant") + (role === "error" ? " error" : "");

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "You" : "AI";

  const body = document.createElement("div");
  body.className = "msg-body";
  const name = document.createElement("div");
  name.className = "msg-name";
  name.textContent = (role === "user" ? "You" : initial.bot_name) + " · " + formatTime(time) + (model ? " · " + model : "");

  const content = document.createElement("div");
  content.className = "msg-content";
  if (role === "assistant") content.innerHTML = renderMarkdown(text);   // safe: escaped first
  else content.textContent = text;                                       // plain text

  body.append(name, content);
  if (role === "assistant" || role === "error") {
    const tools = document.createElement("div");
    tools.className = "msg-tools";
    const first = document.createElement("button");
    if (role === "assistant") {
      first.textContent = "Copy";
      first.onclick = async () => { await navigator.clipboard.writeText(text).catch(() => {}); first.textContent = "Copied!"; setTimeout(() => (first.textContent = "Copy"), 1500); };
    } else if (retry) {
      first.textContent = "Try again";
      first.onclick = () => { row.previousElementSibling?.remove(); row.remove(); send(retry); };   // drop old bubble, resend
    }
    if (first.textContent) tools.append(first);
    body.append(tools);
  }
  row.append(avatar, body);
  messagesBox.append(row);
  scrollToBottom();
  return row;
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "msg assistant";
  row.innerHTML = '<div class="avatar">AI</div><div class="msg-body"><div class="msg-content typing"><span></span><span></span><span></span></div></div>';
  messagesBox.append(row);
  scrollToBottom();
  return row;
}

function setBusy(busy) {
  state.busy = busy;
  sendButton.disabled = busy;
  input.disabled = busy;
  if (!busy) input.focus();
}

async function send(text) {
  text = text.trim();
  if (!text || state.busy) return;
  setBusy(true);
  addMessage("user", text);
  const typing = addTyping();

  const {ok, data} = await api("/api/chat", {
    method: "POST",
    body: {message: text, conversation_id: state.conversationId},
  });
  typing.remove();

  if (!ok) {
    const row = addMessage("error", data.error || "Something went wrong.", {retry: data.code === "not_configured" ? undefined : text});
    if (data.code === "not_configured" || data.code === "auth") {
      const link = document.createElement("a");
      link.href = "/settings";
      link.textContent = "Open Settings";
      row.querySelector(".msg-tools").append(link);
    }
    // the failed question was not saved, so a retry will not create a duplicate
    setBusy(false);
    return;
  }

  addMessage("assistant", data.reply, {model: data.model});
  if (data.created) {                                   // first message: the chat now exists
    state.conversationId = data.conversation_id;
    history.replaceState(null, "", "/chat/" + data.conversation_id);
  }
  $("#chat-title").textContent = data.title;
  setBusy(false);
}

// ---------------------------------------------------------------- events
$("#composer").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value;
  input.value = "";
  autosize();
  send(text);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    $("#composer").requestSubmit();
  }
});

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
}
input.addEventListener("input", autosize);

document.querySelectorAll("[data-prompt]").forEach((card) =>
  card.addEventListener("click", () => send(card.dataset.prompt)));

// ----------------------------------------------------------------- start
for (const m of initial.messages) {
  addMessage(m.role, m.content, {time: m.created_at, model: m.role === "assistant" ? m.model : null});
}
scrollToBottom();
input.focus();
if (initial.auto_prompt && !initial.messages.length) {    // came from a Home page suggestion
  history.replaceState(null, "", "/chat");
  send(initial.auto_prompt);
}
