// Shared helpers for the patient registration and edit forms (identical field sets).
window.PatientForm = (function () {
  "use strict";

  function showAlert(alertBox, message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert(alertBox) {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  function clearFieldErrors(form) {
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
  }

  function setFieldError(form, fieldName, message) {
    const field = form.elements.namedItem(fieldName);
    if (!field) return;
    field.classList.add("is-invalid");
    const feedback = field.parentElement.querySelector(".invalid-feedback");
    if (feedback && message) feedback.textContent = message;
  }

  // Maps a FastAPI/Pydantic 422 error "loc" (e.g. ["body", "full_name"]) to a form field name.
  function fieldNameFromLoc(loc) {
    if (!Array.isArray(loc)) return null;
    return loc[loc.length - 1];
  }

  // Applies a FastAPI 422 error body's field errors onto the form.
  // Returns true if at least one field-level error was applied.
  function applyValidationErrors(form, errorBody) {
    let hadFieldError = false;
    for (const err of errorBody.detail || []) {
      const fieldName = fieldNameFromLoc(err.loc);
      if (fieldName && form.elements.namedItem(fieldName)) {
        setFieldError(form, fieldName, err.msg);
        hadFieldError = true;
      }
    }
    return hadFieldError;
  }

  // Reads the patient form fields (registration and edit forms share the same field set).
  function collectPayload(form) {
    const data = new FormData(form);
    const payload = {
      full_name: data.get("full_name")?.trim(),
      date_of_birth: data.get("date_of_birth"),
      gender: data.get("gender"),
      phone_number: data.get("phone_number")?.trim(),
      ic_or_passport: data.get("ic_or_passport")?.trim(),
    };
    const email = data.get("email")?.trim();
    const address = data.get("address")?.trim();
    if (email) payload.email = email;
    if (address) payload.address = address;
    return payload;
  }

  return {
    showAlert,
    hideAlert,
    clearFieldErrors,
    setFieldError,
    applyValidationErrors,
    collectPayload,
  };
})();
