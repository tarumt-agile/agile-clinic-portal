(function () {
  "use strict";

  const tableBody = document.getElementById("staff-table-body");
  if (!tableBody) return;

  const alertBox = document.getElementById("list-alert");
  const deactivateModalEl = document.getElementById("deactivate-modal");
  const deactivateModal = window.bootstrap ? new bootstrap.Modal(deactivateModalEl) : null;
  const deactivateTargetName = document.getElementById("deactivate-target-name");
  const confirmDeactivateBtn = document.getElementById("confirm-deactivate-btn");

  let pendingStaffId = null;

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  async function loadStaff() {
    alertBox.classList.add("d-none");
    tableBody.innerHTML =
      '<tr><td colspan="7" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch("/api/staff");
      if (!response.ok) throw new Error("Request failed");
      renderTable(await response.json());
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load staff. Please try again.");
    }
  }

  function formatSpecialty(specialty) {
    if (!specialty) return "-";
    return specialty
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  function renderTable(items) {
    if (items.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="7" class="text-center text-muted py-4">No staff accounts yet.</td></tr>';
      return;
    }

    tableBody.innerHTML = items
      .map((s) => {
        const statusBadge = s.is_active
          ? '<span class="badge bg-success">Active</span>'
          : '<span class="badge bg-secondary">Inactive</span>';
        const actionBtn = s.is_active
          ? `<button type="button" class="btn btn-sm btn-outline-danger deactivate-btn" data-staff-id="${escapeHtml(s.staff_id)}" data-staff-name="${escapeHtml(s.full_name)}">Deactivate</button>`
          : `<button type="button" class="btn btn-sm btn-outline-success activate-btn" data-staff-id="${escapeHtml(s.staff_id)}">Activate</button>`;

        return `
      <tr>
        <td class="fw-semibold">${escapeHtml(s.staff_id)}</td>
        <td>${escapeHtml(s.full_name)}</td>
        <td>${escapeHtml(s.email)}</td>
        <td class="text-capitalize">${escapeHtml(s.role)}</td>
        <td>${escapeHtml(formatSpecialty(s.specialty))}</td>
        <td>${statusBadge}</td>
        <td>${actionBtn}</td>
      </tr>`;
      })
      .join("");

    tableBody.querySelectorAll(".deactivate-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        pendingStaffId = btn.dataset.staffId;
        deactivateTargetName.textContent = btn.dataset.staffName;
        if (deactivateModal) {
          deactivateModal.show();
        } else if (window.confirm(`Deactivate ${btn.dataset.staffName}?`)) {
          setStaffStatus(pendingStaffId, false);
        }
      });
    });

    tableBody.querySelectorAll(".activate-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        setStaffStatus(btn.dataset.staffId, true);
      });
    });
  }

  async function setStaffStatus(staffId, isActive) {
    alertBox.classList.add("d-none");
    try {
      const response = await fetch(`/api/staff/${encodeURIComponent(staffId)}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive }),
      });
      if (!response.ok) throw new Error("Request failed");
      await loadStaff();
    } catch (err) {
      showAlert("Unable to update this staff account. Please try again.");
    }
  }

  confirmDeactivateBtn.addEventListener("click", () => {
    if (deactivateModal) deactivateModal.hide();
    if (pendingStaffId) setStaffStatus(pendingStaffId, false);
    pendingStaffId = null;
  });

  loadStaff();
})();
