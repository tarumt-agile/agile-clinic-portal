(function () {
  "use strict";

  const tableBody = document.getElementById("patients-table-body");
  if (!tableBody) return;

  const searchInput = document.getElementById("search-input");
  const alertBox = document.getElementById("list-alert");
  const paginationEl = document.getElementById("pagination-controls");
  const pageSize = 10;

  let state = { query: "", page: 1 };
  let debounceTimer = null;

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  async function loadPatients() {
    alertBox.classList.add("d-none");
    tableBody.innerHTML =
      '<tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>';

    const params = new URLSearchParams({
      page: String(state.page),
      page_size: String(pageSize),
    });
    if (state.query) params.set("q", state.query);

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
        '<tr><td colspan="5" class="text-center text-muted py-4">No patients found.</td></tr>';
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
      </tr>`
      )
      .join("");

    tableBody.querySelectorAll(".patient-row").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `/patients/${row.dataset.patientId}`;
      });
    });
  }

  function renderPagination(page, totalPages, total) {
    if (totalPages <= 1) {
      paginationEl.innerHTML = "";
      return;
    }

    const items = [];
    items.push(pageItem("Previous", page - 1, page === 1));
    for (let p = 1; p <= totalPages; p += 1) {
      items.push(pageItem(String(p), p, false, p === page));
    }
    items.push(pageItem("Next", page + 1, page === totalPages));
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

  function pageItem(label, page, disabled, active) {
    const classes = ["page-item"];
    if (disabled) classes.push("disabled");
    if (active) classes.push("active");
    return `<li class="${classes.join(" ")}"><a class="page-link" href="#" data-page="${page}">${label}</a></li>`;
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.query = searchInput.value.trim();
      state.page = 1;
      loadPatients();
    }, 300);
  });

  loadPatients();
})();
