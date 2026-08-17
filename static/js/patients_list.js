(function () {
  "use strict";

  const tableBody = document.getElementById("patients-table-body");
  if (!tableBody) return;

  const searchInput = document.getElementById("search-input");
  const registeredFromInput = document.getElementById("registered-from-input");
  const registeredToInput = document.getElementById("registered-to-input");
  const alertBox = document.getElementById("list-alert");
  const paginationEl = document.getElementById("pagination-controls");
  const pageSize = 10;

  let state = { query: "", registeredFrom: "", registeredTo: "", page: 1 };
  let debounceTimer = null;

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  async function loadPatients() {
    alertBox.classList.add("d-none");
    tableBody.innerHTML =
      '<tr><td colspan="6" class="text-center text-muted py-4">Loading...</td></tr>';

    const params = new URLSearchParams({
      page: String(state.page),
      page_size: String(pageSize),
    });
    if (state.query) params.set("q", state.query);
    if (state.registeredFrom) params.set("registered_from", state.registeredFrom);
    if (state.registeredTo) params.set("registered_to", state.registeredTo);

    try {
      const response = await fetch(`/api/patients?${params.toString()}`);
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      renderTable(data.items);
      renderPagination(data.page, data.total_pages, data.total);
    } catch (err) {
      tableBody.innerHTML = "";
      alertBox.textContent = "Unable to load patients. Please try again.";
      alertBox.classList.remove("d-none");
    }
  }

  function renderTable(items) {
    if (items.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="6" class="text-center text-muted py-4">No patients found.</td></tr>';
      return;
    }

    tableBody.innerHTML = items
      .map(
        (p) => `
      <tr class="patient-row" role="button" data-patient-id="${escapeHtml(p.patient_id)}">
        <td class="fw-semibold">${escapeHtml(p.patient_id)}</td>
        <td>${escapeHtml(p.full_name)}</td>
        <td class="text-capitalize">${escapeHtml(p.gender)}</td>
        <td>${escapeHtml(p.phone_number)}</td>
        <td>${escapeHtml(p.date_of_birth)}</td>
        <td>${escapeHtml((p.created_at || "").slice(0, 10))}</td>
      </tr>`
      )
      .join("");

    tableBody.querySelectorAll(".patient-row").forEach((row) => {
      row.addEventListener("click", () => {
        const returnPath = window.location.pathname + window.location.search;
        window.location.href =
          `/patients/${encodeURIComponent(row.dataset.patientId)}?` +
          `from=${encodeURIComponent(returnPath)}` +
          `&label=${encodeURIComponent("Back to Patient List")}`;
      });
    });
  }

  // How many page numbers to show on each side of the current page. With a
  // large patient count, rendering one button per page (the old behavior)
  // makes the pagination bar grow wider than the page - this windows it down
  // to a fixed handful of buttons plus jump-to-first/last controls, e.g.
  // [<<] [<] [27] [28] [29] [30] [31] [...] [>] [>>].
  const PAGE_WINDOW = 2;

  function renderPagination(page, totalPages, total) {
    if (totalPages <= 1) {
      paginationEl.innerHTML = "";
      return;
    }

    const items = [];
    items.push(pageItem("«", 1, page === 1, false, "First page"));
    items.push(pageItem("‹", page - 1, page === 1, false, "Previous page"));

    const windowStart = Math.max(1, page - PAGE_WINDOW);
    const windowEnd = Math.min(totalPages, page + PAGE_WINDOW);

    if (windowStart > 1) {
      items.push(pageItem("1", 1, false, page === 1));
      if (windowStart > 2) items.push(ellipsisItem());
    }

    for (let p = windowStart; p <= windowEnd; p += 1) {
      items.push(pageItem(String(p), p, false, p === page));
    }

    if (windowEnd < totalPages) {
      if (windowEnd < totalPages - 1) items.push(ellipsisItem());
      items.push(pageItem(String(totalPages), totalPages, false, page === totalPages));
    }

    items.push(pageItem("›", page + 1, page === totalPages, false, "Next page"));
    items.push(pageItem("»", totalPages, page === totalPages, false, "Last page"));
    paginationEl.innerHTML = items.join("");

    paginationEl.querySelectorAll("[data-page]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.preventDefault();
        const targetPage = Number(el.dataset.page);
        if (!Number.isNaN(targetPage) && targetPage >= 1 && targetPage <= totalPages) {
          state.page = targetPage;
          loadPatients();
        }
      });
    });
  }

  function pageItem(label, page, disabled, active, ariaLabel) {
    const classes = ["page-item"];
    if (disabled) classes.push("disabled");
    if (active) classes.push("active");
    const aria = ariaLabel ? ` aria-label="${escapeHtml(ariaLabel)}"` : "";
    return `<li class="${classes.join(" ")}"><a class="page-link" href="#" data-page="${page}"${aria}>${label}</a></li>`;
  }

  function ellipsisItem() {
    return '<li class="page-item disabled"><span class="page-link">…</span></li>';
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.query = searchInput.value.trim();
      state.page = 1;
      loadPatients();
    }, 300);
  });

  registeredFromInput.addEventListener("input", () => {
    state.registeredFrom = registeredFromInput.value;
    state.page = 1;
    loadPatients();
  });

  registeredToInput.addEventListener("input", () => {
    state.registeredTo = registeredToInput.value;
    state.page = 1;
    loadPatients();
  });

  loadPatients();
})();
