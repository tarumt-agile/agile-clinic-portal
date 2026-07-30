(function () {
  "use strict";

  const root = document.getElementById("record-form-root");
  if (!root) return;

  const patientId = root.dataset.patientId;
  const form = document.getElementById("record-form");
  const alertBox = document.getElementById("form-alert");
  const diagnosesAlert = document.getElementById("diagnoses-alert");
  const submitBtn = document.getElementById("submit-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const doctorSelect = document.getElementById("doctor_id");
  const patientNameLabel = document.getElementById("patient-name-label");
  const diagnosisRows = document.getElementById("diagnosis-rows");
  const rowTemplate = document.getElementById("diagnosis-row-template");
  const addDiagnosisBtn = document.getElementById("add-diagnosis-btn");
  const confirmationModalEl = document.getElementById("confirmation-modal");
  const confirmationModal = window.bootstrap ? new bootstrap.Modal(confirmationModalEl) : null;

  let searchDebounceTimer = null;
  let lastCreatedRecordId = null;

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
  // onto the matching row's input. Falls back to top-level fields (doctor_id, notes).
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

  async function loadDoctors() {
    doctorSelect.innerHTML = '<option value="" selected disabled>Loading doctors...</option>';
    try {
      const response = await fetch("/api/staff/doctor");
      if (!response.ok) throw new Error("Request failed");
      const allDoctors = await response.json();
      const doctors = allDoctors.filter((d) => d.status === "active");

      if (doctors.length === 0) {
        doctorSelect.innerHTML = '<option value="" selected disabled>No doctors available</option>';
        return;
      }

      doctorSelect.innerHTML =
        '<option value="" selected disabled>Choose...</option>' +
        doctors.map((d) => `<option value="${d.staff_id}">${d.full_name}</option>`).join("");
    } catch (err) {
      doctorSelect.innerHTML = '<option value="" selected disabled>Unable to load doctors</option>';
    }
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

  function addDiagnosisRow() {
    const fragment = rowTemplate.content.cloneNode(true);
    const row = fragment.querySelector(".diagnosis-row");
    wireRow(row);
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
      const response = await fetch(`/api/records/icd10?q=${encodeURIComponent(term)}`);
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
      patient_id: patientId,
      doctor_id: doctorSelect.value,
      notes: document.getElementById("notes").value.trim(),
      diagnoses: collectDiagnoses(),
    };
  }

  // --- Submission -----------------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault();
    hideAlert(alertBox);
    hideAlert(diagnosesAlert);
    clearFieldErrors();

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
      const response = await fetch("/api/records", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload()),
      });

      if (response.status === 201) {
        const note = await response.json();
        lastCreatedRecordId = note.record_id;
        if (confirmationModal) {
          confirmationModal.show();
        } else {
          window.location.href = `/patients/${encodeURIComponent(patientId)}`;
        }
        return;
      }

      const body = await response.json().catch(() => ({}));

      if (response.status === 404 || response.status === 409) {
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
    if (lastCreatedRecordId) window.location.href = `/records/${encodeURIComponent(lastCreatedRecordId)}`;
  });
  document.getElementById("back-to-patient-btn").addEventListener("click", () => {
    window.location.href = `/patients/${encodeURIComponent(patientId)}`;
  });
  cancelBtn.addEventListener("click", () => {
    window.location.href = `/patients/${encodeURIComponent(patientId)}`;
  });
  addDiagnosisBtn.addEventListener("click", addDiagnosisRow);
  form.addEventListener("submit", handleSubmit);

  loadDoctors();
  loadPatientName();
  addDiagnosisRow();
})();
