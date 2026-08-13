(function () {
  "use strict";

  const form = document.getElementById("audit-log-filter");
  const fromInput = document.getElementById("audit-from");
  const toInput = document.getElementById("audit-to");
  const body = document.getElementById("audit-log-body");
  const alertBox = document.getElementById("audit-log-alert");
  if (!form) return;

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function render(items) {
    if (items.length === 0) {
      body.innerHTML = '<tr><td colspan="4">No events in this range.</td></tr>';
      return;
    }
    body.innerHTML = items
      .map(
        (item) =>
          `<tr><td>${new Date(item.created_at).toLocaleString()}</td>` +
          `<td>${escapeHtml(item.event)}</td>` +
          `<td>${escapeHtml(item.email || item.user_id || "-")}</td>` +
          `<td>${escapeHtml(item.ip_address || "-")}</td></tr>`
      )
      .join("");
  }

  async function load() {
    alertBox.classList.add("d-none");
    try {
      const params = new URLSearchParams({ from: fromInput.value, to: toInput.value });
      const response = await fetch(`/api/auth/audit-log?${params.toString()}`);
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      render(data.items);
    } catch (err) {
      alertBox.textContent = "Unable to load the audit log.";
      alertBox.classList.remove("d-none");
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load();
  });

  load();
})();
