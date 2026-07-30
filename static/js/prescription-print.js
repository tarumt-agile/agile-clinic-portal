(function () {
  "use strict";

  const root = document.getElementById(
    "prescription-detail-root"
  );

  if (!root) {
    return;
  }

  const prescriptionId =
    root.dataset.prescriptionId;

  const alertBox = document.getElementById(
    "prescription-detail-alert"
  );

  const loadingBox = document.getElementById(
    "prescription-loading"
  );

  const sheet = document.getElementById(
    "prescription-sheet"
  );

  const printButton = document.getElementById(
    "print-prescription-button"
  );

  const backLink = document.getElementById(
    "back-to-consultation-link"
  );

  function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value || "—";
    }
  }

  async function readResponse(response) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  function formatDate(value) {
    if (!value) {
      return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return new Intl.DateTimeFormat(
      undefined,
      {
        dateStyle: "long",
        timeStyle: "short"
      }
    ).format(date);
  }

  function showError(message) {
    loadingBox.classList.add("d-none");
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function renderPrescription(item) {
    setText(
      "print-prescription-id",
      item.prescription_id
    );

    setText(
      "print-issued-at",
      formatDate(item.issued_at)
    );

    setText(
      "print-patient-name",
      item.patient_name
    );

    setText(
      "print-patient-id",
      item.patient_id
    );

    setText(
      "print-doctor-name",
      item.prescribing_doctor_name
    );

    setText(
      "print-doctor-id",
      item.prescribing_doctor_id
    );

    setText(
      "print-diagnosis",
      `${item.diagnosis_code} — ` +
        item.diagnosis_description
    );

    setText(
      "print-medication",
      item.medication
    );

    setText(
      "print-dosage",
      item.dosage
    );

    setText(
      "print-frequency",
      item.frequency
    );

    setText(
      "print-duration",
      item.duration
    );

    setText(
      "print-signature-doctor",
      item.prescribing_doctor_name
    );

    backLink.href =
      "/consultations/" +
      encodeURIComponent(
        item.consultation_record_id
      );

    document.title =
      `Prescription ${item.prescription_id}`;

    loadingBox.classList.add("d-none");
    sheet.classList.remove("d-none");
    printButton.disabled = false;
  }

  async function loadPrescription() {
    try {
      const response = await fetch(
        "/api/prescriptions/" +
        encodeURIComponent(prescriptionId)
      );

      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Prescription could not be loaded."
        );
      }

      renderPrescription(data);

    } catch (error) {
      showError(
        error.message ||
        "Prescription could not be loaded."
      );
    }
  }

  printButton.addEventListener(
    "click",
    function () {
      window.print();
    }
  );

  loadPrescription();
})();
