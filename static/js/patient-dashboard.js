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
  const infoLink = document.getElementById("my-info-link");

  // No real prescription/pharmacy module exists yet - this is placeholder data
  // only, per the dashboard's explicit "Sample data" labelling.
  const SAMPLE_PRESCRIPTIONS = [
    { name: "Amoxicillin 500mg", instructions: "1 capsule, 3x daily", refillsLeft: 2 },
    { name: "Paracetamol 500mg", instructions: "2 tablets as needed for pain", refillsLeft: 1 },
    { name: "Loratadine 10mg", instructions: "1 tablet daily", refillsLeft: 0 },
  ];

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

  function renderPrescriptions() {
    prescriptionsList.innerHTML = SAMPLE_PRESCRIPTIONS.map((rx) => {
      const refillBadge =
        rx.refillsLeft > 0
          ? `<span class="badge text-bg-light">${rx.refillsLeft} refill${rx.refillsLeft === 1 ? "" : "s"} left</span>`
          : `<span class="badge text-bg-light text-danger">No refills left</span>`;
      return `
        <div class="list-group-item">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <div class="fw-semibold">${escapeHtml(rx.name)}</div>
              <div class="small text-muted">${escapeHtml(rx.instructions)}</div>
            </div>
            ${refillBadge}
          </div>
        </div>`;
    }).join("");
    statPrescriptions.textContent = String(SAMPLE_PRESCRIPTIONS.length);
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
    infoLink.href = `/patients/${encodeURIComponent(patient.patient_id)}`;
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
    renderPrescriptions();

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
      const response = await fetch(`/api/records?patient_id=${encodeURIComponent(patient.patient_id)}`);
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
