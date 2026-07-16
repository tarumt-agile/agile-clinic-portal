(function () {
  "use strict";

  const root = document.getElementById("doctor-detail-root");

  if (!root) {
    return;
  }

  const doctorId = root.dataset.doctorId;

  const loadingElement = document.getElementById(
    "doctor-detail-loading"
  );
  const contentElement = document.getElementById(
    "doctor-detail-content"
  );
  const alertBox = document.getElementById(
    "doctor-detail-alert"
  );
  const notFoundBox = document.getElementById(
    "doctor-not-found"
  );

  function setText(elementId, value, fallback = "—") {
    const element = document.getElementById(elementId);

    if (!element) {
      return;
    }

    const cleanValue =
      value === null || value === undefined || value === ""
        ? fallback
        : String(value);

    element.textContent = cleanValue;
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideLoading() {
    loadingElement.classList.add("d-none");
  }

  function getInitials(fullName) {
    const words = String(fullName ?? "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);

    if (words.length === 0) {
      return "DR";
    }

    if (words.length === 1) {
      return words[0].slice(0, 2).toUpperCase();
    }

    return (
      words[0][0] +
      words[words.length - 1][0]
    ).toUpperCase();
  }

  function formatDate(dateValue) {
    if (!dateValue) {
      return "—";
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
      return String(dateValue);
    }

    return new Intl.DateTimeFormat("en-MY", {
      day: "2-digit",
      month: "long",
      year: "numeric"
    }).format(date);
  }

  function renderStatus(status) {
    const badge = document.getElementById(
      "doctor-status-badge"
    );

    const normalisedStatus = String(status ?? "")
      .trim()
      .toLowerCase();

    const isActive = normalisedStatus === "active";

    badge.textContent = isActive ? "Active" : "Inactive";

    badge.classList.remove(
      "doctor-status-active",
      "doctor-status-inactive"
    );

    badge.classList.add(
      isActive
        ? "doctor-status-active"
        : "doctor-status-inactive"
    );
  }

  function renderDoctor(doctor) {
    setText("doctor-heading-id", doctor.doctor_id);
    setText("doctor-full-name", doctor.full_name);
    setText("doctor-specialty-heading", doctor.specialty);
    setText("doctor-email-heading", doctor.email);

    setText(
      "doctor-avatar-text",
      getInitials(doctor.full_name)
    );

    renderStatus(doctor.status);

    setText("view-doctor-id", doctor.doctor_id);
    setText("view-license-number", doctor.license_number);
    setText("view-specialty", doctor.specialty);
    setText("view-department", doctor.department);
    setText("view-doctor-status", doctor.status);

    setText("view-staff-id", doctor.staff_id);
    setText("view-full-name", doctor.full_name);
    setText("linked-staff-id", doctor.staff_id);
    setText(
      "view-created-at",
      formatDate(doctor.created_at)
    );

    const emailLink = document.getElementById("view-email");

    emailLink.textContent = doctor.email || "—";

    if (doctor.email) {
      emailLink.href = `mailto:${doctor.email}`;
    } else {
      emailLink.removeAttribute("href");
    }

    hideLoading();
    contentElement.classList.remove("d-none");
  }

  function showNotFound() {
    hideLoading();
    notFoundBox.classList.remove("d-none");
  }

  async function loadDoctor() {
    if (!doctorId) {
        showNotFound();
        return;
    }

    try {
        const response = await fetch(
        `/api/staff/doctors/${encodeURIComponent(doctorId)}`
        );

        if (response.status === 404) {
        showNotFound();
        return;
        }

        if (!response.ok) {
        throw new Error(
            `Doctor request failed with status ${response.status}`
        );
        }

        const doctor = await response.json();

        renderDoctor(doctor);
    } catch (error) {
        console.error("Unable to load doctor details:", error);

        hideLoading();

        showAlert(
        "Unable to load this doctor profile. " +
        "Please return to the doctor list and try again."
        );
    }
    } 

  loadDoctor();
})();