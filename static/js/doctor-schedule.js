(function () {
  "use strict";

  const tableBody = document.getElementById("schedule-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("schedule-heading");
  const dateInput = document.getElementById("schedule-date");
  const alertBox = document.getElementById("schedule-alert");

  const STATUS_BADGE = {
    scheduled: "text-bg-primary",
    cancelled: "text-bg-secondary",
  };

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  async function loadSchedule(dateValue) {
    hideAlert();
    tableBody.innerHTML =
      '<tr><td colspan="4" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch(`/api/appointments/schedule?date=${dateValue}`);
      const body = await response.json();

      if (response.status === 422) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "Please choose today or a future date.");
        return;
      }

      if (response.status === 404) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "No doctor account found.");
        return;
      }

      if (!response.ok) throw new Error("Request failed");

      heading.textContent = `${body.doctor_name}'s Schedule`;
      renderTable(body.appointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load the schedule. Please try again.");
    }
  }

  function renderTable(appointments) {
    if (appointments.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="4" class="text-center text-muted py-4">No appointments for this date.</td></tr>';
      return;
    }

    tableBody.innerHTML = appointments
      .map((a) => {
        const badgeClass = STATUS_BADGE[a.status] || "text-bg-light";
        return `
      <tr>
        <td>${escapeHtml(a.start_time.slice(0, 5))} - ${escapeHtml(a.end_time.slice(0, 5))}</td>
        <td>${escapeHtml(a.patient_name)} (${escapeHtml(a.patient_id)})</td>
        <td>${escapeHtml(a.reason)}</td>
        <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(a.status)}</span></td>
      </tr>`;
      })
      .join("");
  }

  // Local date, not UTC - toISOString() converts to UTC and can be a day off from
  // the server's dt.date.today() (which uses local time), especially near midnight.
  function todayLocalISODate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  const today = todayLocalISODate();
  dateInput.min = today;
  dateInput.value = today;

  dateInput.addEventListener("change", () => loadSchedule(dateInput.value));
  loadSchedule(today);
})();
