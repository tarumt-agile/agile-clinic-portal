(function () {
  "use strict";

  const root = document.getElementById(
    "patient-detail-root"
  );

  if (!root) {
    return;
  }

  const patientId = root.dataset.patientId;

  const tabButton = document.getElementById(
    "prescriptions-tab-btn"
  );

  const list = document.getElementById(
    "prescriptions-list"
  );

  const emptyBox = document.getElementById(
    "prescriptions-empty"
  );

  const alertBox = document.getElementById(
    "prescriptions-alert"
  );

  const editForm = document.getElementById(
    "edit-prescription-form"
  );

  const editModalElement =
    document.getElementById(
      "edit-prescription-modal"
    );

  const editModal = window.bootstrap
    ? new bootstrap.Modal(
        editModalElement
      )
    : null;

  let prescriptions = [];
  let hasLoaded = false;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatStatus(status) {
    return String(status || "")
      .replaceAll("_", " ")
      .replace(
        /\b\w/g,
        function (letter) {
          return letter.toUpperCase();
        }
      );
  }

  function formatDate(value) {
    return new Date(value).toLocaleString();
  }

  function renderHistory(history) {
    if (!history || history.length === 0) {
      return "";
    }

    return `
      <details class="mt-3">
        <summary class="fw-semibold">
          Dosage Change History
        </summary>

        <div class="mt-2">
          ${history.map(function (item) {
            return `
              <div
                class="border-start border-3
                  ps-3 py-2 mb-2"
              >
                <p class="mb-1">
                  <strong>
                    ${escapeHtml(
                      item.previous_dosage
                    )}
                  </strong>

                  →

                  <strong>
                    ${escapeHtml(
                      item.new_dosage
                    )}
                  </strong>
                </p>

                <p class="mb-1 small">
                  <strong>Reason:</strong>
                  ${escapeHtml(
                    item.change_reason
                  )}
                </p>

                <p class="mb-0 text-muted small">
                  Changed by
                  ${escapeHtml(
                    item.changed_by_doctor_name
                  )}
                  on
                  ${escapeHtml(
                    formatDate(item.changed_at)
                  )}
                </p>
              </div>
            `;
          }).join("")}
        </div>
      </details>
    `;
  }

  function renderPrescriptions() {
    if (prescriptions.length === 0) {
      emptyBox.classList.remove("d-none");
      list.innerHTML = "";
      return;
    }

    emptyBox.classList.add("d-none");

    list.innerHTML = prescriptions
      .map(function (item) {
        const editButton = item.can_edit
          ? `
            <button
              type="button"
              class="btn btn-sm
                btn-outline-primary
                edit-dosage-button"
              data-prescription-id="${
                escapeHtml(
                  item.prescription_id
                )
              }"
            >
              Edit Dosage
            </button>
          `
          : "";

        return `
          <article class="card mb-3">
            <div class="card-body">
              <div
                class="d-flex justify-content-between
                  align-items-start gap-3"
              >
                <div>
                  <div
                    class="d-flex align-items-center
                      gap-2 mb-2"
                  >
                    <h3 class="h5 mb-0">
                      ${escapeHtml(
                        item.medication
                      )}
                    </h3>

                    <span
                      class="badge text-bg-success"
                    >
                      ${escapeHtml(
                        formatStatus(item.status)
                      )}
                    </span>
                  </div>

                  <p class="mb-1">
                    <strong>Dosage:</strong>
                    ${escapeHtml(item.dosage)}
                  </p>

                  <p class="mb-1">
                    <strong>Frequency:</strong>
                    ${escapeHtml(item.frequency)}
                  </p>

                  <p class="mb-1">
                    <strong>Duration:</strong>
                    ${escapeHtml(item.duration)}
                  </p>

                  <p class="mb-1">
                    <strong>Doctor:</strong>
                    ${escapeHtml(
                      item.prescribing_doctor_name
                    )}
                  </p>

                  <p class="mb-1">
                    <strong>Consultation:</strong>

                    <a
                      href="/records/${
                        encodeURIComponent(
                          item.consultation_record_id
                        )
                      }"
                    >
                      ${escapeHtml(
                        item.consultation_record_id
                      )}
                    </a>
                  </p>

                  <p class="mb-0 text-muted small">
                    Issued:
                    ${escapeHtml(
                      formatDate(item.issued_at)
                    )}
                  </p>
                </div>

                <div>
                  ${editButton}
                </div>
              </div>

              ${renderHistory(item.history)}
            </div>
          </article>
        `;
      })
      .join("");

    list.querySelectorAll(
      ".edit-dosage-button"
    ).forEach(function (button) {
      button.addEventListener(
        "click",
        function () {
          openEditModal(
            button.dataset.prescriptionId
          );
        }
      );
    });
  }

  async function loadPrescriptions() {
    alertBox.classList.add("d-none");

    try {
      const response = await fetch(
        "/api/prescriptions/patient/" +
        encodeURIComponent(patientId)
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Prescription history could not be loaded."
        );
      }

      prescriptions = Array.isArray(data.items)
        ? data.items
        : [];

      renderPrescriptions();

    } catch (error) {
      alertBox.textContent = error.message;
      alertBox.classList.remove("d-none");
    }
  }

  function openEditModal(prescriptionId) {
    const prescription = prescriptions.find(
      function (item) {
        return (
          item.prescription_id
          === prescriptionId
        );
      }
    );

    if (!prescription || !prescription.can_edit) {
      return;
    }

    document.getElementById(
      "edit-prescription-id"
    ).value = prescription.prescription_id;

    document.getElementById(
      "edit-prescription-medication"
    ).value = prescription.medication;

    document.getElementById(
      "edit-prescription-dosage"
    ).value = prescription.dosage;

    document.getElementById(
      "edit-prescription-reason"
    ).value = "";

    document.getElementById(
      "edit-prescription-alert"
    ).classList.add("d-none");

    editForm.classList.remove(
      "was-validated"
    );

    if (editModal) {
      editModal.show();
    }
  }

  editForm.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();

      const updateAlert =
        document.getElementById(
          "edit-prescription-alert"
        );

      updateAlert.classList.add("d-none");

      if (!editForm.checkValidity()) {
        editForm.classList.add(
          "was-validated"
        );

        return;
      }

      const prescriptionId =
        document.getElementById(
          "edit-prescription-id"
        ).value;

      const dosage =
        document.getElementById(
          "edit-prescription-dosage"
        ).value
          .trim()
          .replace(/\s+/g, " ");

      const changeReason =
        document.getElementById(
          "edit-prescription-reason"
        ).value
          .trim()
          .replace(/\s+/g, " ");

      const saveButton =
        document.getElementById(
          "save-dosage-button"
        );

      saveButton.disabled = true;
      saveButton.textContent = "Saving...";

      try {
        const response = await fetch(
          "/api/prescriptions/" +
          encodeURIComponent(
            prescriptionId
          ) +
          "/dosage",
          {
            method: "PATCH",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              dosage: dosage,
              change_reason: changeReason
            })
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : "Dosage could not be updated."
          );
        }

        if (editModal) {
          editModal.hide();
        }

        await loadPrescriptions();

      } catch (error) {
        updateAlert.textContent =
          error.message;

        updateAlert.classList.remove(
          "d-none"
        );

      } finally {
        saveButton.disabled = false;
        saveButton.textContent =
          "Save Dosage";
      }
    }
  );

  tabButton.addEventListener(
    "shown.bs.tab",
    function () {
      if (!hasLoaded) {
        hasLoaded = true;
        loadPrescriptions();
      }
    }
  );
})();