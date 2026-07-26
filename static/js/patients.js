(function () {
  "use strict";

  const form = document.getElementById("patient-form");
  if (!form) return;

  const { showAlert, hideAlert, clearFieldErrors, applyValidationErrors, collectPayload } =
    window.PatientForm;

  const dobInput = document.getElementById("date_of_birth");
  const genderInput = document.getElementById("gender");
  const icInput = document.getElementById("ic_or_passport");

  const IC_PATTERN = /^\d{6}-\d{2}-\d{4}$/;

  function checkIcConsistency() {
    const ic = icInput.value.trim();
    icInput.classList.remove("is-invalid");
    if (!ic || !IC_PATTERN.test(ic)) return; // not IC-shaped (empty or a passport) - nothing to check

    const dob = dobInput.value; // "YYYY-MM-DD"
    if (dob) {
      const dobDigits = dob.slice(2, 4) + dob.slice(5, 7) + dob.slice(8, 10);
      if (ic.slice(0, 6) !== dobDigits) {
        icInput.classList.add("is-invalid");
        document.getElementById("ic-or-passport-error").textContent =
          "This IC number does not match the date of birth.";
        return;
      }
    }

    const gender = genderInput.value;
    const lastDigit = Number(ic.slice(-1));
    if (gender === "male" && lastDigit % 2 === 0) {
      icInput.classList.add("is-invalid");
      document.getElementById("ic-or-passport-error").textContent =
        "This IC number's last digit does not match a male patient.";
    } else if (gender === "female" && lastDigit % 2 !== 0) {
      icInput.classList.add("is-invalid");
      document.getElementById("ic-or-passport-error").textContent =
        "This IC number's last digit does not match a female patient.";
    }
  }

  window.PatientForm.autoDash(icInput, [6, 2, 4]);
  icInput.addEventListener("input", checkIcConsistency);
  dobInput.addEventListener("change", checkIcConsistency);
  genderInput.addEventListener("change", checkIcConsistency);

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
