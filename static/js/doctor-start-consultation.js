(function () {
  "use strict";

  const tableBody = document.getElementById("consultation-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("consultation-heading");
  const alertBox = document.getElementById("consultation-alert");
  const currentDatetimeEl = document.getElementById("current-datetime");
  let queueAppointments = null;
  let lastRenderedMinute = null;

  const STATUS_BADGE = {
    scheduled: "text-bg-primary",
    completed: "text-bg-success",
    cancelled: "text-bg-secondary",
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

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  // "HH:MM:SS" (or "HH:MM") -> minutes since midnight, for comparing against
  // the current local time without pulling in a date library.
  function timeToMinutes(value) {
    const [hours, minutes] = value.split(":").map(Number);
    return hours * 60 + minutes;
  }

  function nowMinutes() {
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes();
  }

  async function loadQueue() {
    hideAlert();
    tableBody.innerHTML =
      '<tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch("/api/consultations/today-queue");
      const body = await response.json();

      if (response.status === 404) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "No doctor account found.");
        return;
      }

      if (!response.ok) throw new Error("Request failed");

      heading.textContent = `${body.doctor_name}'s Appointments`;
      queueAppointments = body.appointments;
      renderTable(queueAppointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load the schedule. Please try again.");
    }
  }

  // Turns the full day's queue into what the doctor should actually see and
  // act on: a not-yet-started appointment whose slot has already gone by is
  // dropped (it's no longer something to "start"), while anything with a
  // consultation already on it - started or finished - always stays visible
  // so the doctor can get back into it or confirm it's done.
  function visibleEntries(appointments) {
    const now = nowMinutes();
    return appointments.filter((a) => {
      if (a.consultation_status) return true;
      return timeToMinutes(a.end_time) > now;
    });
  }

  // An appointment is locked only while an earlier slot is still current/future,
  // or while an earlier consultation is genuinely in progress. A missed earlier
  // appointment must stop blocking the rest of the day's queue once its slot ends.
  function isLocked(appointments, index) {
    const now = nowMinutes();
    for (let i = 0; i < index; i++) {
      const earlier = appointments[i];
      if (earlier.appointment_status !== "scheduled") continue;
      if (earlier.consultation_status === "in_progress") return true;
      if (!earlier.consultation_status && timeToMinutes(earlier.end_time) > now) return true;
    }
    return false;
  }

  function viewPatientButton(patientId) {
    const from = encodeURIComponent(window.location.pathname + window.location.search);
    const label = encodeURIComponent("Back to Start Consultation");
    return `<a href="/patients/${encodeURIComponent(patientId)}?from=${from}&label=${label}" target="_self" class="btn btn-sm btn-outline-secondary">View Patient Details</a>`;
  }

  function consultationAction(appointment, locked) {
    if (appointment.consultation_status === "completed") {
      return '<span class="text-muted">Ended</span>';
    }

    if (appointment.consultation_status === "in_progress") {
      // Back to the note form, not the read-only detail page - a draft
      // consultation may still have no notes/diagnoses written yet, which is
      // only editable from the form.
      return `<a href="/consultations/new?patient_id=${encodeURIComponent(appointment.patient_id)}&appointment_reference=${encodeURIComponent(appointment.reference_number)}" class="btn btn-sm btn-warning">Continue Consultation</a>`;
    }

    if (appointment.appointment_status !== "scheduled") {
      return "";
    }

    if (timeToMinutes(appointment.start_time) > nowMinutes()) {
      const start = escapeHtml(appointment.start_time.slice(0, 5));
      return `<button type="button" class="btn btn-sm btn-primary" disabled title="Available at ${start}">Start Consultation</button>`;
    }

    if (locked) {
      return '<button type="button" class="btn btn-sm btn-primary" disabled title="Finish the earlier appointment first">Start Consultation</button>';
    }

    return `<a href="/consultations/new?patient_id=${encodeURIComponent(appointment.patient_id)}&appointment_reference=${encodeURIComponent(appointment.reference_number)}" class="btn btn-sm btn-primary">Start Consultation</a>`;
  }

  function actionCell(appointment, locked) {
    return `<div class="d-flex gap-1">${viewPatientButton(appointment.patient_id)}${consultationAction(appointment, locked)}</div>`;
  }

  function renderTable(appointments) {
    const entries = visibleEntries(appointments);

    if (entries.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="5" class="text-center text-muted py-4">No appointments left for today.</td></tr>';
      return;
    }

    tableBody.innerHTML = entries
      .map((a) => {
        const badgeClass = STATUS_BADGE[a.appointment_status] || "text-bg-light";
        const locked = isLocked(appointments, appointments.indexOf(a));
        return `
      <tr>
        <td>${escapeHtml(a.start_time.slice(0, 5))} - ${escapeHtml(a.end_time.slice(0, 5))}</td>
        <td>${escapeHtml(a.patient_name)} (${escapeHtml(a.patient_id)})</td>
        <td>${escapeHtml(a.reason)}</td>
        <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(a.appointment_status)}</span></td>
        <td>${actionCell(a, locked)}</td>
      </tr>`;
      })
      .join("");
  }

  // Shows the browser's own idea of "now" next to the heading, so it's obvious
  // whether the future-timeslot filtering and locking above are working off the
  // date/time you expect - useful given past-vs-future here depends entirely on
  // this local clock, not the server's.
  function updateCurrentDatetime() {
    const now = new Date();
    currentDatetimeEl.textContent = `Now: ${now.toLocaleString(undefined, {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })}`;

    // A doctor may leave this page open while waiting for a slot. Re-render at
    // the next minute boundary so the action unlocks without requiring refresh.
    const currentMinute = now.getHours() * 60 + now.getMinutes();
    if (
      lastRenderedMinute !== null &&
      currentMinute !== lastRenderedMinute &&
      queueAppointments !== null
    ) {
      renderTable(queueAppointments);
    }
    lastRenderedMinute = currentMinute;
  }

  updateCurrentDatetime();
  setInterval(updateCurrentDatetime, 1000);

  loadQueue();
})();
