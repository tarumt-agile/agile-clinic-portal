(function () {
  "use strict";

  const greeting = document.getElementById("dashboard-greeting");
  if (!greeting) return;

  const subtitle = document.getElementById("dashboard-subtitle");
  const alertBox = document.getElementById("dashboard-alert");
  const statUpcoming = document.getElementById("stat-upcoming");
  const statVisits = document.getElementById("stat-visits");
  const statPrescriptions = document.getElementById("stat-prescriptions");
  const upcomingList = document.getElementById("upcoming-appointments-list");
  const visitsList = document.getElementById("recent-visits-list");
  const prescriptionsList = document.getElementById("prescriptions-list");
  const infoBody = document.getElementById("my-info-body");

  const PRESCRIPTION_STATUS_BADGES = {
    active: '<span class="badge text-bg-success">Active</span>',
    completed: '<span class="badge text-bg-secondary">Completed</span>',
    cancelled: '<span class="badge text-bg-light text-danger">Cancelled</span>',
  };

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function formatDate(isoDate) {
    const d = new Date(isoDate);
    if (Number.isNaN(d.getTime())) return isoDate;
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function renderPrescriptions(prescriptions) {
    const activeCount = prescriptions.filter((rx) => rx.status === "active").length;
    statPrescriptions.textContent = String(activeCount);

    if (prescriptions.length === 0) {
      prescriptionsList.innerHTML =
        '<div class="list-group-item text-muted">No prescriptions on record yet.</div>';
      return;
    }

    prescriptionsList.innerHTML = prescriptions
      .map((rx) => {
        const badge = PRESCRIPTION_STATUS_BADGES[rx.status] || "";
        const instructions = [rx.dosage, rx.frequency, rx.duration]
          .filter(Boolean)
          .join(" - ");
        return `
        <div class="list-group-item">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <div class="fw-semibold">${escapeHtml(rx.medication)}</div>
              <div class="small text-muted">${escapeHtml(instructions)}</div>
              <div class="small text-muted">Prescribed by ${escapeHtml(rx.prescribing_doctor_name)} on ${escapeHtml(formatDate(rx.issued_at))}</div>
            </div>
            ${badge}
          </div>
        </div>`;
      })
      .join("");
  }

  function renderUpcomingAppointments(appointments) {
    const upcoming = appointments.filter((a) => a.status === "scheduled").slice(0, 3);
    statUpcoming.textContent = String(upcoming.length);

    if (upcoming.length === 0) {
      upcomingList.innerHTML =
        '<div class="list-group-item text-muted">No upcoming appointments. <a href="/appointments/book">Book one now</a>.</div>';
      return;
    }

    upcomingList.innerHTML = upcoming
      .map(
        (a) => `
        <div class="list-group-item">
          <div class="d-flex justify-content-between">
            <span class="fw-semibold">${escapeHtml(a.doctor_name)}</span>
            <span class="text-muted small">${escapeHtml(formatDate(a.appointment_date))}, ${escapeHtml(a.start_time.slice(0, 5))}</span>
          </div>
          <div class="small text-muted">${escapeHtml(a.reason)}</div>
        </div>`
      )
      .join("");
  }

  function renderRecentVisits(items) {
    statVisits.textContent = String(items.length);
    const recent = items.slice(0, 3);

    if (recent.length === 0) {
      visitsList.innerHTML =
        '<div class="list-group-item text-muted">No past visits on record yet.</div>';
      return;
    }

    visitsList.innerHTML = recent
      .map((note) => {
        const diagnoses = note.diagnoses
          .map((d) => `<span class="badge text-bg-light me-1">${escapeHtml(d.description)}</span>`)
          .join("");
        return `
        <div class="list-group-item">
          <div class="d-flex justify-content-between">
            <span class="fw-semibold">${escapeHtml(note.doctor_name)}</span>
            <span class="text-muted small">${escapeHtml(formatDate(note.visit_date))}</span>
          </div>
          <div class="small mt-1">${diagnoses}</div>
        </div>`;
      })
      .join("");
  }

  function renderInfo(patient) {
    const returnPath = window.location.pathname + window.location.search;
    infoLink.href =
      `/patients/${encodeURIComponent(patient.patient_id)}?` +
      `from=${encodeURIComponent(returnPath)}` +
      `&label=${encodeURIComponent("Back to Dashboard")}`;
    infoBody.innerHTML = `
      <dl class="row mb-0 small">
        <dt class="col-5">Patient ID</dt>
        <dd class="col-7">${escapeHtml(patient.patient_id)}</dd>
        <dt class="col-5">Date of birth</dt>
        <dd class="col-7">${escapeHtml(patient.date_of_birth)}</dd>
        <dt class="col-5">Phone</dt>
        <dd class="col-7">${escapeHtml(patient.phone_number)}</dd>
        <dt class="col-5">Email</dt>
        <dd class="col-7">${escapeHtml(patient.email || "-")}</dd>
      </dl>`;
  }

  async function load() {
    let patient;
    try {
      const response = await fetch("/api/patients/me");
      if (response.status === 404) {
        showAlert("No patient account found.");
        upcomingList.innerHTML = "";
        visitsList.innerHTML = "";
        infoBody.innerHTML = "";
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      patient = await response.json();
    } catch (err) {
      showAlert("Unable to load your patient record. Please try again.");
      return;
    }

    greeting.textContent = `Welcome back, ${patient.full_name}`;
    subtitle.textContent = `Patient ID: ${patient.patient_id}`;
    renderInfo(patient);

    try {
      const response = await fetch("/api/appointments/mine");
      if (response.ok) {
        const body = await response.json();
        renderUpcomingAppointments(body.appointments);
      } else {
        upcomingList.innerHTML = '<div class="list-group-item text-muted">Unable to load appointments.</div>';
      }
    } catch (err) {
      upcomingList.innerHTML = '<div class="list-group-item text-muted">Unable to load appointments.</div>';
    }

    try {
      const response = await fetch("/api/prescriptions/mine");
      if (response.ok) {
        const body = await response.json();
        renderPrescriptions(body.items);
      } else {
        prescriptionsList.innerHTML =
          '<div class="list-group-item text-muted">Unable to load prescriptions.</div>';
        statPrescriptions.textContent = "0";
      }
    } catch (err) {
      prescriptionsList.innerHTML =
        '<div class="list-group-item text-muted">Unable to load prescriptions.</div>';
      statPrescriptions.textContent = "0";
    }

    try {
      const response = await fetch(`/api/consultations?patient_id=${encodeURIComponent(patient.patient_id)}`);
      if (response.ok) {
        const body = await response.json();
        renderRecentVisits(body.items);
      } else {
        visitsList.innerHTML = '<div class="list-group-item text-muted">Unable to load visit history.</div>';
        statVisits.textContent = "0";
      }
    } catch (err) {
      visitsList.innerHTML = '<div class="list-group-item text-muted">Unable to load visit history.</div>';
      statVisits.textContent = "0";
    }
  }

  load();
})();
