(function () {
  "use strict";

  const root = document.getElementById(
    "pharmacy-root"
  );
  if (!root) {
    return;
  }

  const alertBox = document.getElementById(
    "pharmacy-alert"
  );
  const loadingBox = document.getElementById(
    "pharmacy-loading"
  );
  const emptyBox = document.getElementById(
    "pharmacy-empty"
  );
  const tableWrap = document.getElementById(
    "pharmacy-table-wrap"
  );
  const tableBody = document.getElementById(
    "pharmacy-table-body"
  );
  const searchInput = document.getElementById(
    "pharmacy-search"
  );
  const includeInactive =
    document.getElementById(
      "include-inactive"
    );

  const medicationForm =
    document.getElementById(
      "medication-form"
    );
  const medicationFormAlert =
    document.getElementById(
      "medication-form-alert"
    );
  const medicationModalElement =
    document.getElementById(
      "medication-modal"
    );
  const medicationModal =
    new bootstrap.Modal(
      medicationModalElement
    );

  const stockForm = document.getElementById(
    "stock-form"
  );
  const stockFormAlert =
    document.getElementById(
      "stock-form-alert"
    );
  const stockModal = new bootstrap.Modal(
    document.getElementById(
      "stock-modal"
    )
  );

  let medications = [];
  let searchTimer = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function readResponse(response) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  function showAlert(element, message) {
    element.textContent = message;
    element.classList.remove("d-none");
  }

  function hideAlert(element) {
    element.textContent = "";
    element.classList.add("d-none");
  }

  function stockClass(item) {
    if (item.stock_quantity === 0) {
      return "pharmacy-stock-empty";
    }
    if (item.low_stock) {
      return "pharmacy-stock-low";
    }
    return "";
  }

  function renderSummary() {
    document.getElementById(
      "medication-total"
    ).textContent = String(
      medications.length
    );
    document.getElementById(
      "low-stock-total"
    ).textContent = String(
      medications.filter(function (item) {
        return (
          item.low_stock &&
          item.stock_quantity > 0
        );
      }).length
    );
    document.getElementById(
      "out-of-stock-total"
    ).textContent = String(
      medications.filter(function (item) {
        return item.stock_quantity === 0;
      }).length
    );
  }

  function renderMedications() {
    renderSummary();
    loadingBox.classList.add("d-none");

    if (medications.length === 0) {
      tableWrap.classList.add("d-none");
      emptyBox.classList.remove("d-none");
      tableBody.innerHTML = "";
      return;
    }

    emptyBox.classList.add("d-none");
    tableWrap.classList.remove("d-none");

    tableBody.innerHTML = medications
      .map(function (item) {
        const statusClass = item.is_active
          ? "text-bg-success"
          : "text-bg-secondary";
        const statusText = item.is_active
          ? "Active"
          : "Inactive";

        return `
          <tr>
            <td class="text-nowrap">
              ${escapeHtml(item.medication_id)}
            </td>
            <td>
              <strong>
                ${escapeHtml(item.name)}
              </strong>
            </td>
            <td>${escapeHtml(item.form)}</td>
            <td>
              ${escapeHtml(
                item.standard_dosage
              )}
            </td>
            <td class="${stockClass(item)}">
              <span class="pharmacy-stock-quantity">
                ${item.stock_quantity}
                ${escapeHtml(item.unit)}
              </span>
              <span
                class="d-block small
                  text-muted fw-normal"
              >
                Reorder at ${item.reorder_level}
              </span>
            </td>
            <td>
              <span class="badge ${statusClass}">
                ${statusText}
              </span>
            </td>
            <td class="text-end text-nowrap">
              <button
                type="button"
                class="btn btn-sm
                  btn-outline-primary
                  adjust-stock-button"
                data-medication-id="${
                  escapeHtml(
                    item.medication_id
                  )
                }"
              >
                Stock
              </button>
              <button
                type="button"
                class="btn btn-sm
                  btn-outline-secondary
                  edit-medication-button"
                data-medication-id="${
                  escapeHtml(
                    item.medication_id
                  )
                }"
              >
                Edit
              </button>
            </td>
          </tr>
        `;
      })
      .join("");

    tableBody.querySelectorAll(
      ".edit-medication-button"
    ).forEach(function (button) {
      button.addEventListener(
        "click",
        function () {
          openEditMedication(
            button.dataset.medicationId
          );
        }
      );
    });

    tableBody.querySelectorAll(
      ".adjust-stock-button"
    ).forEach(function (button) {
      button.addEventListener(
        "click",
        function () {
          openStockAdjustment(
            button.dataset.medicationId
          );
        }
      );
    });
  }

  async function loadMedications() {
    hideAlert(alertBox);

    const params = new URLSearchParams();
    const query = searchInput.value.trim();
    if (query) {
      params.set("q", query);
    }
    if (includeInactive.checked) {
      params.set("include_inactive", "true");
    }

    try {
      const response = await fetch(
        "/api/pharmacy/medications?" +
        params.toString()
      );
      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Medications could not be loaded."
        );
      }

      medications = Array.isArray(data.items)
        ? data.items
        : [];
      renderMedications();

    } catch (error) {
      loadingBox.classList.add("d-none");
      showAlert(
        alertBox,
        error.message ||
        "Medications could not be loaded."
      );
    }
  }

  function resetMedicationForm() {
    medicationForm.reset();
    medicationForm.classList.remove(
      "was-validated"
    );
    hideAlert(medicationFormAlert);
    document.getElementById(
      "medication-edit-id"
    ).value = "";
    document.getElementById(
      "medication-unit"
    ).value = "units";
    document.getElementById(
      "medication-reorder-level"
    ).value = "10";
    document.getElementById(
      "medication-initial-stock"
    ).value = "0";
    document.getElementById(
      "medication-active"
    ).checked = true;
  }

  function openAddMedication() {
    resetMedicationForm();
    document.getElementById(
      "medication-modal-title"
    ).textContent = "Add Medication";
    document.getElementById(
      "initial-stock-group"
    ).classList.remove("d-none");
    medicationModal.show();
  }

  function openEditMedication(medicationId) {
    const item = medications.find(
      function (medication) {
        return (
          medication.medication_id ===
          medicationId
        );
      }
    );
    if (!item) {
      return;
    }

    resetMedicationForm();
    document.getElementById(
      "medication-modal-title"
    ).textContent = "Edit Medication";
    document.getElementById(
      "medication-edit-id"
    ).value = item.medication_id;
    document.getElementById(
      "medication-name"
    ).value = item.name;
    document.getElementById(
      "medication-form-type"
    ).value = item.form;
    document.getElementById(
      "medication-standard-dosage"
    ).value = item.standard_dosage;
    document.getElementById(
      "medication-unit"
    ).value = item.unit;
    document.getElementById(
      "medication-reorder-level"
    ).value = String(item.reorder_level);
    document.getElementById(
      "medication-active"
    ).checked = item.is_active;
    document.getElementById(
      "initial-stock-group"
    ).classList.add("d-none");
    medicationModal.show();
  }

  function medicationPayload(isEdit) {
    const payload = {
      name: document.getElementById(
        "medication-name"
      ).value,
      form: document.getElementById(
        "medication-form-type"
      ).value,
      standard_dosage:
        document.getElementById(
          "medication-standard-dosage"
        ).value,
      unit: document.getElementById(
        "medication-unit"
      ).value,
      reorder_level: Number(
        document.getElementById(
          "medication-reorder-level"
        ).value
      ),
      is_active: document.getElementById(
        "medication-active"
      ).checked
    };

    if (!isEdit) {
      payload.initial_stock = Number(
        document.getElementById(
          "medication-initial-stock"
        ).value || 0
      );
    }

    return payload;
  }

  async function loadStockHistory(
    medicationId
  ) {
    const historyBox =
      document.getElementById(
        "stock-history"
      );
    historyBox.innerHTML = `
      <p class="text-muted p-3 mb-0">
        Loading stock history...
      </p>
    `;

    const response = await fetch(
      "/api/pharmacy/medications/" +
      encodeURIComponent(medicationId) +
      "/transactions"
    );
    const data = await readResponse(response);

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Stock history could not be loaded."
      );
    }

    if (!Array.isArray(data) || data.length === 0) {
      historyBox.innerHTML = `
        <p class="text-muted p-3 mb-0">
          No stock adjustments recorded.
        </p>
      `;
      return;
    }

    historyBox.innerHTML = data
      .map(function (item) {
        const change =
          item.quantity_change > 0
            ? `+${item.quantity_change}`
            : String(item.quantity_change);

        return `
          <div class="stock-history-item">
            <strong>
              ${escapeHtml(change)}
            </strong>
            <div>
              ${escapeHtml(item.reason)}
              <span
                class="d-block small text-muted"
              >
                ${escapeHtml(
                  item.performed_by_staff_name
                )}
                ·
                ${escapeHtml(
                  new Date(
                    item.created_at
                  ).toLocaleString()
                )}
              </span>
            </div>
            <span class="text-muted">
              Balance ${item.balance_after}
            </span>
          </div>
        `;
      })
      .join("");
  }

  async function openStockAdjustment(
    medicationId
  ) {
    const item = medications.find(
      function (medication) {
        return (
          medication.medication_id ===
          medicationId
        );
      }
    );
    if (!item) {
      return;
    }

    stockForm.reset();
    stockForm.classList.remove(
      "was-validated"
    );
    hideAlert(stockFormAlert);
    document.getElementById(
      "stock-medication-id"
    ).value = item.medication_id;
    document.getElementById(
      "stock-medication-label"
    ).textContent =
      `${item.prescription_value} · ` +
      `Current stock: ${item.stock_quantity} ` +
      item.unit;

    stockModal.show();

    try {
      await loadStockHistory(
        item.medication_id
      );
    } catch (error) {
      showAlert(
        stockFormAlert,
        error.message
      );
    }
  }

  document.getElementById(
    "add-medication-button"
  ).addEventListener(
    "click",
    openAddMedication
  );

  medicationForm.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();
      hideAlert(medicationFormAlert);

      if (!medicationForm.checkValidity()) {
        medicationForm.classList.add(
          "was-validated"
        );
        return;
      }

      const medicationId =
        document.getElementById(
          "medication-edit-id"
        ).value;
      const isEdit = Boolean(medicationId);
      const saveButton =
        document.getElementById(
          "save-medication-button"
        );
      saveButton.disabled = true;

      try {
        const response = await fetch(
          isEdit
            ? "/api/pharmacy/medications/" +
              encodeURIComponent(
                medicationId
              )
            : "/api/pharmacy/medications",
          {
            method: isEdit ? "PATCH" : "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify(
              medicationPayload(isEdit)
            )
          }
        );
        const data = await readResponse(response);

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Medication could not be saved."
          );
        }

        medicationModal.hide();
        await loadMedications();

      } catch (error) {
        showAlert(
          medicationFormAlert,
          error.message
        );
      } finally {
        saveButton.disabled = false;
      }
    }
  );

  stockForm.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();
      hideAlert(stockFormAlert);

      if (!stockForm.checkValidity()) {
        stockForm.classList.add(
          "was-validated"
        );
        return;
      }

      const medicationId =
        document.getElementById(
          "stock-medication-id"
        ).value;
      const saveButton =
        document.getElementById(
          "save-stock-button"
        );
      saveButton.disabled = true;

      try {
        const response = await fetch(
          "/api/pharmacy/medications/" +
          encodeURIComponent(medicationId) +
          "/stock-adjustments",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              quantity_change: Number(
                document.getElementById(
                  "stock-quantity-change"
                ).value
              ),
              reason: document.getElementById(
                "stock-reason"
              ).value
            })
          }
        );
        const data = await readResponse(response);

        if (!response.ok) {
          throw new Error(
            data.detail ||
            "Stock adjustment could not be saved."
          );
        }

        stockForm.reset();
        document.getElementById(
          "stock-medication-id"
        ).value = medicationId;
        await loadMedications();

        const refreshed = medications.find(
          function (item) {
            return (
              item.medication_id ===
              medicationId
            );
          }
        );
        if (refreshed) {
          document.getElementById(
            "stock-medication-label"
          ).textContent =
            `${refreshed.prescription_value} · ` +
            `Current stock: ` +
            `${refreshed.stock_quantity} ` +
            refreshed.unit;
        }

        await loadStockHistory(medicationId);

      } catch (error) {
        showAlert(
          stockFormAlert,
          error.message
        );
      } finally {
        saveButton.disabled = false;
      }
    }
  );

  searchInput.addEventListener(
    "input",
    function () {
      if (searchTimer) {
        window.clearTimeout(searchTimer);
      }
      searchTimer = window.setTimeout(
        loadMedications,
        250
      );
    }
  );

  includeInactive.addEventListener(
    "change",
    loadMedications
  );

  loadMedications();
})();
