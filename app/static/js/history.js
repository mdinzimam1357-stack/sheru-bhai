/* history.js - rename and delete chats from the History page. */

document.querySelectorAll(".hist").forEach((row) => {
  const id = row.dataset.id;

  // delete (two clicks)
  confirmClick(row.querySelector(".act-delete"), async () => {
    const {ok, data} = await api(`/api/conversations/${id}`, {method: "DELETE"});
    if (!ok) return toast(data.error || "Could not delete.", true);
    row.remove();
    toast("Chat deleted");
    if (!document.querySelector(".hist")) location.reload();
  });

  // rename (inline edit)
  row.querySelector(".act-rename").addEventListener("click", () => {
    const titleEl = row.querySelector(".hist-title");
    const old = titleEl.textContent;
    const field = document.createElement("input");
    field.className = "rename-input";
    field.value = old;
    field.maxLength = 80;
    titleEl.replaceWith(field);
    field.focus();
    field.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      done = true;
      let title = old;
      if (save && field.value.trim() && field.value.trim() !== old) {
        const {ok, data} = await api(`/api/conversations/${id}`, {method: "PATCH", body: {title: field.value}});
        if (ok) { title = data.title; toast("Renamed"); } else toast(data.error || "Could not rename.", true);
      }
      titleEl.textContent = title;
      field.replaceWith(titleEl);
    };
    field.addEventListener("keydown", (e) => {
      if (e.key === "Enter") finish(true);
      if (e.key === "Escape") finish(false);
    });
    field.addEventListener("blur", () => finish(true));
    field.addEventListener("click", (e) => e.preventDefault());
  });
});

const wipe = $("#delete-all");
if (wipe) confirmClick(wipe, async () => {
  const {ok} = await api("/api/conversations", {method: "DELETE"});
  if (ok) location.href = "/history";
});
