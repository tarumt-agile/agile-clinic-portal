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

  const clearButton = document.getElementById(
    "clear-staff-filters"
  );

  const alertBox = document.getElementById(
    "staff-list-alert"
  );

  const roleLabels = {
    admin: "Administration",
    doctor: "Doctor",
    nurse: "Nurse (Receptionist)"
  };

  let staffAccounts = [];

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatRole(role) {
    return (
      roleLabels[role] ||
      role ||
      "Unknown"
    );
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

  function createStatusBadge(staff) {
    const statusClass = staff.is_active
      ? "staff-status-active"
      : "staff-status-inactive";

    const statusText = staff.is_active
      ? "Active"
      : "Inactive";

    return `
      <span
        class="staff-status-badge ${statusClass}"
      >
        ${statusText}
      </span>
    `;
  }

  function createViewButton(staff) {
    const staffId = encodeURIComponent(
      staff.staff_id
    );

    return `
      <a
        class="btn btn-sm btn-outline-primary
          staff-view-button"
        href="/staff/${staffId}"
      >
        View
      </a>
    `;
  }

  function updateSummary() {
    const activeCount = staffAccounts.filter(
      function (staff) {
        return staff.is_active;
      }
    ).length;

    document.getElementById(
      "total-staff"
    ).textContent = String(
      staffAccounts.length
    );

    document.getElementById(
      "active-staff"
    ).textContent = String(
      activeCount
    );

    document.getElementById(
      "inactive-staff"
    ).textContent = String(
      staffAccounts.length - activeCount
    );

    document.getElementById(
      "all-staff-count"
    ).textContent = String(
      staffAccounts.length
    );
  }

  function getFilteredStaff() {
    const searchTerm = searchInput.value
      .trim()
      .toLowerCase();

    const selectedRole = roleFilter.value;
    const selectedStatus =
      statusFilter.value;

    return staffAccounts.filter(
      function (staff) {
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
          searchableText.includes(
            searchTerm
          );

        const matchesRole =
          !selectedRole ||
          staff.role === selectedRole;

        const staffStatus = staff.is_active
          ? "active"
          : "inactive";

        const matchesStatus =
          !selectedStatus ||
          staffStatus === selectedStatus;

        return (
          matchesSearch &&
          matchesRole &&
          matchesStatus
        );
      }
    );
  }

  function renderStaff() {
    const filteredStaff =
      getFilteredStaff();

    document.getElementById(
      "visible-staff-count"
    ).textContent = String(
      filteredStaff.length
    );

    if (filteredStaff.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td
            colspan="5"
            class="staff-table-message"
          >
            No staff accounts match the
            selected filters.
          </td>
        </tr>
      `;

      mobileList.innerHTML = `
        <p class="staff-table-message">
          No staff accounts match the
          selected filters.
        </p>
      `;

      return;
    }

    tableBody.innerHTML = filteredStaff
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
                class="staff-role-badge
                  ${getRoleClass(staff.role)}"
              >
                ${escapeHtml(
                  formatRole(staff.role)
                )}
              </span>
            </td>

            <td>
              ${createStatusBadge(staff)}
            </td>

            <td class="staff-action-cell">
              ${createViewButton(staff)}
            </td>
          </tr>
        `;
      })
      .join("");

    mobileList.innerHTML = filteredStaff
      .map(function (staff) {
        return `
          <article class="staff-mobile-card">
            <div
              class="staff-mobile-card-header"
            >
              <div>
                <h3>
                  ${escapeHtml(staff.full_name)}
                </h3>

                <p
                  class="staff-mobile-card-id"
                >
                  ${escapeHtml(staff.staff_id)}
                </p>
              </div>

              ${createStatusBadge(staff)}
            </div>

            <p
              class="staff-mobile-card-email"
            >
              ${escapeHtml(staff.email)}
            </p>

            <div
              class="staff-mobile-card-badges"
            >
              <span
                class="staff-role-badge
                  ${getRoleClass(staff.role)}"
              >
                ${escapeHtml(
                  formatRole(staff.role)
                )}
              </span>
            </div>

            <div
              class="staff-mobile-card-action"
            >
              ${createViewButton(staff)}
            </div>
          </article>
        `;
      })
      .join("");
  }

  async function loadStaff() {
    alertBox.classList.add("d-none");

    try {
      const response = await fetch(
        "/api/staff"
      );

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
      renderStaff();

    } catch (error) {
      staffAccounts = [];

      updateSummary();
      renderStaff();

      alertBox.textContent =
        error.message ||
        "Unable to connect to the server.";

      alertBox.classList.remove("d-none");
    }
  }

  searchInput.addEventListener(
    "input",
    renderStaff
  );

  roleFilter.addEventListener(
    "change",
    renderStaff
  );

  statusFilter.addEventListener(
    "change",
    renderStaff
  );

  clearButton.addEventListener(
    "click",
    function () {
      searchInput.value = "";
      roleFilter.value = "";
      statusFilter.value = "";

      renderStaff();
      searchInput.focus();
    }
  );

  loadStaff();
})();