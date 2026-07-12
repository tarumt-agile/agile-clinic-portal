(function () {
  "use strict";

  const form = document.getElementById("appointment-form");
  if (!form) return;

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");
  const dateInput = document.getElementById("appointment_date");
  const patientIdInput = document.getElementById("patient_id");
  const patientFeedback = document.getElementById("patient-lookup-feedback");
  const specialtySelect = document.getElementById("specialty");
  const doctorSelect = document.getElementById("doctor_id");
  const slotGrid = document.getElementById("slot-grid");
  const slotError = document.getElementById("slot-error");
  const startTimeInput = document.getElementById("start_time");
  const confirmationModalEl = document.getElementById("confirmation-modal");
  const confirmationModal = window.bootstrap ? new bootstrap.Modal(confirmationModalEl) : null;

  let allDoctors = [];

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  function clearFieldErrors() {
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
    slotError.classList.remove("d-block");
  }

  function fieldNameFromLoc(loc) {
    if (!Array.isArray(loc)) return null;
    return loc[loc.length - 1];
  }

  function formatSpecialty(specialty) {
    if (!specialty) return "";
    return specialty
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  // Pydantic 422s have a list `detail` of field errors; service-layer 422s (invalid
  // slot) have a plain string `detail`. Only the former can be mapped onto a field.
  function applyValidationErrors(errorBody) {
    if (!Array.isArray(errorBody.detail)) return false;
    let hadFieldError = false;
    for (const err of errorBody.detail) {
      const fieldName = fieldNameFromLoc(err.loc);
      const field = fieldName && form.elements.namedItem(fieldName);
      if (field) {
        field.classList.add("is-invalid");
        const feedback = field.parentElement.querySelector(".invalid-feedback");
        if (feedback && err.msg) feedback.textContent = err.msg;
        hadFieldError = true;
      }
    }
    return hadFieldError;
  }

  function collectPayload() {
    const data = new FormData(form);
    return {
      patient_id: data.get("patient_id")?.trim(),
      doctor_id: data.get("doctor_id"),
      appointment_date: data.get("appointment_date"),
      start_time: data.get("start_time"),
      reason: data.get("reason")?.trim(),
    };
  }

  async function loadDoctors() {
    doctorSelect.innerHTML = '<option value="" selected disabled>Loading doctors...</option>';
    try {
      const response = await fetch("/api/staff");
      if (!response.ok) throw new Error("Request failed");
      const staff = await response.json();
      allDoctors = staff.filter((s) => s.role === "doctor" && s.is_active);

      const specialties = [...new Set(allDoctors.map((d) => d.specialty))].sort();
      specialtySelect.innerHTML =
        '<option value="">All specialties</option>' +
        specialties
          .map((s) => `<option value="${s}">${formatSpecialty(s)}</option>`)
          .join("");

      renderDoctorOptions();
    } catch (err) {
      doctorSelect.innerHTML = '<option value="" selected disabled>Unable to load doctors</option>';
    }
  }

  function renderDoctorOptions() {
    const specialty = specialtySelect.value;
    const doctors = specialty
      ? allDoctors.filter((d) => d.specialty === specialty)
      : allDoctors;

    if (doctors.length === 0) {
      doctorSelect.innerHTML = '<option value="" selected disabled>No doctors available</option>';
      return;
    }

    doctorSelect.innerHTML =
      '<option value="" selected disabled selected>Choose...</option>' +
      doctors
        .map(
          (d) =>
            `<option value="${d.staff_id}">${d.full_name} (${formatSpecialty(d.specialty)})</option>`
        )
        .join("");
    doctorSelect.value = "";
    clearSlots();
  }

  function clearSlots() {
    startTimeInput.value = "";
    slotGrid.innerHTML =
      '<p class="text-muted mb-0" id="slot-placeholder">Select a doctor and date to see available time slots.</p>';
  }

  async function loadSlots() {
    const doctorId = doctorSelect.value;
    const date = dateInput.value;
    if (!doctorId || !date) {
      clearSlots();
      return;
    }

    startTimeInput.value = "";
    slotGrid.innerHTML = '<p class="text-muted mb-0">Loading slots...</p>';

    try {
      const response = await fetch(
        `/api/appointments/slots?doctor_id=${encodeURIComponent(doctorId)}&date=${date}`
      );
      const body = await response.json();

      if (!response.ok) {
        slotGrid.innerHTML = "";
        showAlert(body.detail || "Unable to load available time slots.");
        return;
      }

      renderSlots(body.slots);
    } catch (err) {
      slotGrid.innerHTML = "";
      showAlert("Unable to load available time slots. Please try again.");
    }
  }

  function renderSlots(slots) {
    slotGrid.innerHTML = "";
    slots.forEach((slot) => {
      const label = slot.start_time.slice(0, 5);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.dataset.time = slot.start_time;
      btn.className = slot.available
        ? "btn btn-outline-primary btn-sm slot-btn"
        : "btn btn-outline-secondary btn-sm slot-btn disabled";
      btn.disabled = !slot.available;
      if (slot.available) {
        btn.addEventListener("click", () => selectSlot(btn));
      }
      slotGrid.appendChild(btn);
    });
  }

  function selectSlot(selectedBtn) {
    slotGrid.querySelectorAll(".slot-btn").forEach((btn) => {
      btn.classList.remove("btn-primary", "text-white");
      if (!btn.disabled) btn.classList.add("btn-outline-primary");
    });
    selectedBtn.classList.remove("btn-outline-primary");
    selectedBtn.classList.add("btn-primary", "text-white");
    startTimeInput.value = selectedBtn.dataset.time;
    slotError.classList.remove("d-block");
  }

  async function lookupPatient() {
    const patientId = patientIdInput.value.trim();
    patientFeedback.textContent = "";
    patientFeedback.classList.remove("text-danger", "text-success");
    if (!patientId) return;

    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(patientId)}`);
      if (response.status === 404) {
        patientFeedback.textContent = "No patient found with this ID.";
        patientFeedback.classList.add("text-danger");
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      const patient = await response.json();
      patientFeedback.textContent = `✓ ${patient.full_name}`;
      patientFeedback.classList.add("text-success");
    } catch (err) {
      patientFeedback.textContent = "Unable to verify patient ID right now.";
      patientFeedback.classList.add("text-danger");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    hideAlert();
    clearFieldErrors();

    const slotMissing = !startTimeInput.value;
    if (!form.checkValidity() || slotMissing) {
      form.classList.add("was-validated");
      if (slotMissing) slotError.classList.add("d-block");
      return;
    }

    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/appointments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload()),
      });

      if (response.status === 201) {
        const appointment = await response.json();
        showConfirmation(appointment);
        form.reset();
        form.classList.remove("was-validated");
        patientFeedback.textContent = "";
        clearSlots();
        return;
      }

      const body = await response.json().catch(() => ({}));

      if (response.status === 404) {
        showAlert(body.detail || "This appointment could not be booked.");
        return;
      }

      if (response.status === 409) {
        showAlert(body.detail || "That slot was just taken. Please pick another.");
        loadSlots(); // refresh - the slot we picked is no longer free
        return;
      }

      if (response.status === 422) {
        if (!applyValidationErrors(body)) {
          showAlert(typeof body.detail === "string" ? body.detail : "Please check the form for errors.");
        }
        return;
      }

      showAlert("Something went wrong while booking the appointment. Please try again.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function showConfirmation(appointment) {
    document.getElementById("confirm-reference").textContent = appointment.reference_number;
    document.getElementById("confirm-patient").textContent =
      `${appointment.patient_name} (${appointment.patient_id})`;
    document.getElementById("confirm-doctor").textContent =
      `${appointment.doctor_name} (${appointment.doctor_id})`;
    document.getElementById("confirm-datetime").textContent =
      `${appointment.appointment_date} ${appointment.start_time.slice(0, 5)}`;
    if (confirmationModal) {
      confirmationModal.show();
    } else {
      window.alert(`Appointment booked: ${appointment.reference_number}`);
    }
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

  dateInput.min = todayLocalISODate();

  specialtySelect.addEventListener("change", renderDoctorOptions);
  doctorSelect.addEventListener("change", loadSlots);
  dateInput.addEventListener("change", loadSlots);
  patientIdInput.addEventListener("blur", lookupPatient);
  form.addEventListener("submit", handleSubmit);
  loadDoctors();
})();
