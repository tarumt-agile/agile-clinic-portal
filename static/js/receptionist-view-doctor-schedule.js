(function () {
  "use strict";

  const tableBody = document.getElementById("doctor-schedule-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("doctor-schedule-heading");
  const alertBox = document.getElementById("doctor-schedule-alert");
  const doctorFilter = document.getElementById("doctor-filter");

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

  async function loadDoctors() {
    try {
      const response = await fetch("/api/staff/doctor");
      if (!response.ok) throw new Error("Request failed");
      const doctors = await response.json();
      const active = doctors.filter((d) => d.status === "active");

      if (active.length === 0) {
        doctorFilter.innerHTML = '<option value="" selected disabled>No doctors available</option>';
        tableBody.innerHTML =
          '<tr><td colspan="4" class="text-center text-muted py-4">No doctors available.</td></tr>';
        return;
      }

      doctorFilter.innerHTML = active
        .map((d) => `<option value="${escapeHtml(d.staff_id)}">${escapeHtml(d.full_name)}</option>`)
        .join("");

      loadSchedule(doctorFilter.value);
    } catch (err) {
      doctorFilter.innerHTML = '<option value="" selected disabled>Unable to load doctors</option>';
      tableBody.innerHTML = "";
      showAlert("Unable to load the doctor list. Please try again.");
    }
  }

  async function loadSchedule(doctorId) {
    if (!doctorId) return;
    hideAlert();
    tableBody.innerHTML =
      '<tr><td colspan="4" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch(
        `/api/appointments/schedule/by-doctor?doctor_id=${encodeURIComponent(doctorId)}&date=${today}`
      );
      const body = await response.json();

      if (!response.ok) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "Unable to load this doctor's schedule.");
        return;
      }

      heading.textContent = `${body.doctor_name}'s Appointments Today`;
      renderTable(body.appointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load the schedule. Please try again.");
    }
  }

  function renderTable(appointments) {
    if (appointments.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="4" class="text-center text-muted py-4">No appointments today.</td></tr>';
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

  doctorFilter.addEventListener("change", () => loadSchedule(doctorFilter.value));
  loadDoctors();
})();
