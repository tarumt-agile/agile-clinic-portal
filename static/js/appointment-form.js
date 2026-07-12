(function () {
  "use strict";

  const form = document.getElementById("appointment-form");
  if (!form) return;

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");
  const dateInput = document.getElementById("appointment_date");
  const patientIdInput = document.getElementById("patient_id");
  const patientFeedback = document.getElementById("patient-lookup-feedback");
  const doctorSelect = document.getElementById("doctor_id");
  const confirmationModalEl = document.getElementById("confirmation-modal");
  const confirmationModal = window.bootstrap ? new bootstrap.Modal(confirmationModalEl) : null;

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  function clearFieldErrors() {
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
  }

  function fieldNameFromLoc(loc) {
    if (!Array.isArray(loc)) return null;
    return loc[loc.length - 1];
  }

  // Pydantic 422s have a list `detail` of field errors; service-layer 422s (invalid
  // slot) have a plain string `detail`. Only the former can be mapped onto a field.
  function applyValidationErrors(errorBody) {
    if (!Array.isArray(errorBody.detail)) return false;
    let hadFieldError = false;
    for (const err of errorBody.detail) {
      const fieldName = fieldNameFromLoc(err.loc);
      const field = fieldName && form.elements.namedItem(fieldName);
      if (field) {
        field.classList.add("is-invalid");
        const feedback = field.parentElement.querySelector(".invalid-feedback");
        if (feedback && err.msg) feedback.textContent = err.msg;
        hadFieldError = true;
      }
    }
    return hadFieldError;
  }

  function collectPayload() {
    const data = new FormData(form);
    return {
      patient_id: data.get("patient_id")?.trim(),
      doctor_id: data.get("doctor_id"),
      appointment_date: data.get("appointment_date"),
      start_time: data.get("start_time"),
      reason: data.get("reason")?.trim(),
    };
  }

  async function loadDoctors() {
    doctorSelect.innerHTML = '<option value="" selected disabled>Loading doctors...</option>';
    try {
      const response = await fetch("/api/staff");
      if (!response.ok) throw new Error("Request failed");
      const staff = await response.json();
      const doctors = staff.filter((s) => s.role === "doctor" && s.is_active);

      if (doctors.length === 0) {
        doctorSelect.innerHTML = '<option value="" selected disabled>No doctors available</option>';
        return;
      }

      doctorSelect.innerHTML =
        '<option value="" selected disabled>Choose...</option>' +
        doctors
          .map((d) => `<option value="${d.staff_id}">${d.full_name}</option>`)
          .join("");
    } catch (err) {
      doctorSelect.innerHTML = '<option value="" selected disabled>Unable to load doctors</option>';
    }
  }

  async function lookupPatient() {
    const patientId = patientIdInput.value.trim();
    patientFeedback.textContent = "";
    patientFeedback.classList.remove("text-danger", "text-success");
    if (!patientId) return;

    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(patientId)}`);
      if (response.status === 404) {
        patientFeedback.textContent = "No patient found with this ID.";
        patientFeedback.classList.add("text-danger");
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      const patient = await response.json();
      patientFeedback.textContent = `✓ ${patient.full_name}`;
      patientFeedback.classList.add("text-success");
    } catch (err) {
      patientFeedback.textContent = "Unable to verify patient ID right now.";
      patientFeedback.classList.add("text-danger");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    hideAlert();
    clearFieldErrors();

    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/appointments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload()),
      });

      if (response.status === 201) {
        const appointment = await response.json();
        showConfirmation(appointment);
        form.reset();
        form.classList.remove("was-validated");
        patientFeedback.textContent = "";
        return;
      }

      const body = await response.json().catch(() => ({}));

      if (response.status === 404 || response.status === 409) {
        showAlert(body.detail || "This appointment could not be booked.");
        return;
      }

      if (response.status === 422) {
        if (!applyValidationErrors(body)) {
          showAlert(typeof body.detail === "string" ? body.detail : "Please check the form for errors.");
        }
        return;
      }

      showAlert("Something went wrong while booking the appointment. Please try again.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function showConfirmation(appointment) {
    document.getElementById("confirm-reference").textContent = appointment.reference_number;
    document.getElementById("confirm-patient").textContent =
      `${appointment.patient_name} (${appointment.patient_id})`;
    document.getElementById("confirm-doctor").textContent =
      `${appointment.doctor_name} (${appointment.doctor_id})`;
    document.getElementById("confirm-datetime").textContent =
      `${appointment.appointment_date} ${appointment.start_time.slice(0, 5)}`;
    if (confirmationModal) {
      confirmationModal.show();
    } else {
      window.alert(`Appointment booked: ${appointment.reference_number}`);
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

  dateInput.min = todayLocalISODate();

  patientIdInput.addEventListener("blur", lookupPatient);
  form.addEventListener("submit", handleSubmit);
  loadDoctors();
})();
