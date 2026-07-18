(function () {
  "use strict";

  const form = document.getElementById("patient-form");
  if (!form) return;

  const { showAlert, hideAlert, clearFieldErrors, applyValidationErrors, collectPayload } =
    window.PatientForm;

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");
  const confirmationModalEl = document.getElementById("confirmation-modal");
  const confirmationModal = window.bootstrap ? new bootstrap.Modal(confirmationModalEl) : null;

  async function handleSubmit(event) {
    event.preventDefault();
    hideAlert(alertBox);
    clearFieldErrors(form);

    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/patients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload(form)),
      });

      if (response.status === 201) {
        const patient = await response.json();
        showConfirmation(patient);
        form.reset();
        form.classList.remove("was-validated");
        return;
      }

      if (response.status === 422) {
        const body = await response.json();
        if (!applyValidationErrors(form, body)) {
          showAlert(alertBox, "Please check the form for errors.");
        }
        return;
      }

      if (response.status === 409) {
        const body = await response.json();
        showAlert(alertBox, body.detail || "This patient is already registered.");
        return;
      }

      showAlert(alertBox, "Something went wrong while registering the patient. Please try again.");
    } catch (err) {
      showAlert(alertBox, "Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function showConfirmation(patient) {
    document.getElementById("confirm-patient-id").textContent = patient.patient_id;
    document.getElementById("confirm-full-name").textContent = patient.full_name;
    document.getElementById("confirm-ic").textContent = patient.ic_or_passport;
    document.getElementById("confirm-phone").textContent = patient.phone_number;
    if (confirmationModal) {
      confirmationModal.show();
    } else {
      window.alert(`Patient registered: ${patient.patient_id}`);
    }
  }

  form.addEventListener("submit", handleSubmit);
})();
