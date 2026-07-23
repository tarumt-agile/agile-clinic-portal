(function () {
  "use strict";

  const alertBox = document.getElementById("form-alert");

  const REDIRECT_BY_ROLE = {
    admin: "/staff",
    doctor: "/appointments/schedule",
    nurse: "/patients",
    receptionist: "/patients",
  };

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  async function handleStaffSubmit(event) {
    event.preventDefault();
    hideAlert();
    const form = event.target;
    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
    const submitBtn = document.getElementById("staff-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: data.get("email")?.trim(),
          password: data.get("password"),
        }),
      });

      if (response.ok) {
        const body = await response.json();
        window.location.href = REDIRECT_BY_ROLE[body.role] || "/patients";
        return;
      }

      const body = await response.json().catch(() => ({}));
      if (response.status === 403) {
        showAlert(body.detail || "This account has been deactivated.");
      } else if (response.status === 401) {
        showAlert(body.detail || "Invalid email or password.");
      } else {
        showAlert("Something went wrong while logging in. Please try again.");
      }
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function handlePatientSubmit(event) {
    event.preventDefault();
    hideAlert();
    const form = event.target;
    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
    const submitBtn = document.getElementById("patient-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/patient-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: data.get("patient_id")?.trim(),
          ic_or_passport: data.get("ic_or_passport")?.trim(),
        }),
      });

      if (response.ok) {
        window.location.href = "/patients/dashboard";
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(body.detail || "Invalid patient ID or IC/passport number.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  const staffForm = document.getElementById("staff-login-form");
  const patientForm = document.getElementById("patient-login-form");
  if (staffForm) staffForm.addEventListener("submit", handleStaffSubmit);
  if (patientForm) patientForm.addEventListener("submit", handlePatientSubmit);
})();
