(function () {
  "use strict";

  const root = document.getElementById("record-form-root");
  if (!root) return;

  const patientId = root.dataset.patientId;
  const appointmentReference = new URLSearchParams(window.location.search).get(
    "appointment_reference"
  );
  const formHeading = document.getElementById("form-heading");
  const form = document.getElementById("record-form");
  const backLink = document.getElementById("back-link");
  const viewPatientLink = document.getElementById("view-patient-link");
  const alertBox = document.getElementById("form-alert");
  const diagnosesAlert = document.getElementById("diagnoses-alert");
  const submitBtn = document.getElementById("submit-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const patientNameLabel = document.getElementById("patient-name-label");
  const diagnosisRows = document.getElementById("diagnosis-rows");
  const rowTemplate = document.getElementById("diagnosis-row-template");
  const addDiagnosisBtn = document.getElementById("add-diagnosis-btn");
  const confirmationModalEl = document.getElementById("confirmation-modal");
  const confirmationModal = window.bootstrap ? new bootstrap.Modal(confirmationModalEl) : null;

  let searchDebounceTimer = null;
  // The record this page is writing to - set once /start resolves. Saving is
  // disabled until then, since there's nothing to save to yet.
  let recordId = null;

  function showAlert(box, message) {
    box.textContent = message;
    box.classList.remove("d-none");
  }

  function hideAlert(box) {
    box.classList.add("d-none");
    box.textContent = "";
  }

  function clearFieldErrors() {
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
  }

  function fieldNameFromLoc(loc) {
    if (!Array.isArray(loc)) return null;
    return loc[loc.length - 1];
  }

  // Maps Pydantic 422 errors for nested diagnoses (loc like ["body", "diagnoses", 0, "icd10_code"])
  // onto the matching row's input. Falls back to top-level fields (notes).
  function applyValidationErrors(errorBody) {
    if (!Array.isArray(errorBody.detail)) return false;
    let hadFieldError = false;
    const rows = diagnosisRows.querySelectorAll(".diagnosis-row");

    for (const err of errorBody.detail) {
      const loc = err.loc || [];
      if (loc[1] === "diagnoses" && typeof loc[2] === "number") {
        const row = rows[loc[2]];
        const fieldClass = loc[3] === "icd10_code" ? ".diagnosis-code" : ".diagnosis-description";
        const field = row && row.querySelector(fieldClass);
        if (field) {
          field.classList.add("is-invalid");
          const feedback = field.parentElement.querySelector(".invalid-feedback");
          if (feedback && err.msg) feedback.textContent = err.msg;
          hadFieldError = true;
        }
        continue;
      }
      const fieldName = fieldNameFromLoc(loc);
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

  async function loadPatientName() {
    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(patientId)}`);
      if (!response.ok) throw new Error("Request failed");
      const patient = await response.json();
      patientNameLabel.textContent = patient.full_name;
    } catch (err) {
      patientNameLabel.textContent = "Unknown patient";
    }
  }

  // --- Diagnosis rows -----------------------------------------------------

  function addDiagnosisRow(icd10Code, description) {
    const fragment = rowTemplate.content.cloneNode(true);
    const row = fragment.querySelector(".diagnosis-row");
    wireRow(row);
    if (icd10Code) row.querySelector(".diagnosis-code").value = icd10Code;
    if (description) row.querySelector(".diagnosis-description").value = description;
    if (icd10Code && description) {
      row.querySelector(".diagnosis-search").value = `${icd10Code} - ${description}`;
    }
    diagnosisRows.appendChild(row);
    hideAlert(diagnosesAlert);
  }

  function removeDiagnosisRow(row) {
    row.remove();
  }

  function wireRow(row) {
    const searchInput = row.querySelector(".diagnosis-search");
    const suggestions = row.querySelector(".diagnosis-suggestions");
    const codeInput = row.querySelector(".diagnosis-code");
    const descriptionInput = row.querySelector(".diagnosis-description");
    const removeBtn = row.querySelector(".remove-diagnosis-btn");

    searchInput.addEventListener("input", () => {
      clearTimeout(searchDebounceTimer);
      const term = searchInput.value.trim();
      if (!term) {
        suggestions.classList.add("d-none");
        suggestions.innerHTML = "";
        return;
      }
      searchDebounceTimer = setTimeout(() => runSearch(term, suggestions, (entry) => {
        codeInput.value = entry.code;
        descriptionInput.value = entry.description;
        codeInput.classList.remove("is-invalid");
        descriptionInput.classList.remove("is-invalid");
        searchInput.value = `${entry.code} - ${entry.description}`;
        suggestions.classList.add("d-none");
        suggestions.innerHTML = "";
      }), 250);
    });

    document.addEventListener("click", (event) => {
      if (!row.contains(event.target)) {
        suggestions.classList.add("d-none");
      }
    });

    removeBtn.addEventListener("click", () => removeDiagnosisRow(row));
  }

  async function runSearch(term, suggestionsEl, onPick) {
    try {
      const response = await fetch(`/api/consultations/icd10?q=${encodeURIComponent(term)}`);
      if (!response.ok) throw new Error("Request failed");
      const results = await response.json();

      if (results.length === 0) {
        suggestionsEl.innerHTML = '<div class="list-group-item text-muted">No matches found</div>';
        suggestionsEl.classList.remove("d-none");
        return;
      }

      suggestionsEl.innerHTML = results
        .map(
          (entry, i) =>
            `<button type="button" class="list-group-item list-group-item-action" data-index="${i}">` +
            `<strong>${entry.code}</strong> - ${entry.description}</button>`
        )
        .join("");
      suggestionsEl.classList.remove("d-none");

      suggestionsEl.querySelectorAll("button").forEach((btn, i) => {
        btn.addEventListener("click", () => onPick(results[i]));
      });
    } catch (err) {
      suggestionsEl.classList.add("d-none");
    }
  }

  function collectDiagnoses() {
    const rows = diagnosisRows.querySelectorAll(".diagnosis-row");
    const diagnoses = [];
    rows.forEach((row) => {
      const code = row.querySelector(".diagnosis-code").value.trim();
      const description = row.querySelector(".diagnosis-description").value.trim();
      if (code && description) {
        diagnoses.push({ icd10_code: code, description });
      }
    });
    return diagnoses;
  }

  function collectPayload() {
    return {
      notes: document.getElementById("notes").value.trim(),
      diagnoses: collectDiagnoses(),
    };
  }

  // --- Starting/resuming ------------------------------------------------------

  // Opens (or resumes) the consultation the instant this page loads, before the
  // doctor has written anything - so leaving the page without ever clicking Save
  // still leaves a draft the doctor can get back to, instead of losing the visit.
  // Idempotent server-side: reopening the same appointment's note resumes the
  // same draft rather than creating a duplicate.
  async function startConsultation() {
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/consultations/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientId,
          appointment_reference: appointmentReference || null,
        }),
      });

      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        showAlert(
          alertBox,
          typeof body.detail === "string" ? body.detail : "Unable to start this consultation."
        );
        return;
      }

      recordId = body.record_id;
      document.getElementById("notes").value = body.notes || "";

      diagnosisRows.innerHTML = "";
      if (Array.isArray(body.diagnoses) && body.diagnoses.length > 0) {
        body.diagnoses.forEach((d) => addDiagnosisRow(d.icd10_code, d.description));
        formHeading.textContent = "Continue Consultation Note";
      } else {
        addDiagnosisRow();
      }

      submitBtn.disabled = false;
    } catch (err) {
      showAlert(alertBox, "Unable to reach the server. Please check your connection and try again.");
    }
  }

  // --- Submission -----------------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault();
    hideAlert(alertBox);
    hideAlert(diagnosesAlert);
    clearFieldErrors();

    if (!recordId) {
      showAlert(alertBox, "This consultation hasn't finished starting yet. Please try again.");
      return;
    }

    const diagnoses = collectDiagnoses();
    const formValid = form.checkValidity();

    if (diagnosisRows.querySelectorAll(".diagnosis-row").length === 0 || diagnoses.length === 0) {
      showAlert(diagnosesAlert, "At least one diagnosis is required.");
      if (!formValid) form.classList.add("was-validated");
      return;
    }

    if (!formValid) {
      form.classList.add("was-validated");
      return;
    }

    submitBtn.disabled = true;
    try {
      const response = await fetch(`/api/consultations/${encodeURIComponent(recordId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload()),
      });

      if (response.status === 200) {
        if (confirmationModal) {
          confirmationModal.show();
        } else {
          window.location.href = `/patients/${encodeURIComponent(patientId)}`;
        }
        return;
      }

      const body = await response.json().catch(() => ({}));

      if (response.status === 404 || response.status === 403 || response.status === 409) {
        showAlert(alertBox, body.detail || "This consultation note could not be saved.");
        return;
      }

      if (response.status === 422) {
        if (!applyValidationErrors(body)) {
          showAlert(
            alertBox,
            typeof body.detail === "string" ? body.detail : "Please check the form for errors."
          );
        }
        return;
      }

      showAlert(alertBox, "Something went wrong while saving. Please try again.");
    } catch (err) {
      showAlert(alertBox, "Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  document.getElementById("view-record-btn").addEventListener("click", () => {
    if (recordId) window.location.href = `/consultations/${encodeURIComponent(recordId)}`;
  });
  document.getElementById("back-to-patient-btn").addEventListener("click", () => {
    window.location.href = `/patients/${encodeURIComponent(patientId)}`;
  });
  cancelBtn.addEventListener("click", () => {
    // Same destination as the "Back" link above - wherever this note was
    // opened from, not the patient details page.
    window.location.href = backLink.href;
  });
  addDiagnosisBtn.addEventListener("click", () => addDiagnosisRow());
  form.addEventListener("submit", handleSubmit);

  // If this note was started from the Start Consultation queue, "back" should
  // return there (where the doctor will see this appointment's updated
  // state) rather than to the general My Schedule page.
  if (appointmentReference) {
    backLink.href = "/appointments/consultations";
    backLink.textContent = "Back to Start Consultation";
  }

  // "View Patient Details" opens in a new tab so an in-progress draft note
  // isn't lost - its own Back button should return to this exact page
  // (including appointment_reference), not somewhere generic.
  viewPatientLink.href =
    `/patients/${encodeURIComponent(patientId)}?` +
    `from=${encodeURIComponent(window.location.pathname + window.location.search)}` +
    `&label=${encodeURIComponent("Back to Consultation Note")}`;

  loadPatientName();
  startConsultation();
})();
