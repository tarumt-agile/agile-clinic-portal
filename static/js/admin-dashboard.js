(function () {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  async function loadStats() {
    try {
      const response = await fetch("/api/dashboard/admin-stats");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load dashboard stats.");
      }

      byId("stat-total-patients").textContent = data.total_patients;
      byId("stat-total-staff").textContent = data.total_staff;
      byId("stat-active-doctors").textContent = data.active_doctors;
      byId("stat-appointments-today").textContent = data.appointments_today;
    } catch (error) {
      const alertEl = byId("dashboard-alert");
      alertEl.textContent = error.message;
      alertEl.classList.remove("d-none");
    }
  }

  loadStats();
})();
