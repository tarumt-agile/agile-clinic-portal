(function () {
  "use strict";

  const tableBody = document.getElementById("appointments-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("appointments-heading");
  const alertBox = document.getElementById("appointments-alert");

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

  async function loadAppointments() {
    hideAlert();
    tableBody.innerHTML =
      '<tr><td colspan="6" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch("/api/appointments/mine");
      const body = await response.json();

      if (response.status === 404) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "No patient account found.");
        return;
      }

      if (!response.ok) throw new Error("Request failed");

      heading.textContent = `${body.patient_name}'s Appointments`;
      renderTable(body.appointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load your appointments. Please try again.");
    }
  }

  function renderTable(appointments) {
    if (appointments.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="6" class="text-center text-muted py-4">You have no upcoming appointments.</td></tr>';
      return;
    }

    tableBody.innerHTML = appointments
      .map((a) => {
        const badgeClass = STATUS_BADGE[a.status] || "text-bg-light";
        const action =
          a.status === "scheduled"
            ? `<button type="button" class="btn btn-sm btn-outline-danger cancel-btn" data-reference="${escapeHtml(a.reference_number)}" data-doctor-name="${escapeHtml(a.doctor_name)}">Cancel</button>`
            : "-";
        return `
      <tr>
        <td>${escapeHtml(a.appointment_date)}</td>
        <td>${escapeHtml(a.start_time.slice(0, 5))} - ${escapeHtml(a.end_time.slice(0, 5))}</td>
        <td>${escapeHtml(a.doctor_name)}</td>
        <td>${escapeHtml(a.reason)}</td>
        <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(a.status)}</span></td>
        <td>${action}</td>
      </tr>`;
      })
      .join("");

    tableBody.querySelectorAll(".cancel-btn").forEach((btn) => {
      btn.addEventListener("click", () => openCancelModal(btn.dataset.reference, btn.dataset.doctorName));
    });
  }

  function openCancelModal(referenceNumber, doctorName) {
    pendingReferenceNumber = referenceNumber;
    cancelTargetPatient.textContent = doctorName;
    cancelReasonInput.value = "";
    cancelForm.classList.remove("was-validated");
    cancelReasonInput.classList.remove("is-invalid");
    cancelAlert.classList.add("d-none");
    if (cancelModal) {
      cancelModal.show();
    } else {
      const reason = window.prompt(`Cancel your appointment with ${doctorName}? Enter a reason:`);
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
        loadAppointments();
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

  cancelForm.addEventListener("submit", handleCancelSubmit);
  loadAppointments();
})();
