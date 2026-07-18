(function () {
  "use strict";

  const root = document.getElementById(
    "record-detail-root"
  );

  if (!root) {
    return;
  }

  const recordId = root.dataset.recordId;

  const alertBox = document.getElementById(
    "detail-alert"
  );

  const notFoundAlert =
    document.getElementById(
      "not-found-alert"
    );

  const content = document.getElementById(
    "record-content"
  );

  const backLink = document.getElementById(
    "back-to-patient-link"
  );

  const diagnosisList =
    document.getElementById(
      "diagnosis-list"
    );

  const prescriptionAlert =
    document.getElementById(
      "record-prescription-alert"
    );

  const prescriptionForm =
    document.getElementById(
      "add-prescription-form"
    );

  const formAlert =
    document.getElementById(
      "prescription-form-alert"
    );

  const medicationInput =
    document.getElementById(
      "prescription-medication"
    );

  const dosageInput =
    document.getElementById(
      "prescription-dosage"
    );

  const frequencyInput =
    document.getElementById(
      "prescription-frequency"
    );

  const durationInput =
    document.getElementById(
      "prescription-duration"
    );

  const diagnosisIdInput =
    document.getElementById(
      "prescription-diagnosis-id"
    );

  const selectedDiagnosisLabel =
    document.getElementById(
      "selected-diagnosis-label"
    );

  const saveButton =
    document.getElementById(
      "save-prescription-button"
    );

  const modalElement =
    document.getElementById(
      "add-prescription-modal"
    );

  const prescriptionModal =
    window.bootstrap && modalElement
      ? new bootstrap.Modal(modalElement)
      : null;

  let currentRecord = null;
  let prescriptions = [];
  let optionsLoaded = false;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function showAlert(
    element,
    message
  ) {
    if (!element) {
      return;
    }

    element.textContent = message;
    element.classList.remove("d-none");
  }

  function hideAlert(element) {
    if (!element) {
      return;
    }

    element.textContent = "";
    element.classList.add("d-none");
  }

  async function readResponse(response) {
    const contentType =
      response.headers.get(
        "content-type"
      ) || "";

    if (
      contentType.includes(
        "application/json"
      )
    ) {
      return await response.json();
    }

    const text = await response.text();

    return {
      detail:
        text ||
        `Request failed with status ${response.status}.`
    };
  }

  function createOptions(
    values,
    placeholder
  ) {
    const options = values.map(
      function (item) {
        const value =
          typeof item === "string"
            ? item
            : item.value;

        const label =
          typeof item === "string"
            ? item
            : item.label;

        return `
          <option value="${escapeHtml(value)}">
            ${escapeHtml(label)}
          </option>
        `;
      }
    );

    return `
      <option value="">
        ${escapeHtml(placeholder)}
      </option>

      ${options.join("")}
    `;
  }

  async function loadPrescriptionOptions() {
    if (optionsLoaded) {
      return;
    }

    const response = await fetch(
      "/api/prescriptions/options"
    );

    const data = await readResponse(response);

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Prescription options could not be loaded."
      );
    }

    medicationInput.innerHTML =
      createOptions(
        data.medications,
        "Choose a medication..."
      );

    dosageInput.innerHTML =
      createOptions(
        data.dosages,
        "Choose a dosage..."
      );

    frequencyInput.innerHTML =
      createOptions(
        data.frequencies,
        "Choose a frequency..."
      );

    durationInput.innerHTML =
      createOptions(
        data.durations,
        "Choose a duration..."
      );

    optionsLoaded = true;
  }

  function prescriptionsForDiagnosis(
    diagnosisId
  ) {
    return prescriptions.filter(
      function (prescription) {
        return (
          Number(
            prescription.diagnosis_id
          )
          === Number(diagnosisId)
        );
      }
    );
  }

  function renderMedicationCards(items) {
    if (items.length === 0) {
      return `
        <p class="text-muted mb-0">
          No medication has been added
          for this diagnosis.
        </p>
      `;
    }

    return items
      .map(function (item) {
        return `
          <article
            class="border rounded p-3 mb-2 bg-light"
          >
            <div
              class="d-flex justify-content-between
                align-items-start gap-3"
            >
              <div>
                <h4 class="h6 mb-2">
                  ${escapeHtml(
                    item.medication
                  )}
                </h4>

                <p class="mb-1">
                  <strong>Dosage:</strong>
                  ${escapeHtml(
                    item.dosage
                  )}
                </p>

                <p class="mb-1">
                  <strong>Frequency:</strong>
                  ${escapeHtml(
                    item.frequency
                  )}
                </p>

                <p class="mb-0">
                  <strong>Duration:</strong>
                  ${escapeHtml(
                    item.duration
                  )}
                </p>
              </div>

              <div class="text-end">
                <span
                  class="badge text-bg-success"
                >
                  ${escapeHtml(
                    item.status
                  )}
                </span>

                <div
                  class="small text-muted mt-2"
                >
                  ${escapeHtml(
                    new Date(
                      item.issued_at
                    ).toLocaleString()
                  )}
                </div>
              </div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderDiagnoses() {
    if (
      !currentRecord ||
      !Array.isArray(
        currentRecord.diagnoses
      ) ||
      currentRecord.diagnoses.length === 0
    ) {
      diagnosisList.innerHTML = `
        <div class="alert alert-warning">
          No diagnoses were recorded for
          this consultation.
        </div>
      `;

      return;
    }

    diagnosisList.innerHTML =
      currentRecord.diagnoses
        .map(function (
          diagnosis,
          index
        ) {
          const items =
            prescriptionsForDiagnosis(
              diagnosis.id
            );

          return `
            <article class="card mb-4">
              <div class="card-header">
                <div
                  class="d-flex
                    justify-content-between
                    align-items-center gap-3"
                >
                  <div>
                    <p
                      class="text-muted
                        small mb-1"
                    >
                      Diagnosis ${index + 1}
                    </p>

                    <h3 class="h5 mb-0">
                      <span
                        class="badge
                          bg-danger-subtle
                          text-danger-emphasis
                          me-2"
                      >
                        ${escapeHtml(
                          diagnosis.icd10_code
                        )}
                      </span>

                      ${escapeHtml(
                        diagnosis.description
                      )}
                    </h3>
                  </div>

                  <button
                    type="button"
                    class="btn btn-sm
                      btn-primary
                      add-medication-button"
                    data-diagnosis-id="${
                      diagnosis.id
                    }"
                    data-diagnosis-code="${
                      escapeHtml(
                        diagnosis.icd10_code
                      )
                    }"
                    data-diagnosis-description="${
                      escapeHtml(
                        diagnosis.description
                      )
                    }"
                  >
                    + Add Medication
                  </button>
                </div>
              </div>

              <div class="card-body">
                <h4 class="h6">
                  Prescribed Medication
                </h4>

                ${renderMedicationCards(items)}
              </div>
            </article>
          `;
        })
        .join("");

    diagnosisList
      .querySelectorAll(
        ".add-medication-button"
      )
      .forEach(function (button) {
        button.addEventListener(
          "click",
          function () {
            openPrescriptionModal(
              Number(
                button.dataset.diagnosisId
              ),
              button.dataset.diagnosisCode,
              button.dataset
                .diagnosisDescription
            );
          }
        );
      });
  }

  async function openPrescriptionModal(
    diagnosisId,
    diagnosisCode,
    diagnosisDescription
  ) {
    hideAlert(formAlert);

    prescriptionForm.reset();

    prescriptionForm.classList.remove(
      "was-validated"
    );

    diagnosisIdInput.value =
      String(diagnosisId);

    selectedDiagnosisLabel.textContent =
      `${diagnosisCode} - ` +
      diagnosisDescription;

    try {
      await loadPrescriptionOptions();

      if (prescriptionModal) {
        prescriptionModal.show();
      }

    } catch (error) {
      showAlert(
        prescriptionAlert,
        error.message
      );
    }
  }

  async function loadPrescriptions() {
    hideAlert(prescriptionAlert);

    const response = await fetch(
      "/api/prescriptions/consultation/" +
      encodeURIComponent(recordId)
    );

    const data = await readResponse(response);

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Prescriptions could not be loaded."
      );
    }

    prescriptions = Array.isArray(
      data.items
    )
      ? data.items
      : [];
  }

  async function loadRecord() {
    try {
      const response = await fetch(
        "/api/records/" +
        encodeURIComponent(recordId)
      );

      const data = await readResponse(response);

      if (response.status === 404) {
        notFoundAlert.classList.remove(
          "d-none"
        );

        return;
      }

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Consultation could not be loaded."
        );
      }

      currentRecord = data;

      document.getElementById(
        "heading-record-id"
      ).textContent =
        data.record_id;

      document.getElementById(
        "view-patient"
      ).textContent =
        `${data.patient_name} ` +
        `(${data.patient_id})`;

      document.getElementById(
        "view-doctor"
      ).textContent =
        `${data.doctor_name} ` +
        `(${data.doctor_id})`;

      document.getElementById(
        "view-visit-date"
      ).textContent =
        new Date(
          data.visit_date
        ).toLocaleString();

      document.getElementById(
        "view-notes"
      ).textContent =
        data.notes;

      backLink.href =
        "/patients/" +
        encodeURIComponent(
          data.patient_id
        );

      await loadPrescriptions();

      renderDiagnoses();

      content.classList.remove(
        "d-none"
      );

    } catch (error) {
      console.error(
        "Consultation loading error:",
        error
      );

      showAlert(
        alertBox,
        error.message ||
        "Unable to load this consultation."
      );
    }
  }

  prescriptionForm.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();

      hideAlert(formAlert);

      if (
        !prescriptionForm.checkValidity()
      ) {
        prescriptionForm.classList.add(
          "was-validated"
        );

        return;
      }

      const payload = {
        consultation_record_id:
          recordId,

        diagnosis_id: Number(
          diagnosisIdInput.value
        ),

        medication:
          medicationInput.value,

        dosage:
          dosageInput.value,

        frequency:
          frequencyInput.value,

        duration:
          durationInput.value
      };

      saveButton.disabled = true;
      saveButton.textContent =
        "Adding...";

      try {
        const response = await fetch(
          "/api/prescriptions",
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify(
              payload
            )
          }
        );

        const data =
          await readResponse(response);

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Medication could not be added."
          );
        }

        if (prescriptionModal) {
          prescriptionModal.hide();
        }

        await loadPrescriptions();

        renderDiagnoses();

      } catch (error) {
        showAlert(
          formAlert,
          error.message
        );

      } finally {
        saveButton.disabled = false;
        saveButton.textContent =
          "Add Medication";
      }
    }
  );

  loadRecord();
})();