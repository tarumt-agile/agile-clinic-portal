(function () {
  "use strict";

  const root = document.getElementById(
    "reports-dashboard-root"
  );
  if (!root) {
    return;
  }

  const rangeForm = document.getElementById(
    "report-date-range-form"
  );
  const fromInput = document.getElementById(
    "report-from-date"
  );
  const toInput = document.getElementById(
    "report-to-date"
  );
  const quickRangeInput = document.getElementById(
    "report-quick-range"
  );
  const exportButton = document.getElementById(
    "export-report-button"
  );
  const selectedRangeLabel = document.getElementById(
    "selected-range-label"
  );
  const totalAppointmentsValue = document.getElementById(
    "total-appointments-value"
  );
  const tableBody = document.getElementById(
    "daily-appointments-table-body"
  );
  const alertBox = document.getElementById(
    "reports-alert"
  );
  const loadingIndicator = document.getElementById(
    "reports-loading"
  );
  const chartCanvas = document.getElementById(
    "daily-appointments-chart"
  );
  const chartContext = chartCanvas.getContext("2d");

  let currentReport = null;
  let resizeTimer = null;
  let requestSequence = 0;

  function escapeHtml(value) {
    return String(value).replace(
      /[&<>"']/g,
      function (character) {
        return {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }[character];
      }
    );
  }

  async function readResponse(response) {
    const contentType =
      response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return {};
  }

  function showError(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideError() {
    alertBox.textContent = "";
    alertBox.classList.add("d-none");
  }

  function selectedRangeParams() {
    return new URLSearchParams({
      from: fromInput.value,
      to: toInput.value
    });
  }

  function parseInputDate(value) {
    const parts = value.split("-").map(Number);
    return new Date(
      parts[0],
      parts[1] - 1,
      parts[2],
      12
    );
  }

  function formatInputDate(value) {
    const year = value.getFullYear();
    const month = String(
      value.getMonth() + 1
    ).padStart(2, "0");
    const day = String(
      value.getDate()
    ).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function addDays(value, numberOfDays) {
    const result = new Date(value);
    result.setDate(
      result.getDate() + numberOfDays
    );
    return result;
  }

  function startOfWeek(value) {
    const daysSinceMonday =
      (value.getDay() + 6) % 7;
    return addDays(value, -daysSinceMonday);
  }

  function rangeForPreset(preset) {
    const today = parseInputDate(
      root.dataset.today
    );
    const monday = startOfWeek(today);

    if (preset === "today") {
      return [today, today];
    }
    if (preset === "yesterday") {
      const yesterday = addDays(today, -1);
      return [yesterday, yesterday];
    }
    if (preset === "tomorrow") {
      const tomorrow = addDays(today, 1);
      return [tomorrow, tomorrow];
    }
    if (preset === "this_week") {
      return [monday, addDays(monday, 6)];
    }
    if (preset === "last_week") {
      return [
        addDays(monday, -7),
        addDays(monday, -1)
      ];
    }
    if (preset === "next_week") {
      return [
        addDays(monday, 7),
        addDays(monday, 13)
      ];
    }
    if (preset === "this_month") {
      return [
        new Date(
          today.getFullYear(),
          today.getMonth(),
          1,
          12
        ),
        new Date(
          today.getFullYear(),
          today.getMonth() + 1,
          0,
          12
        )
      ];
    }
    if (preset === "last_month") {
      return [
        new Date(
          today.getFullYear(),
          today.getMonth() - 1,
          1,
          12
        ),
        new Date(
          today.getFullYear(),
          today.getMonth(),
          0,
          12
        )
      ];
    }
    return null;
  }

  function applyQuickRange() {
    const range = rangeForPreset(
      quickRangeInput.value
    );
    if (!range) {
      return;
    }

    fromInput.value = formatInputDate(range[0]);
    toInput.value = formatInputDate(range[1]);
    rangeForm.classList.remove("was-validated");
    refreshReports();
  }

  function validateRange() {
    rangeForm.classList.add("was-validated");

    if (!rangeForm.checkValidity()) {
      showError("Choose both a start date and an end date.");
      return false;
    }

    if (fromInput.value > toInput.value) {
      showError(
        "The start date must be on or before the end date."
      );
      return false;
    }

    hideError();
    return true;
  }

  function formatDate(dateValue, options) {
    return new Intl.DateTimeFormat(
      "en-MY",
      options
    ).format(
      new Date(dateValue + "T00:00:00")
    );
  }

  function renderTable(items) {
    if (items.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td
            colspan="3"
            class="text-center text-muted py-4"
          >
            No dates are available for this range.
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = items.map(
      function (item) {
        return `
          <tr>
            <td>
              ${escapeHtml(
                formatDate(item.date, {
                  day: "2-digit",
                  month: "short",
                  year: "numeric"
                })
              )}
            </td>
            <td>
              ${escapeHtml(
                formatDate(item.date, {
                  weekday: "long"
                })
              )}
            </td>
            <td class="text-end">
              ${escapeHtml(item.total)}
            </td>
          </tr>
        `;
      }
    ).join("");
  }

  function resizeCanvas() {
    const bounds = chartCanvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    chartCanvas.width = Math.max(
      1,
      Math.floor(bounds.width * ratio)
    );
    chartCanvas.height = Math.max(
      1,
      Math.floor(bounds.height * ratio)
    );
    chartContext.setTransform(
      ratio,
      0,
      0,
      ratio,
      0,
      0
    );
    return {
      width: bounds.width,
      height: bounds.height
    };
  }

  function renderChart(items) {
    const dimensions = resizeCanvas();
    const width = dimensions.width;
    const height = dimensions.height;

    chartContext.clearRect(0, 0, width, height);

    const margin = {
      top: 20,
      right: 16,
      bottom: 68,
      left: 44
    };
    const plotWidth = Math.max(
      1,
      width - margin.left - margin.right
    );
    const plotHeight = Math.max(
      1,
      height - margin.top - margin.bottom
    );
    const maximum = Math.max(
      1,
      ...items.map(function (item) {
        return item.total;
      })
    );
    const ySteps = Math.min(5, maximum);

    chartContext.strokeStyle = "#d9e2ec";
    chartContext.fillStyle = "#62778b";
    chartContext.lineWidth = 1;
    chartContext.font =
      '12px system-ui, -apple-system, "Segoe UI", sans-serif';
    chartContext.textAlign = "right";
    chartContext.textBaseline = "middle";

    for (let step = 0; step <= ySteps; step += 1) {
      const value = Math.round(
        maximum * step / ySteps
      );
      const y =
        margin.top +
        plotHeight -
        plotHeight * step / ySteps;

      chartContext.beginPath();
      chartContext.moveTo(margin.left, y);
      chartContext.lineTo(width - margin.right, y);
      chartContext.stroke();
      chartContext.fillText(
        String(value),
        margin.left - 8,
        y
      );
    }

    if (items.length === 0) {
      return;
    }

    const slotWidth = plotWidth / items.length;
    const barWidth = Math.max(
      2,
      Math.min(38, slotWidth * 0.62)
    );

    items.forEach(function (item, index) {
      const barHeight =
        plotHeight * item.total / maximum;
      const x =
        margin.left +
        slotWidth * index +
        (slotWidth - barWidth) / 2;
      const y = margin.top + plotHeight - barHeight;

      chartContext.fillStyle = "#2463a8";
      chartContext.fillRect(
        x,
        y,
        barWidth,
        Math.max(item.total > 0 ? 2 : 0, barHeight)
      );

      if (
        items.length <= 31 ||
        index % Math.ceil(items.length / 31) === 0
      ) {
        chartContext.save();
        chartContext.translate(
          x + barWidth / 2,
          margin.top + plotHeight + 10
        );
        chartContext.rotate(-Math.PI / 4);
        chartContext.fillStyle = "#62778b";
        chartContext.textAlign = "right";
        chartContext.textBaseline = "middle";
        chartContext.fillText(
          formatDate(item.date, {
            day: "2-digit",
            month: "short"
          }),
          0,
          0
        );
        chartContext.restore();
      }
    });
  }

  function renderReport(report) {
    currentReport = report;
    selectedRangeLabel.textContent =
      report.selected_range_label;
    totalAppointmentsValue.textContent =
      String(report.total_appointments);
    renderChart(report.daily_totals);
    renderTable(report.daily_totals);
    exportButton.disabled = false;
  }

  function setLoading(isLoading) {
    loadingIndicator.classList.toggle(
      "d-none",
      !isLoading
    );
    if (isLoading) {
      exportButton.disabled = true;
    }
  }

  async function refreshReports() {
    if (!validateRange()) {
      return;
    }

    const sequence = ++requestSequence;
    setLoading(true);

    try {
      const response = await fetch(
        "/api/reports/appointments/daily?" +
        selectedRangeParams().toString()
      );
      const data = await readResponse(response);

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "The report could not be loaded."
        );
      }

      if (sequence !== requestSequence) {
        return;
      }

      renderReport(data);
    } catch (error) {
      if (sequence !== requestSequence) {
        return;
      }
      currentReport = null;
      showError(error.message);
    } finally {
      if (sequence === requestSequence) {
        setLoading(false);
        exportButton.disabled = !currentReport;
      }
    }
  }

  function filenameFromResponse(response) {
    const disposition =
      response.headers.get("content-disposition") || "";
    const match = disposition.match(
      /filename="?([^";]+)"?/i
    );
    return match
      ? match[1]
      : "appointment-activity-report.pdf";
  }

  async function exportReport() {
    if (!validateRange()) {
      return;
    }

    exportButton.disabled = true;
    exportButton.textContent = "Generating PDF...";

    try {
      const response = await fetch(
        "/api/reports/appointments/daily/export.pdf?" +
        selectedRangeParams().toString()
      );

      if (!response.ok) {
        const data = await readResponse(response);
        throw new Error(
          data.detail ||
          "The PDF report could not be generated."
        );
      }

      const pdfBlob = await response.blob();
      const downloadUrl = URL.createObjectURL(pdfBlob);
      const downloadLink = document.createElement("a");
      downloadLink.href = downloadUrl;
      downloadLink.download =
        filenameFromResponse(response);
      document.body.appendChild(downloadLink);
      downloadLink.click();
      downloadLink.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      showError(error.message);
    } finally {
      exportButton.disabled = !currentReport;
      exportButton.textContent = "Export PDF";
    }
  }

  rangeForm.addEventListener(
    "submit",
    function (event) {
      event.preventDefault();
      refreshReports();
    }
  );

  [fromInput, toInput].forEach(function (input) {
    input.addEventListener("change", function () {
      quickRangeInput.value = "custom";
      if (fromInput.value && toInput.value) {
        refreshReports();
      }
    });
  });

  quickRangeInput.addEventListener(
    "change",
    applyQuickRange
  );

  exportButton.addEventListener(
    "click",
    exportReport
  );

  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(
      function () {
        if (currentReport) {
          renderChart(currentReport.daily_totals);
        }
      },
      120
    );
  });

  fromInput.value =
    root.dataset.defaultFrom || fromInput.value;
  toInput.value =
    root.dataset.defaultTo || toInput.value;
  quickRangeInput.value = "this_week";
  refreshReports();
})();
