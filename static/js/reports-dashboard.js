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
  const reportTypeInput = document.getElementById(
    "report-type"
  );
  const appointmentFilters = document.getElementById(
    "report-date-range-form"
  );
  const patientRegistrationFilters = document.getElementById(
    "patient-registration-filters"
  );
  const appointmentReportSection = document.getElementById(
    "appointment-activity-report"
  );
  const patientRegistrationReportSection = document.getElementById(
    "patient-registration-report"
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
  const chartTooltip = document.getElementById(
    "appointment-chart-tooltip"
  );
  const registrationYearInput = document.getElementById(
    "patient-registration-year"
  );
  const totalPatientRegistrations = document.getElementById(
    "total-patient-registrations"
  );
  const patientRegistrationsTableBody = document.getElementById(
    "monthly-patient-registrations-table-body"
  );
  const patientRegistrationChartCanvas = document.getElementById(
    "monthly-patient-registrations-chart"
  );
  const patientRegistrationChartTooltip = document.getElementById(
    "patient-registration-chart-tooltip"
  );
  const chartContext = chartCanvas.getContext("2d");
  const patientRegistrationChartContext =
    patientRegistrationChartCanvas.getContext("2d");

  let currentAppointmentReport = null;
  let currentPatientRegistrationReport = null;
  let chartBars = [];
  let patientRegistrationChartBars = [];
  let resizeTimer = null;
  let requestSequence = 0;
  let patientRequestSequence = 0;

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

  function renderPatientRegistrations(report) {
    currentPatientRegistrationReport = report;
    totalPatientRegistrations.textContent =
      String(report.total_registrations);
    patientRegistrationsTableBody.innerHTML =
      report.monthly_registrations.map(
        function (item) {
          return `
            <tr>
              <td>${escapeHtml(item.month)}</td>
              <td class="text-end">${escapeHtml(item.count)}</td>
            </tr>
          `;
        }
      ).join("");
    renderPatientRegistrationChart(
      report.monthly_registrations
    );
    exportButton.disabled = false;
  }

  async function refreshPatientRegistrations() {
    if (reportTypeInput.value !== "patient_registrations") {
      return;
    }
    const sequence = ++patientRequestSequence;
    exportButton.disabled = true;
    totalPatientRegistrations.textContent = "Loading...";
    try {
      const params = new URLSearchParams({
        year: registrationYearInput.value
      });
      const response = await fetch(
        "/api/reports/patients/registrations/monthly?" +
        params.toString()
      );
      const data = await readResponse(response);
      if (!response.ok) {
        throw new Error(
          data.detail ||
          "Patient registrations could not be loaded."
        );
      }
      if (
        sequence !== patientRequestSequence ||
        reportTypeInput.value !== "patient_registrations"
      ) {
        return;
      }
      renderPatientRegistrations(data);
    } catch (error) {
      if (sequence !== patientRequestSequence) {
        return;
      }
      currentPatientRegistrationReport = null;
      totalPatientRegistrations.textContent = "Unavailable";
      patientRegistrationsTableBody.innerHTML = `
        <tr>
          <td colspan="2" class="text-center text-muted py-4">
            Patient registrations could not be loaded.
          </td>
        </tr>
      `;
      showError(error.message);
    } finally {
      if (
        sequence === patientRequestSequence &&
        reportTypeInput.value === "patient_registrations"
      ) {
        exportButton.disabled =
          !currentPatientRegistrationReport;
      }
    }
  }

  function resizeCanvas(canvas, context) {
    const bounds = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(
      1,
      Math.floor(bounds.width * ratio)
    );
    canvas.height = Math.max(
      1,
      Math.floor(bounds.height * ratio)
    );
    context.setTransform(
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
    const dimensions = resizeCanvas(
      chartCanvas,
      chartContext
    );
    const width = dimensions.width;
    const height = dimensions.height;
    chartBars = [];
    chartTooltip.classList.add("d-none");

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

    chartContext.strokeStyle = "#e2e8f0";
    chartContext.fillStyle = "#475569";
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

      chartContext.fillStyle = "#4f46e5";
      const drawnHeight = Math.max(
        item.total > 0 ? 2 : 0,
        barHeight
      );
      chartContext.fillRect(
        x,
        y,
        barWidth,
        drawnHeight
      );
      chartBars.push({
        x: x,
        y: item.total > 0
          ? y
          : margin.top + plotHeight - 6,
        width: barWidth,
        height: Math.max(drawnHeight, 6),
        item: item
      });

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
        chartContext.fillStyle = "#475569";
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

  function renderPatientRegistrationChart(items) {
    const dimensions = resizeCanvas(
      patientRegistrationChartCanvas,
      patientRegistrationChartContext
    );
    const width = dimensions.width;
    const height = dimensions.height;
    const context = patientRegistrationChartContext;
    patientRegistrationChartBars = [];
    patientRegistrationChartTooltip.classList.add("d-none");
    context.clearRect(0, 0, width, height);

    const margin = {
      top: 20,
      right: 16,
      bottom: 48,
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
        return item.count;
      })
    );
    const ySteps = Math.min(5, maximum);

    context.strokeStyle = "#e2e8f0";
    context.fillStyle = "#475569";
    context.lineWidth = 1;
    context.font =
      '12px system-ui, -apple-system, "Segoe UI", sans-serif';
    context.textAlign = "right";
    context.textBaseline = "middle";

    for (let step = 0; step <= ySteps; step += 1) {
      const value = Math.round(
        maximum * step / ySteps
      );
      const y =
        margin.top +
        plotHeight -
        plotHeight * step / ySteps;
      context.beginPath();
      context.moveTo(margin.left, y);
      context.lineTo(width - margin.right, y);
      context.stroke();
      context.fillText(String(value), margin.left - 8, y);
    }

    if (items.length === 0) {
      return;
    }

    const slotWidth = plotWidth / items.length;
    const barWidth = Math.max(
      4,
      Math.min(38, slotWidth * 0.62)
    );
    items.forEach(function (item, index) {
      const barHeight =
        plotHeight * item.count / maximum;
      const x =
        margin.left +
        slotWidth * index +
        (slotWidth - barWidth) / 2;
      const y = margin.top + plotHeight - barHeight;
      const drawnHeight = Math.max(
        item.count > 0 ? 2 : 0,
        barHeight
      );

      context.fillStyle = "#4f46e5";
      context.fillRect(x, y, barWidth, drawnHeight);
      patientRegistrationChartBars.push({
        x: x,
        y: item.count > 0
          ? y
          : margin.top + plotHeight - 6,
        width: barWidth,
        height: Math.max(drawnHeight, 6),
        item: item
      });

      context.fillStyle = "#475569";
      context.textAlign = "center";
      context.textBaseline = "top";
      context.fillText(
        item.month.slice(0, 3),
        x + barWidth / 2,
        margin.top + plotHeight + 10
      );
    });
  }

  function hideChartTooltip() {
    chartTooltip.classList.add("d-none");
    chartCanvas.style.cursor = "default";
  }

  function showChartTooltip(event) {
    const bounds = chartCanvas.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    const hoveredBar = chartBars.find(
      function (bar) {
        return x >= bar.x &&
          x <= bar.x + bar.width &&
          y >= bar.y &&
          y <= bar.y + bar.height;
      }
    );

    if (!hoveredBar) {
      hideChartTooltip();
      return;
    }

    const count = hoveredBar.item.total;
    chartTooltip.textContent =
      formatDate(hoveredBar.item.date, {
        day: "2-digit",
        month: "short",
        year: "numeric"
      }) +
      ": " + count +
      (count === 1 ? " appointment" : " appointments");
    chartTooltip.classList.remove("d-none");
    chartCanvas.style.cursor = "pointer";

    const tooltipLeft = Math.min(
      Math.max(8, x + 12),
      Math.max(8, bounds.width - chartTooltip.offsetWidth - 8)
    );
    const tooltipTop = Math.max(
      8,
      y - chartTooltip.offsetHeight - 12
    );
    chartTooltip.style.left = tooltipLeft + "px";
    chartTooltip.style.top = tooltipTop + "px";
  }

  function hidePatientRegistrationChartTooltip() {
    patientRegistrationChartTooltip.classList.add("d-none");
    patientRegistrationChartCanvas.style.cursor = "default";
  }

  function showPatientRegistrationChartTooltip(event) {
    const bounds =
      patientRegistrationChartCanvas.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    const hoveredBar = patientRegistrationChartBars.find(
      function (bar) {
        return x >= bar.x &&
          x <= bar.x + bar.width &&
          y >= bar.y &&
          y <= bar.y + bar.height;
      }
    );

    if (!hoveredBar) {
      hidePatientRegistrationChartTooltip();
      return;
    }

    const count = hoveredBar.item.count;
    patientRegistrationChartTooltip.textContent =
      hoveredBar.item.month +
      ": " + count +
      (count === 1 ? " registration" : " registrations");
    patientRegistrationChartTooltip.classList.remove("d-none");
    patientRegistrationChartCanvas.style.cursor = "pointer";

    const tooltipLeft = Math.min(
      Math.max(8, x + 12),
      Math.max(
        8,
        bounds.width -
        patientRegistrationChartTooltip.offsetWidth -
        8
      )
    );
    const tooltipTop = Math.max(
      8,
      y - patientRegistrationChartTooltip.offsetHeight - 12
    );
    patientRegistrationChartTooltip.style.left =
      tooltipLeft + "px";
    patientRegistrationChartTooltip.style.top =
      tooltipTop + "px";
  }

  function renderReport(report) {
    currentAppointmentReport = report;
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
    if (reportTypeInput.value !== "appointment_activity") {
      return;
    }
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

      if (
        sequence !== requestSequence ||
        reportTypeInput.value !== "appointment_activity"
      ) {
        return;
      }

      renderReport(data);
    } catch (error) {
      if (sequence !== requestSequence) {
        return;
      }
      currentAppointmentReport = null;
      showError(error.message);
    } finally {
      if (
        sequence === requestSequence &&
        reportTypeInput.value === "appointment_activity"
      ) {
        setLoading(false);
        exportButton.disabled = !currentAppointmentReport;
      }
    }
  }

  function filenameFromResponse(response, fallbackFilename) {
    const disposition =
      response.headers.get("content-disposition") || "";
    const match = disposition.match(
      /filename="?([^";]+)"?/i
    );
    return match
      ? match[1]
      : fallbackFilename;
  }

  function selectedExportRequest() {
    if (reportTypeInput.value === "patient_registrations") {
      return {
        url:
          "/api/reports/patients/registrations/monthly/export.pdf?" +
          new URLSearchParams({
            year: registrationYearInput.value
          }).toString(),
        ready: Boolean(currentPatientRegistrationReport),
        fallbackFilename: "patient-registration-report.pdf"
      };
    }
    return {
      url:
        "/api/reports/appointments/daily/export.pdf?" +
        selectedRangeParams().toString(),
      ready: Boolean(currentAppointmentReport),
      fallbackFilename: "appointment-activity-report.pdf"
    };
  }

  async function exportReport() {
    if (
      reportTypeInput.value === "appointment_activity" &&
      !validateRange()
    ) {
      return;
    }

    const exportRequest = selectedExportRequest();
    if (!exportRequest.ready) {
      return;
    }

    exportButton.disabled = true;
    exportButton.textContent = "Generating PDF...";

    try {
      const response = await fetch(
        exportRequest.url
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
        filenameFromResponse(
          response,
          exportRequest.fallbackFilename
        );
      document.body.appendChild(downloadLink);
      downloadLink.click();
      downloadLink.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      showError(error.message);
    } finally {
      exportButton.disabled = !selectedExportRequest().ready;
      exportButton.textContent = "Export PDF";
    }
  }

  function selectReportType() {
    const showAppointments =
      reportTypeInput.value === "appointment_activity";
    appointmentFilters.classList.toggle(
      "d-none",
      !showAppointments
    );
    appointmentReportSection.classList.toggle(
      "d-none",
      !showAppointments
    );
    patientRegistrationFilters.classList.toggle(
      "d-none",
      showAppointments
    );
    patientRegistrationReportSection.classList.toggle(
      "d-none",
      showAppointments
    );
    hideError();

    if (showAppointments) {
      patientRequestSequence += 1;
      hidePatientRegistrationChartTooltip();
      exportButton.disabled = !currentAppointmentReport;
      if (currentAppointmentReport) {
        window.requestAnimationFrame(function () {
          renderChart(currentAppointmentReport.daily_totals);
        });
      } else {
        refreshReports();
      }
    } else {
      requestSequence += 1;
      setLoading(false);
      hideChartTooltip();
      exportButton.disabled =
        !currentPatientRegistrationReport;
      if (currentPatientRegistrationReport) {
        window.requestAnimationFrame(function () {
          renderPatientRegistrationChart(
            currentPatientRegistrationReport
              .monthly_registrations
          );
        });
      } else {
        refreshPatientRegistrations();
      }
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

  reportTypeInput.addEventListener(
    "change",
    selectReportType
  );

  registrationYearInput.addEventListener(
    "change",
    refreshPatientRegistrations
  );

  chartCanvas.addEventListener(
    "mousemove",
    showChartTooltip
  );
  chartCanvas.addEventListener(
    "mouseleave",
    hideChartTooltip
  );
  patientRegistrationChartCanvas.addEventListener(
    "mousemove",
    showPatientRegistrationChartTooltip
  );
  patientRegistrationChartCanvas.addEventListener(
    "mouseleave",
    hidePatientRegistrationChartTooltip
  );

  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(
      function () {
        if (
          currentAppointmentReport &&
          reportTypeInput.value === "appointment_activity"
        ) {
          renderChart(currentAppointmentReport.daily_totals);
        } else if (
          currentPatientRegistrationReport &&
          reportTypeInput.value === "patient_registrations"
        ) {
          renderPatientRegistrationChart(
            currentPatientRegistrationReport
              .monthly_registrations
          );
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
