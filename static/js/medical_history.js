(function () {
  "use strict";

  const detailRoot = document.getElementById("patient-detail-root");
  if (!detailRoot) return;

  const patientId = detailRoot.dataset.patientId;
  const historyTabBtn = document.getElementById("history-tab-btn");
  const searchInput = document.getElementById("history-search");
  const newRecordLink = document.getElementById("new-record-link");
  const historyAlert = document.getElementById("history-alert");
  const historyEmpty = document.getElementById("history-empty");
  const historyList = document.getElementById("history-list");

  let searchDebounceTimer = null;
  let hasLoadedOnce = false;

  newRecordLink.href = `/records/new?patient_id=${encodeURIComponent(patientId)}`;

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function highlight(text, query) {
    const escaped = escapeHtml(text);
    if (!query) return escaped;
    const re = new RegExp(escapeRegExp(query), "gi");
    return escaped.replace(re, (match) => `<mark>${match}</mark>`);
  }

  function renderHistory(items, query) {
    if (items.length === 0) {
      historyEmpty.classList.remove("d-none");
      historyList.innerHTML = "";
      return;
    }
    historyEmpty.classList.add("d-none");

    historyList.innerHTML = items
      .map((item) => {
        const diagnosisChips = item.diagnoses
          .map(
            (d) =>
              `<span class="badge bg-danger-subtle text-danger-emphasis me-1 mb-1">` +
              `${highlight(d.icd10_code, query)} - ${highlight(d.description, query)}</span>`
          )
          .join("");
        const notesPreview =
          item.notes.length > 160 ? `${item.notes.slice(0, 160)}…` : item.notes;

        return (
          `<a href="/records/${encodeURIComponent(item.record_id)}" ` +
          `class="card mb-2 text-decoration-none text-body">` +
          `<div class="card-body">` +
          `<div class="d-flex justify-content-between">` +
          `<span class="fw-semibold">${new Date(item.visit_date).toLocaleString()}</span>` +
          `<span class="text-muted">${escapeHtml(item.doctor_name)}</span>` +
          `</div>` +
          `<div class="mt-2">${diagnosisChips}</div>` +
          `<p class="text-muted small mb-0 mt-2">${highlight(notesPreview, query)}</p>` +
          `</div></a>`
        );
      })
      .join("");
  }

  async function loadHistory() {
    const query = searchInput.value.trim();
    historyAlert.classList.add("d-none");
    try {
      const params = new URLSearchParams({ patient_id: patientId });
      if (query) params.set("q", query);
      const response = await fetch(`/api/records?${params.toString()}`);
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      renderHistory(data.items, query);
    } catch (err) {
      historyAlert.textContent = "Unable to load medical history. Please try again.";
      historyAlert.classList.remove("d-none");
    }
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(loadHistory, 250);
  });

  historyTabBtn.addEventListener("shown.bs.tab", () => {
    if (!hasLoadedOnce) {
      hasLoadedOnce = true;
      loadHistory();
    }
  });
})();
