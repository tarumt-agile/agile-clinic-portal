(function () {
  "use strict";

  const tableBody = document.getElementById("schedule-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("schedule-heading");
  const dateInput = document.getElementById("schedule-date");
  const alertBox = document.getElementById("schedule-alert");

  const cancelModalEl = document.getElementById("cancel-modal");
  const cancelModal = window.bootstrap ? new bootstrap.Modal(cancelModalEl) : null;
  const cancelForm = document.getElementById("cancel-form");
  const cancelReasonInput = document.getElementById("cancel-reason");
  const cancelTargetPatient = document.getElementById("cancel-target-patient");
  const cancelAlert = document.getElementById("cancel-alert");
  const confirmCancelBtn = document.getElementById("confirm-cancel-btn");

  const STATUS_BADGE = {
    scheduled: "text-bg-primary",
    cancelled: "text-bg-secondary",
  };

  let pendingReferenceNumber = null;

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

  async function loadSchedule(dateValue) {
    hideAlert();
    tableBody.innerHTML =
      '<tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch(`/api/appointments/schedule?date=${dateValue}`);
      const body = await response.json();

      if (response.status === 422) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "Please choose today or a future date.");
        return;
      }

      if (response.status === 404) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "No doctor account found.");
        return;
      }

      if (!response.ok) throw new Error("Request failed");

      heading.textContent = `${body.doctor_name}'s Schedule`;
      renderTable(body.appointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load the schedule. Please try again.");
    }
  }

  function renderTable(appointments) {
    if (appointments.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="5" class="text-center text-muted py-4">No appointments for this date.</td></tr>';
      return;
    }

    tableBody.innerHTML = appointments
      .map((a) => {
        const badgeClass = STATUS_BADGE[a.status] || "text-bg-light";
        const action =
          a.status === "scheduled"
            ? `<button type="button" class="btn btn-sm btn-outline-danger cancel-btn" data-reference="${escapeHtml(a.reference_number)}" data-patient-name="${escapeHtml(a.patient_name)}">Cancel</button>`
            : "-";
        return `
      <tr>
        <td>${escapeHtml(a.start_time.slice(0, 5))} - ${escapeHtml(a.end_time.slice(0, 5))}</td>
        <td>${escapeHtml(a.patient_name)} (${escapeHtml(a.patient_id)})</td>
        <td>${escapeHtml(a.reason)}</td>
        <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(a.status)}</span></td>
        <td>${action}</td>
      </tr>`;
      })
      .join("");

    tableBody.querySelectorAll(".cancel-btn").forEach((btn) => {
      btn.addEventListener("click", () => openCancelModal(btn.dataset.reference, btn.dataset.patientName));
    });
  }

  function openCancelModal(referenceNumber, patientName) {
    pendingReferenceNumber = referenceNumber;
    cancelTargetPatient.textContent = patientName;
    cancelReasonInput.value = "";
    cancelForm.classList.remove("was-validated");
    cancelReasonInput.classList.remove("is-invalid");
    cancelAlert.classList.add("d-none");
    if (cancelModal) {
      cancelModal.show();
    } else {
      const reason = window.prompt(`Cancel appointment with ${patientName}? Enter a reason:`);
      if (reason && reason.trim()) submitCancellation(referenceNumber, reason.trim());
    }
  }

  async function handleCancelSubmit(event) {
    event.preventDefault();
    cancelAlert.classList.add("d-none");

    if (!cancelForm.checkValidity()) {
      cancelForm.classList.add("was-validated");
      return;
    }

    await submitCancellation(pendingReferenceNumber, cancelReasonInput.value.trim());
  }

  async function submitCancellation(referenceNumber, reason) {
    confirmCancelBtn.disabled = true;
    try {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(referenceNumber)}/cancel`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cancellation_reason: reason }),
        }
      );

      if (response.ok) {
        if (cancelModal) cancelModal.hide();
        loadSchedule(dateInput.value);
        return;
      }

      const body = await response.json().catch(() => ({}));
      const message = typeof body.detail === "string" ? body.detail : "Unable to cancel this appointment.";
      if (cancelModal) {
        cancelAlert.textContent = message;
        cancelAlert.classList.remove("d-none");
      } else {
        window.alert(message);
      }
    } catch (err) {
      const message = "Unable to reach the server. Please check your connection and try again.";
      if (cancelModal) {
        cancelAlert.textContent = message;
        cancelAlert.classList.remove("d-none");
      } else {
        window.alert(message);
      }
    } finally {
      confirmCancelBtn.disabled = false;
    }
  }

  // Local date, not UTC - toISOString() converts to UTC and can be a day off from
  // the server's dt.date.today() (which uses local time), especially near midnight.
  function todayLocalISODate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  const today = todayLocalISODate();
  dateInput.min = today;
  dateInput.value = today;

  dateInput.addEventListener("change", () => loadSchedule(dateInput.value));
  cancelForm.addEventListener("submit", handleCancelSubmit);
  loadSchedule(today);
})();
