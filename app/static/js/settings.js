/* settings.js - the Settings page: save, test the key, presets, reset. */

const providers = JSON.parse($("#providers").textContent);
const form = $("#settings-form");

const PERSONAS = {
  helper: "You are a helpful, friendly AI assistant. Answer clearly and honestly. Use short paragraphs, bullet points and code blocks when they help. If you are not sure about something, say so instead of guessing.",
  tutor: "You are a patient Python and web-development tutor for beginners. Explain step by step in simple words, give a small runnable example, then ask one short question to check understanding.",
  short: "You are a concise assistant. Answer in at most three sentences unless the user asks for more detail. No filler.",
  eli12: "Explain everything like the person is 12 years old: simple words, everyday examples, no jargon. If you must use a technical word, explain it right away.",
  interview: "You are an interview coach for fresher software jobs. Ask one interview question at a time, wait for the answer, then give brief, constructive feedback and a better sample answer.",
};

// ---- provider-dependent bits: model suggestions, key link, base URL box
function applyProvider() {
  const p = providers[$("#provider").value];
  $("#model-list").replaceChildren(...p.models.map((name) => Object.assign(document.createElement("option"), {value: name})));
  $("#model").placeholder = p.default_model ? `${p.default_model} (default)` : "e.g. llama3.1 or openai/gpt-4o-mini";
  $("#field-base-url").hidden = $("#provider").value !== "custom";
  const link = $("#key-link");
  link.hidden = !p.key_url;
  link.href = p.key_url || "#";
}
$("#provider").addEventListener("change", applyProvider);
applyProvider();

// ---- small live labels
$("#temperature").addEventListener("input", (e) => ($("#temp-val").textContent = e.target.value));
$("#memory_messages").addEventListener("input", (e) => ($("#mem-val").textContent = e.target.value));
$("#persona").addEventListener("change", (e) => {
  if (PERSONAS[e.target.value]) $("#system_prompt").value = PERSONAS[e.target.value];
});
$("#theme").addEventListener("change", (e) => (document.documentElement.dataset.theme = e.target.value));
$("#show-key").addEventListener("click", (e) => {
  const box = $("#api_key");
  box.type = box.type === "password" ? "text" : "password";
  e.target.textContent = box.type === "password" ? "Show" : "Hide";
});

function formValues() {
  const v = {};
  new FormData(form).forEach((value, key) => (v[key] = value));
  return v;
}

function showErrors(errors = {}) {
  document.querySelectorAll(".field-error").forEach((el) => el.remove());
  document.querySelectorAll(".field.invalid").forEach((el) => el.classList.remove("invalid"));
  for (const [name, message] of Object.entries(errors)) {
    const field = document.querySelector(`[name="${name}"]`)?.closest(".field");
    if (!field) continue;
    field.classList.add("invalid");
    const note = document.createElement("small");
    note.className = "field-error";
    note.textContent = message;
    field.append(note);
  }
}

function refreshConnection(saved) {
  const tag = $("#conn-tag");
  tag.textContent = saved.ready ? "Ready" : "Not connected";
  tag.className = "tag " + (saved.ready ? "ok" : "warn");
  const keyBox = $("#api_key");
  keyBox.value = "";
  $("#key-help").textContent = saved.has_key ? "A key is saved. Type a new one to replace it."
    : "The key stays on your computer and is never shown again after saving.";
  keyBox.placeholder = saved.has_key ? `${saved.api_key_hint} (saved - leave empty to keep)` : "Paste your API key here";
  const status = document.querySelector(".status");
  status.classList.toggle("ok", saved.ready);
  status.querySelector("span").textContent = saved.ready ? saved.effective_model : "API key needed";
}

// ---- save
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const {ok, data} = await api("/api/settings", {method: "POST", body: formValues()});
  showErrors(ok ? {} : data.errors);
  const out = $("#save-result");
  if (ok) {
    out.textContent = "";
    refreshConnection(data);
    toast("Settings saved");
    if (!data.has_key && $("#provider").value !== "custom") toast("Saved. Now add your API key to start chatting.");
  } else {
    out.textContent = data.error || "Could not save.";
    out.className = "result bad";
  }
});

// ---- test the connection with what is currently typed (even if not saved yet)
$("#test").addEventListener("click", async () => {
  const out = $("#test-result");
  const button = $("#test");
  out.className = "result";
  out.textContent = "Testing...";
  button.disabled = true;
  const {data} = await api("/api/settings/test", {method: "POST", body: formValues()});
  button.disabled = false;
  showErrors(data.errors);
  if (data.ok) {
    out.textContent = `Connected. ${data.model} answered: "${data.reply}"`;
    out.className = "result ok";
  } else {
    out.textContent = data.error || "Test failed.";
    out.className = "result bad";
  }
});

// ---- remove key / reset / wipe
const removeKey = $("#remove-key");
if (removeKey) removeKey.addEventListener("click", async () => {
  const {ok, data} = await api("/api/settings", {method: "POST", body: {clear_api_key: true}});
  if (ok) { refreshConnection(data); removeKey.remove(); $("#key-help").textContent = "The key was removed."; toast("API key removed"); }
});

confirmClick($("#reset"), async () => {
  const {ok} = await api("/api/settings/reset", {method: "POST"});
  if (ok) location.reload();
});
confirmClick($("#wipe"), async () => {
  const {ok, data} = await api("/api/conversations", {method: "DELETE"});
  if (ok) toast(`Deleted ${data.deleted} chat${data.deleted === 1 ? "" : "s"}`);
});
