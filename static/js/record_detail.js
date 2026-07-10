(function () {
  "use strict";

  const root = document.getElementById("record-detail-root");
  if (!root) return;

  const recordId = root.dataset.recordId;
  const alertBox = document.getElementById("detail-alert");
  const notFoundAlert = document.getElementById("not-found-alert");
  const content = document.getElementById("record-content");
  const backLink = document.getElementById("back-to-patient-link");
  const diagnosisList = document.getElementById("diagnosis-list");

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function renderDiagnoses(diagnoses) {
    diagnosisList.innerHTML = diagnoses
      .map(
        (d) =>
          `<div class="card border-danger-subtle mb-2">
             <div class="card-body py-2 px-3">
               <span class="badge bg-danger-subtle text-danger-emphasis me-2">${d.icd10_code}</span>
               <span class="fw-semibold">${d.description}</span>
             </div>
           </div>`
      )
      .join("");
  }

  async function loadRecord() {
    try {
      const response = await fetch(`/api/records/${encodeURIComponent(recordId)}`);
      if (response.status === 404) {
        notFoundAlert.classList.remove("d-none");
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      const note = await response.json();

      document.getElementById("heading-record-id").textContent = note.record_id;
      document.getElementById("view-patient").textContent = `${note.patient_name} (${note.patient_id})`;
      document.getElementById("view-doctor").textContent = `${note.doctor_name} (${note.doctor_id})`;
      document.getElementById("view-visit-date").textContent = new Date(note.visit_date).toLocaleString();
      document.getElementById("view-notes").textContent = note.notes;
      renderDiagnoses(note.diagnoses);
      backLink.href = `/patients/${encodeURIComponent(note.patient_id)}`;

      content.classList.remove("d-none");
    } catch (err) {
      showAlert("Unable to load this consultation note. Please try again.");
    }
  }

  loadRecord();
})();
