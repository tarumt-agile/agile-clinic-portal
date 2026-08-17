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

  // Applies a FastAPI 422 error body's field errors onto the form. Returns
  // { hadFieldError, message }: hadFieldError is true if at least one error
  // mapped to a specific input (which now shows its own inline message).
  // message is a fallback string built from any errors that couldn't be
  // pinned to a field - e.g. cross-field checks like "IC number does not
  // match the date of birth", where Pydantic's model_validator errors carry
  // no field name in their "loc" - for display in the page's alert banner.
  function applyValidationErrors(form, errorBody) {
    let hadFieldError = false;
    const fallbackMessages = [];
    for (const err of errorBody.detail || []) {
      const fieldName = fieldNameFromLoc(err.loc);
      if (fieldName && form.elements.namedItem(fieldName)) {
        setFieldError(form, fieldName, err.msg);
        hadFieldError = true;
      } else if (err.msg) {
        fallbackMessages.push(err.msg.replace(/^Value error,\s*/, ""));
      }
    }
    return { hadFieldError, message: fallbackMessages.join(" ") };
  }

  // Reformats digits-only input into dash-separated groups as the user types,
  // e.g. groupSizes [6, 2, 4] turns "900520101234" into "900520-10-1234". Skips
  // reformatting if the field has any letters in it - this field also accepts
  // passport numbers, which aren't digits-only and shouldn't be touched.
  function autoDash(input, groupSizes) {
    input.addEventListener("input", () => {
      if (/[a-zA-Z]/.test(input.value)) {
        input.value = input.value.replace(/-/g, "");
        return;
      }
      const digits = input.value.replace(/\D/g, "");
      const groups = [];
      let start = 0;
      for (const size of groupSizes) {
        if (start >= digits.length) break;
        groups.push(digits.slice(start, start + size));
        start += size;
      }
      input.value = groups.join("-");
    });
  }

  // Local date, not UTC - toISOString() converts to UTC and can be a day off
  // from the browser's local "today" near midnight, which would make the DOB
  // max/min boundary wrong.
  function toLocalISODate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  // Sets native min/max bounds on a date-of-birth input, matching the
  // server-side "not in the future, not more than 100 years ago" rule.
  function setDobRange(input) {
    const today = new Date();
    input.max = toLocalISODate(today);
    const earliest = new Date(today);
    earliest.setFullYear(earliest.getFullYear() - 100);
    input.min = toLocalISODate(earliest);
  }

  // Reads the patient form fields (registration and edit forms share the same field set).
  function collectPayload(form) {
    const data = new FormData(form);
    const payload = {
      full_name: data.get("full_name")?.trim(),
      date_of_birth: data.get("date_of_birth"),
      gender: data.get("gender"),
      phone_number: data.get("phone_number")?.trim(),
    };
    const email = data.get("email")?.trim();
    const address = data.get("address")?.trim();
    const icOrPassport = data.get("ic_or_passport")?.trim();
    if (email) payload.email = email;
    if (address) payload.address = address;
    if (icOrPassport) payload.ic_or_passport = icOrPassport;
    return payload;
  }

  // Fills form fields from a PatientOut JSON object (used to enter edit mode).
  function fillForm(form, patient) {
    form.elements.namedItem("full_name").value = patient.full_name || "";
    form.elements.namedItem("date_of_birth").value = patient.date_of_birth || "";
    form.elements.namedItem("gender").value = patient.gender || "";
    form.elements.namedItem("phone_number").value = patient.phone_number || "";
    form.elements.namedItem("email").value = patient.email || "";
    form.elements.namedItem("address").value = patient.address || "";
  }

  return {
    showAlert,
    hideAlert,
    clearFieldErrors,
    setFieldError,
    applyValidationErrors,
    collectPayload,
    fillForm,
    autoDash,
    setDobRange,
  };
})();
