(function () {
  "use strict";

  const root = document.getElementById("patient-detail-root");
  if (!root) return;

  const { showAlert, hideAlert, clearFieldErrors, applyValidationErrors, collectPayload, fillForm } =
    window.PatientForm;

  const patientId = root.dataset.patientId;
  const alertBox = document.getElementById("detail-alert");
  const notFoundAlert = document.getElementById("not-found-alert");
  const viewMode = document.getElementById("view-mode");
  const editForm = document.getElementById("edit-form");
  const editBtn = document.getElementById("edit-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const saveBtn = document.getElementById("save-btn");
  const successModalEl = document.getElementById("success-modal");
  const successModal = window.bootstrap ? new bootstrap.Modal(successModalEl) : null;

  let currentPatient = null;

  function renderView(patient) {
    document.getElementById("heading-patient-id").textContent = patient.patient_id;
    document.getElementById("view-full-name").textContent = patient.full_name;
    document.getElementById("view-dob").textContent = patient.date_of_birth;
    document.getElementById("view-gender").textContent = patient.gender;
    document.getElementById("view-phone").textContent = patient.phone_number;
    document.getElementById("view-email").textContent = patient.email || "-";
    document.getElementById("view-ic").textContent = patient.ic_or_passport;
    document.getElementById("view-address").textContent = patient.address || "-";
  }

  function enterEditMode() {
    fillForm(editForm, currentPatient);
    editForm.classList.remove("was-validated");
    clearFieldErrors(editForm);
    hideAlert(alertBox);
    viewMode.classList.add("d-none");
    editForm.classList.remove("d-none");
    editBtn.classList.add("d-none");
  }

  function exitEditMode() {
    editForm.classList.add("d-none");
    viewMode.classList.remove("d-none");
    editBtn.classList.remove("d-none");
  }

  async function loadPatient() {
    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(patientId)}`);
      if (response.status === 404) {
        notFoundAlert.classList.remove("d-none");
        editBtn.classList.add("d-none");
        viewMode.classList.add("d-none");
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      currentPatient = await response.json();
      renderView(currentPatient);
    } catch (err) {
      showAlert(alertBox, "Unable to load this patient. Please try again.");
    }
  }

  async function handleSave(event) {
    event.preventDefault();
    hideAlert(alertBox);
    clearFieldErrors(editForm);

    if (!editForm.checkValidity()) {
      editForm.classList.add("was-validated");
      return;
    }

    saveBtn.disabled = true;
    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(patientId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload(editForm)),
      });

      if (response.ok) {
        currentPatient = await response.json();
        renderView(currentPatient);
        exitEditMode();
        if (successModal) successModal.show();
        return;
      }

      if (response.status === 422) {
        const body = await response.json();
        if (!applyValidationErrors(editForm, body)) {
          showAlert(alertBox, "Please check the form for errors.");
        }
        return;
      }

      if (response.status === 409) {
        const body = await response.json();
        showAlert(alertBox, body.detail || "This IC/passport number is already in use.");
        return;
      }

      if (response.status === 404) {
        notFoundAlert.classList.remove("d-none");
        editForm.classList.add("d-none");
        return;
      }

      showAlert(alertBox, "Something went wrong while saving. Please try again.");
    } catch (err) {
      showAlert(alertBox, "Unable to reach the server. Please check your connection and try again.");
    } finally {
      saveBtn.disabled = false;
    }
  }

  editBtn.addEventListener("click", enterEditMode);
  cancelBtn.addEventListener("click", exitEditMode);
  editForm.addEventListener("submit", handleSave);

  loadPatient();
})();
