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

  function detailMessage(body, fallback) {
    return typeof body.detail === "string" ? body.detail : fallback;
  }

  // Reformats digits-only input into dash-separated groups as the user types,
  // e.g. groupSizes [6, 2, 4] turns "900520101234" into "900520-10-1234". Skips
  // reformatting if the field has any letters in it - the IC field also accepts
  // passport numbers, which aren't digits-only and shouldn't be touched.
  function autoDash(input, groupSizes) {
    input.addEventListener("input", () => {
      if (/[a-zA-Z]/.test(input.value)) {
        // Passport number - undo any dash inserted before the first letter showed up.
        input.value = input.value.replace(/-/g, "");
        return;
      }
      const digits = input.value.replace(/\D/g, "");
      const groups = [];
      let start = 0;
      for (const size of groupSizes) {
        if (start >= digits.length) break;
        groups.push(digits.slice(start, start + size));
        start += size;
      }
      input.value = groups.join("-");
    });
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
        showAlert(detailMessage(body, "This account has been deactivated."));
      } else if (response.status === 401) {
        showAlert(detailMessage(body, "Invalid email or password."));
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
          ic_or_passport: data.get("ic_or_passport")?.trim(),
          phone_number: data.get("phone_number")?.trim(),
        }),
      });

      if (response.ok) {
        window.location.href = "/patients/dashboard";
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(detailMessage(body, "Invalid IC/passport number or phone number."));
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

  const icInput = document.getElementById("patient-ic");
  const phoneInput = document.getElementById("patient-phone");
  if (icInput) autoDash(icInput, [6, 2, 4]);
  if (phoneInput) autoDash(phoneInput, [3, 7]);
})();
