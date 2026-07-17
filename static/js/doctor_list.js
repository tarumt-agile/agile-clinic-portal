(function () {
  "use strict";

  const tableBody = document.getElementById("doctor-table-body");
  const mobileCardList = document.getElementById("doctor-card-list");
  const alertBox = document.getElementById("doctor-list-alert");

  const searchInput = document.getElementById("doctor-search");
  const specialtyFilter = document.getElementById("specialty-filter");
  const statusFilter = document.getElementById("status-filter");
  const clearFiltersButton = document.getElementById(
    "clear-filters-button"
  );

  const totalDoctorsElement = document.getElementById("total-doctors");
  const activeDoctorsElement = document.getElementById("active-doctors");
  const inactiveDoctorsElement = document.getElementById(
    "inactive-doctors"
  );
  const resultCountElement = document.getElementById(
    "doctor-result-count"
  );

  if (!tableBody || !mobileCardList) {
    return;
  }

  let doctors = [];

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
  }

  function normaliseValue(value) {
    return String(value ?? "")
      .trim()
      .toLowerCase();
  }

  function showAlert(message) {
    if (!alertBox) {
      return;
    }

    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    if (!alertBox) {
      return;
    }

    alertBox.textContent = "";
    alertBox.classList.add("d-none");
  }

  function createDoctorDetailUrl(doctorId) {
    return (
      "/staff/admin/viewDoctor/" +
      encodeURIComponent(doctorId)
    );
  }

  function createStatusBadge(status) {
    const normalisedStatus = normaliseValue(status);
    const badgeClass =
      normalisedStatus === "active"
        ? "doctor-status-active"
        : "doctor-status-inactive";

    const label =
      normalisedStatus === "active" ? "Active" : "Inactive";

    return `
      <span class="doctor-status-badge ${badgeClass}">
        ${label}
      </span>
    `;
  }

  function formatDoctorCount(count) {
    return `${count} ${count === 1 ? "doctor" : "doctors"}`;
  }

  function updateSummary() {
    const total = doctors.length;

    const active = doctors.filter(
      (doctor) => normaliseValue(doctor.status) === "active"
    ).length;

    const inactive = total - active;

    totalDoctorsElement.textContent = String(total);
    activeDoctorsElement.textContent = String(active);
    inactiveDoctorsElement.textContent = String(inactive);
  }

  function populateSpecialtyFilter() {
    const specialties = [
      ...new Set(
        doctors
          .map((doctor) => doctor.specialty)
          .filter(Boolean)
      )
    ].sort((first, second) =>
      first.localeCompare(second)
    );

    specialtyFilter.innerHTML =
      '<option value="">All specialties</option>';

    specialties.forEach((specialty) => {
      const option = document.createElement("option");
      option.value = specialty;
      option.textContent = specialty;
      specialtyFilter.appendChild(option);
    });
  }

  function getFilteredDoctors() {
    const query = normaliseValue(searchInput.value);
    const selectedSpecialty = specialtyFilter.value;
    const selectedStatus = normaliseValue(statusFilter.value);

    return doctors.filter((doctor) => {
      const searchableValues = [
        doctor.doctor_id,
        doctor.staff_id,
        doctor.full_name,
        doctor.email,
        doctor.license_number,
        doctor.specialty,
        doctor.department,
        doctor.status
      ]
        .map(normaliseValue)
        .join(" ");

      const matchesSearch =
        query === "" || searchableValues.includes(query);

      const matchesSpecialty =
        selectedSpecialty === "" ||
        doctor.specialty === selectedSpecialty;

      const matchesStatus =
        selectedStatus === "" ||
        normaliseValue(doctor.status) === selectedStatus;

      return (
        matchesSearch &&
        matchesSpecialty &&
        matchesStatus
      );
    });
  }

  function renderDesktopTable(items) {
    if (items.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="doctor-table-message">
            No doctors match the selected filters.
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = items
      .map((doctor) => {
        const detailUrl = createDoctorDetailUrl(
          doctor.doctor_id
        );

        return `
          <tr
            class="doctor-record-row"
            tabindex="0"
            role="link"
            data-detail-url="${escapeHtml(detailUrl)}"
            aria-label="View ${escapeHtml(doctor.full_name)}"
          >
            <td>
              <span class="doctor-id">
                ${escapeHtml(doctor.doctor_id)}
              </span>
            </td>

            <td>
              <div class="doctor-cell-name">
                <strong>${escapeHtml(doctor.full_name)}</strong>
                <span>${escapeHtml(doctor.email)}</span>
              </div>
            </td>

            <td>${escapeHtml(doctor.license_number)}</td>

            <td>${escapeHtml(doctor.specialty)}</td>

            <td>${createStatusBadge(doctor.status)}</td>

            <td class="doctor-action-cell">
              <a
                href="${escapeHtml(detailUrl)}"
                class="btn btn-sm btn-outline-primary doctor-view-button"
              >
                View
              </a>
            </td>
          </tr>
        `;
      })
      .join("");

    tableBody
      .querySelectorAll(".doctor-record-row")
      .forEach((row) => {
        row.addEventListener("click", (event) => {
          if (event.target.closest("a, button")) {
            return;
          }

          window.location.href = row.dataset.detailUrl;
        });

        row.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            window.location.href = row.dataset.detailUrl;
          }
        });
      });
  }

  function renderMobileCards(items) {
    if (items.length === 0) {
      mobileCardList.innerHTML = `
        <p class="text-center text-muted my-3">
          No doctors match the selected filters.
        </p>
      `;
      return;
    }

    mobileCardList.innerHTML = items
      .map((doctor) => {
        const detailUrl = createDoctorDetailUrl(
          doctor.doctor_id
        );

        return `
          <a
            href="${escapeHtml(detailUrl)}"
            class="doctor-mobile-card"
          >
            <div class="doctor-mobile-card-header">
              <div>
                <h3>${escapeHtml(doctor.full_name)}</h3>
                <p class="doctor-mobile-card-id">
                  ${escapeHtml(doctor.doctor_id)}
                </p>
              </div>

              ${createStatusBadge(doctor.status)}
            </div>

            <dl class="doctor-mobile-card-details">
              <div>
                <dt>Staff ID</dt>
                <dd>${escapeHtml(doctor.staff_id)}</dd>
              </div>

              <div>
                <dt>Licence</dt>
                <dd>${escapeHtml(doctor.license_number)}</dd>
              </div>

              <div>
                <dt>Specialty</dt>
                <dd>${escapeHtml(doctor.specialty)}</dd>
              </div>

              <div>
                <dt>Email</dt>
                <dd>${escapeHtml(doctor.email)}</dd>
              </div>
            </dl>
          </a>
        `;
      })
      .join("");
  }

  function renderDoctors() {
    const filteredDoctors = getFilteredDoctors();

    renderDesktopTable(filteredDoctors);
    renderMobileCards(filteredDoctors);

    resultCountElement.textContent =
      filteredDoctors.length === doctors.length
        ? `Showing ${formatDoctorCount(doctors.length)}`
        : `Showing ${filteredDoctors.length} of ${formatDoctorCount(
            doctors.length
          )}`;
  }

  async function loadDoctors() {
    hideAlert();

    tableBody.innerHTML = `
      <tr>
        <td colspan="6" class="doctor-table-message">
          Loading doctors...
        </td>
      </tr>
    `;

    mobileCardList.innerHTML = `
      <p class="text-center text-muted my-3">
        Loading doctors...
      </p>
    `;

    try {
      const response = await fetch("/api/staff/doctors");

      if (!response.ok) {
        throw new Error(
          `Doctor request failed with status ${response.status}`
        );
      }

      const responseData = await response.json();

      if (!Array.isArray(responseData)) {
        throw new Error("Doctor response is not a list.");
      }

      doctors = responseData;

      updateSummary();
      populateSpecialtyFilter();
      renderDoctors();
    } catch (error) {
      console.error("Unable to load doctors:", error);

      tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="doctor-table-message">
            Doctor records could not be loaded.
          </td>
        </tr>
      `;

      mobileCardList.innerHTML = "";

      showAlert(
        "Unable to load the doctor list. Please refresh the page and try again."
      );
    }
  }

  searchInput.addEventListener("input", renderDoctors);
  specialtyFilter.addEventListener("change", renderDoctors);
  statusFilter.addEventListener("change", renderDoctors);

  clearFiltersButton.addEventListener("click", function () {
    searchInput.value = "";
    specialtyFilter.value = "";
    statusFilter.value = "";

    renderDoctors();
    searchInput.focus();
  });

  loadDoctors();
})();