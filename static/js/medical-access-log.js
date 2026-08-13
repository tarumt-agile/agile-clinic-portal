(function () {
  "use strict";

  const form = document.getElementById("access-log-filter");
  const patientInput = document.getElementById("filter-patient-id");
  const doctorInput = document.getElementById("filter-doctor-id");
  const body = document.getElementById("access-log-body");
  const alertBox = document.getElementById("access-log-alert");
  if (!form) return;

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function render(items) {
    if (items.length === 0) {
      body.innerHTML = '<tr><td colspan="5">No matching access log entries.</td></tr>';
      return;
    }
    body.innerHTML = items
      .map(
        (item) =>
          `<tr><td>${new Date(item.created_at).toLocaleString()}</td>` +
          `<td>${escapeHtml(item.record_id)}</td>` +
          `<td>${escapeHtml(item.patient_id)}</td>` +
          `<td>${escapeHtml(item.accessed_by_name)}</td>` +
          `<td>${escapeHtml(item.action)}</td></tr>`
      )
      .join("");
  }

  async function load() {
    alertBox.classList.add("d-none");
    try {
      const params = new URLSearchParams();
      if (patientInput.value.trim()) params.set("patient_id", patientInput.value.trim());
      if (doctorInput.value.trim()) params.set("doctor_id", doctorInput.value.trim());
      const response = await fetch(`/api/consultations/access-log?${params.toString()}`);
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      render(data.items);
    } catch (err) {
      alertBox.textContent = "Unable to load the access log.";
      alertBox.classList.remove("d-none");
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load();
  });

  load();
})();
