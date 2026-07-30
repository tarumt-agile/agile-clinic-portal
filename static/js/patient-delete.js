(function () {
  "use strict";

  const root = document.getElementById("patient-detail-root");
  const deleteBtn = document.getElementById("delete-patient-button");
  if (!root || !deleteBtn) return;

  const patientId = root.dataset.patientId;
  const modalEl = document.getElementById("delete-patient-modal");
  const modal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl) : null;
  const modalAlert = document.getElementById("delete-patient-modal-alert");
  const confirmBtn = document.getElementById("confirm-delete-patient-button");

  function showAlert(message) {
    modalAlert.textContent = message;
    modalAlert.classList.remove("d-none");
  }

  function hideAlert() {
    modalAlert.textContent = "";
    modalAlert.classList.add("d-none");
  }

  deleteBtn.addEventListener("click", () => {
    hideAlert();
    if (modal) modal.show();
  });

  confirmBtn.addEventListener("click", async () => {
    hideAlert();
    confirmBtn.disabled = true;
    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(patientId)}`, {
        method: "DELETE",
      });

      if (response.status === 204) {
        window.location.href = "/patients";
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(body.detail || "This patient could not be deleted.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      confirmBtn.disabled = false;
    }
  });
})();
