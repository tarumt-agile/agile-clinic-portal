(function () {
  "use strict";

  const tableBody = document.getElementById(
    "staff-table-body"
  );

  if (!tableBody) {
    return;
  }

  const mobileList = document.getElementById(
    "staff-mobile-list"
  );

  const searchInput = document.getElementById(
    "staff-search"
  );

  const roleFilter = document.getElementById(
    "role-filter"
  );

  const statusFilter = document.getElementById(
    "staff-status-filter"
  );

  const clearFiltersButton = document.getElementById(
    "clear-staff-filters"
  );

  const listAlert = document.getElementById(
    "staff-list-alert"
  );

  const totalStaffElement = document.getElementById(
    "total-staff"
  );

  const activeStaffElement = document.getElementById(
    "active-staff"
  );

  const inactiveStaffElement = document.getElementById(
    "inactive-staff"
  );

  const visibleStaffCount = document.getElementById(
    "visible-staff-count"
  );

  const allStaffCount = document.getElementById(
    "all-staff-count"
  );

  const statusModalElement = document.getElementById(
    "staff-status-modal"
  );

  const statusModalMessage = document.getElementById(
    "staff-status-modal-message"
  );

  const statusModalAlert = document.getElementById(
    "staff-status-modal-alert"
  );

  const confirmStatusButton = document.getElementById(
    "confirm-staff-status-button"
  );

  let staffAccounts = [];
  let selectedStaff = null;
  let selectedNewStatus = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatRole(role) {
    const roleLabels = {
      admin: "Administration",
      doctor: "Doctor",
      nurse: "Nurse (Receptionist)"
    };

    return roleLabels[role] || role || "Unknown";
  }

  function getRoleClass(role) {
    const validRoles = [
      "admin",
      "doctor",
      "nurse"
    ];

    if (!validRoles.includes(role)) {
      return "";
    }

    return "staff-role-" + role;
  }

  function showListAlert(message) {
    listAlert.textContent = message;
    listAlert.classList.remove("d-none");
  }

  function hideListAlert() {
    listAlert.textContent = "";
    listAlert.classList.add("d-none");
  }

  function updateSummary() {
    const activeCount = staffAccounts.filter(
      function (staff) {
        return staff.is_active;
      }
    ).length;

    totalStaffElement.textContent =
      String(staffAccounts.length);

    activeStaffElement.textContent =
      String(activeCount);

    inactiveStaffElement.textContent =
      String(staffAccounts.length - activeCount);

    allStaffCount.textContent =
      String(staffAccounts.length);
  }

  function getFilteredStaff() {
    const searchTerm = searchInput.value
      .trim()
      .toLowerCase();

    const selectedRole = roleFilter.value;
    const selectedStatus = statusFilter.value;

    return staffAccounts.filter(function (staff) {
      const searchableText = [
        staff.staff_id,
        staff.full_name,
        staff.email,
        staff.role
      ]
        .join(" ")
        .toLowerCase();

      const matchesSearch =
        !searchTerm ||
        searchableText.includes(searchTerm);

      const matchesRole =
        !selectedRole ||
        staff.role === selectedRole;

      const statusValue =
        staff.is_active ? "active" : "inactive";

      const matchesStatus =
        !selectedStatus ||
        statusValue === selectedStatus;

      return (
        matchesSearch &&
        matchesRole &&
        matchesStatus
      );
    });
  }

  function createStatusBadge(staff) {
    if (staff.is_active) {
      return `
        <span class="staff-status-badge staff-status-active">
          Active
        </span>
      `;
    }

    return `
      <span class="staff-status-badge staff-status-inactive">
        Inactive
      </span>
    `;
  }

  function createPasswordBadge(staff) {
    if (staff.must_change_password) {
      return `
        <span class="staff-password-badge staff-password-temporary">
          Temporary Password
        </span>
      `;
    }

    return `
      <span class="staff-password-badge staff-password-updated">
        Password Updated
      </span>
    `;
  }

  function createActionButton(staff) {
    const nextAction =
      staff.is_active ? "deactivate" : "activate";

    const buttonClass =
      staff.is_active
        ? "btn-outline-danger"
        : "btn-outline-success";

    const buttonText =
      staff.is_active
        ? "Deactivate"
        : "Activate";

    return `
      <button
        type="button"
        class="btn btn-sm ${buttonClass} staff-status-button"
        data-staff-id="${escapeHtml(staff.staff_id)}"
        data-action="${nextAction}"
      >
        ${buttonText}
      </button>
    `;
  }

  function renderDesktopTable(staffList) {
    if (staffList.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="staff-table-message">
            No staff accounts match the selected filters.
          </td>
        </tr>
      `;

      return;
    }

    tableBody.innerHTML = staffList
      .map(function (staff) {
        return `
          <tr>
            <td>
              <span class="staff-id">
                ${escapeHtml(staff.staff_id)}
              </span>
            </td>

            <td>
              <div class="staff-member-cell">
                <strong>
                  ${escapeHtml(staff.full_name)}
                </strong>

                <span>
                  ${escapeHtml(staff.email)}
                </span>
              </div>
            </td>

            <td>
              <span
                class="staff-role-badge ${getRoleClass(staff.role)}"
              >
                ${escapeHtml(formatRole(staff.role))}
              </span>
            </td>

            <td>
              ${createStatusBadge(staff)}
            </td>

            <td>
              ${createPasswordBadge(staff)}
            </td>

            <td class="staff-action-cell">
              ${createActionButton(staff)}
            </td>
          </tr>
        `;
      })
      .join("");
  }

  function renderMobileCards(staffList) {
    if (staffList.length === 0) {
      mobileList.innerHTML = `
        <p class="staff-table-message">
          No staff accounts match the selected filters.
        </p>
      `;

      return;
    }

    mobileList.innerHTML = staffList
      .map(function (staff) {
        return `
          <article class="staff-mobile-card">
            <div class="staff-mobile-card-header">
              <div>
                <h3>
                  ${escapeHtml(staff.full_name)}
                </h3>

                <p class="staff-mobile-card-id">
                  ${escapeHtml(staff.staff_id)}
                </p>
              </div>

              ${createStatusBadge(staff)}
            </div>

            <p class="staff-mobile-card-email">
              ${escapeHtml(staff.email)}
            </p>

            <div class="staff-mobile-card-badges">
              <span
                class="staff-role-badge ${getRoleClass(staff.role)}"
              >
                ${escapeHtml(formatRole(staff.role))}
              </span>

              ${createPasswordBadge(staff)}
            </div>

            <div class="staff-mobile-card-action">
              ${createActionButton(staff)}
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderStaffList() {
    const filteredStaff = getFilteredStaff();

    visibleStaffCount.textContent =
      String(filteredStaff.length);

    renderDesktopTable(filteredStaff);
    renderMobileCards(filteredStaff);
  }

  function findStaffById(staffId) {
    return staffAccounts.find(function (staff) {
      return staff.staff_id === staffId;
    });
  }

  function openStatusModal(staff, action) {
    selectedStaff = staff;
    selectedNewStatus = action === "activate";

    statusModalAlert.textContent = "";
    statusModalAlert.classList.add("d-none");

    if (selectedNewStatus) {
      statusModalMessage.textContent =
        `Activate the account for ${staff.full_name}? ` +
        "The staff member will be allowed to log in again.";

      confirmStatusButton.textContent =
        "Activate Account";

      confirmStatusButton.className =
        "btn btn-success";
    } else {
      statusModalMessage.textContent =
        `Deactivate the account for ${staff.full_name}? ` +
        "The staff member will no longer be allowed to log in.";

      confirmStatusButton.textContent =
        "Deactivate Account";

      confirmStatusButton.className =
        "btn btn-danger";
    }

    if (
      window.bootstrap &&
      window.bootstrap.Modal
    ) {
      const modal =
        window.bootstrap.Modal.getOrCreateInstance(
          statusModalElement
        );

      modal.show();
    }
  }

  async function updateStaffStatus() {
    if (!selectedStaff) {
      return;
    }

    const originalButtonText =
      confirmStatusButton.textContent;

    confirmStatusButton.disabled = true;
    confirmStatusButton.textContent = "Saving...";

    statusModalAlert.textContent = "";
    statusModalAlert.classList.add("d-none");

    try {
      const response = await fetch(
        `/api/staff/${encodeURIComponent(
          selectedStaff.staff_id
        )}/status`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            is_active: selectedNewStatus
          })
        }
      );

      let payload = null;

      try {
        payload = await response.json();
      } catch (error) {
        payload = null;
      }

      if (!response.ok) {
        const message =
          payload && typeof payload.detail === "string"
            ? payload.detail
            : "Staff status could not be updated.";

        throw new Error(message);
      }

      const staffIndex = staffAccounts.findIndex(
        function (staff) {
          return staff.staff_id === payload.staff_id;
        }
      );

      if (staffIndex !== -1) {
        staffAccounts[staffIndex] = payload;
      }

      updateSummary();
      renderStaffList();

      const modal =
        window.bootstrap.Modal.getOrCreateInstance(
          statusModalElement
        );

      modal.hide();

    } catch (error) {
      statusModalAlert.textContent =
        error.message ||
        "Unable to connect to the server.";

      statusModalAlert.classList.remove("d-none");
    } finally {
      confirmStatusButton.disabled = false;
      confirmStatusButton.textContent =
        originalButtonText;
    }
  }

  async function loadStaff() {
    hideListAlert();

    try {
      const response = await fetch("/api/staff");

      if (!response.ok) {
        throw new Error(
          "Staff accounts could not be loaded."
        );
      }

      const payload = await response.json();

      staffAccounts = Array.isArray(payload)
        ? payload
        : [];

      updateSummary();
      renderStaffList();

    } catch (error) {
      staffAccounts = [];

      updateSummary();
      renderStaffList();

      showListAlert(
        error.message ||
        "Unable to connect to the server."
      );
    }
  }

  function handleStatusButtonClick(event) {
    const button = event.target.closest(
      ".staff-status-button"
    );

    if (!button) {
      return;
    }

    const staff = findStaffById(
      button.dataset.staffId
    );

    if (!staff) {
      return;
    }

    openStatusModal(
      staff,
      button.dataset.action
    );
  }

  searchInput.addEventListener(
    "input",
    renderStaffList
  );

  roleFilter.addEventListener(
    "change",
    renderStaffList
  );

  statusFilter.addEventListener(
    "change",
    renderStaffList
  );

  clearFiltersButton.addEventListener(
    "click",
    function () {
      searchInput.value = "";
      roleFilter.value = "";
      statusFilter.value = "";

      renderStaffList();
      searchInput.focus();
    }
  );

  tableBody.addEventListener(
    "click",
    handleStatusButtonClick
  );

  mobileList.addEventListener(
    "click",
    handleStatusButtonClick
  );

  confirmStatusButton.addEventListener(
    "click",
    updateStaffStatus
  );

  loadStaff();
})();