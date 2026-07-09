(function () {
  "use strict";

  const form = document.getElementById("staff-form");
  if (!form) return;

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");
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

  function applyValidationErrors(errorBody) {
    let hadFieldError = false;
    for (const err of errorBody.detail || []) {
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
      full_name: data.get("full_name")?.trim(),
      email: data.get("email")?.trim(),
      role: data.get("role"),
    };
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
      const response = await fetch("/api/staff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload()),
      });

      if (response.status === 201) {
        const staff = await response.json();
        showConfirmation(staff);
        form.reset();
        form.classList.remove("was-validated");
        return;
      }

      if (response.status === 422) {
        const body = await response.json();
        if (!applyValidationErrors(body)) {
          showAlert("Please check the form for errors.");
        }
        return;
      }

      if (response.status === 409) {
        const body = await response.json();
        showAlert(body.detail || "A staff account with this email already exists.");
        return;
      }

      showAlert("Something went wrong while creating the account. Please try again.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function showConfirmation(staff) {
    document.getElementById("confirm-staff-id").textContent = staff.staff_id;
    document.getElementById("confirm-full-name").textContent = staff.full_name;
    document.getElementById("confirm-role").textContent = staff.role;
    if (confirmationModal) {
      confirmationModal.show();
    } else {
      window.alert(`Staff account created: ${staff.staff_id}`);
    }
  }

  form.addEventListener("submit", handleSubmit);
})();
