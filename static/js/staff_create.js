(function () {
  "use strict";

  const form = document.getElementById("create-staff-form");
  if (!form) return;

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");
  const fullNameInput = document.getElementById("full_name");
  const emailInput = document.getElementById("email");
  const roleInput = document.getElementById("role");
  const doctorFields = document.getElementById("doctor-fields");
  const licenseInput = document.getElementById("license_number");
  const specialtyInput = document.getElementById("specialty");
  const statusInput = document.getElementById("status");

  const modalElement = document.getElementById("confirmation-modal");
  const confirmationModal = window.bootstrap && modalElement
    ? new bootstrap.Modal(modalElement) : null;

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const namePattern = /^[\p{L}\p{M}.'’-]+(?:\s+[\p{L}\p{M}.'’-]+)+$/u;
  const licensePattern = /^MMC-\d{5}$/;

  function normaliseSpaces(value) {
    return value.trim().replace(/\s+/g, " ");
  }

  function errorElement(input) {
    return document.getElementById(input.id + "_error");
  }

  function showError(input, message) {
    input.classList.add("is-invalid");
    input.classList.remove("is-valid");
    input.setAttribute("aria-invalid", "true");
    const element = errorElement(input);
    if (element) { element.textContent = message; element.style.display = "block"; }
  }

  function showValid(input) {
    input.classList.remove("is-invalid");
    input.classList.add("is-valid");
    input.setAttribute("aria-invalid", "false");
    const element = errorElement(input);
    if (element) { element.textContent = ""; element.style.display = "none"; }
  }

  function clearState(input) {
    input.classList.remove("is-invalid", "is-valid");
    input.removeAttribute("aria-invalid");
    const element = errorElement(input);
    if (element) { element.textContent = ""; element.style.display = "none"; }
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.textContent = "";
    alertBox.classList.add("d-none");
  }

  function isDoctor() { return roleInput.value === "doctor"; }

  function toggleDoctorFields() {
    doctorFields.classList.toggle("d-none", !isDoctor());
    [licenseInput, specialtyInput, statusInput].forEach(function (input) {
      input.disabled = !isDoctor();
      if (!isDoctor()) clearState(input);
    });
  }

  function validateName() {
    const value = normaliseSpaces(fullNameInput.value);
    if (!value) { showError(fullNameInput, "Full name must be filled in."); return false; }
    if (value.split(" ").length < 2) { showError(fullNameInput, "Full name must contain at least 2 words."); return false; }
    if (!namePattern.test(value)) { showError(fullNameInput, "Full name may only contain letters, spaces, apostrophes, periods and hyphens."); return false; }
    fullNameInput.value = value;
    showValid(fullNameInput);
    return true;
  }

  function validateEmail() {
    const value = emailInput.value.trim().toLowerCase();
    if (!value) { showError(emailInput, "Email address must be filled in."); return false; }
    if (!emailPattern.test(value)) { showError(emailInput, "Email format is invalid. Example: staff@example.com."); return false; }
    emailInput.value = value;
    showValid(emailInput);
    return true;
  }

  function validateRole() {
    if (!["doctor", "nurse", "admin"].includes(roleInput.value)) {
      showError(roleInput, "Please select a staff role."); return false;
    }
    showValid(roleInput); return true;
  }

  function validateDoctorFields() {
    if (!isDoctor()) return true;
    let valid = true;
    const license = licenseInput.value.trim().toUpperCase();
    if (!licensePattern.test(license)) { showError(licenseInput, "Registration number must use the format MMC-12345."); valid = false; }
    else { licenseInput.value = license; showValid(licenseInput); }
    if (!specialtyInput.value) { showError(specialtyInput, "Please select a specialty."); valid = false; }
    else showValid(specialtyInput);
    if (!["active", "inactive"].includes(statusInput.value)) { showError(statusInput, "Please select a status."); valid = false; }
    else showValid(statusInput);
    return valid;
  }

  function payload() {
    const data = {
      full_name: normaliseSpaces(fullNameInput.value),
      email: emailInput.value.trim().toLowerCase(),
      role: roleInput.value
    };
    if (isDoctor()) {
      data.license_number = licenseInput.value.trim().toUpperCase();
      data.specialty = specialtyInput.value;
      data.status = statusInput.value;
    }
    return data;
  }

  function backendMessage(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map(e => e.msg || "Invalid value.").join(" ");
    return "Staff account could not be created.";
  }

  roleInput.addEventListener("change", function () { toggleDoctorFields(); validateRole(); });
  fullNameInput.addEventListener("blur", validateName);
  emailInput.addEventListener("blur", validateEmail);
  licenseInput.addEventListener("input", function () { licenseInput.value = licenseInput.value.toUpperCase(); });

  // Do not validate and trim the name on every key press. This is what previously removed spaces.
  fullNameInput.addEventListener("input", function () { if (fullNameInput.classList.contains("is-invalid")) clearState(fullNameInput); });
  emailInput.addEventListener("input", function () { if (emailInput.classList.contains("is-invalid")) clearState(emailInput); });

  form.addEventListener("reset", function () {
    hideAlert();
    setTimeout(function () {
      [fullNameInput, emailInput, roleInput, licenseInput, specialtyInput, statusInput].forEach(clearState);
      toggleDoctorFields();
    }, 0);
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    hideAlert();
    const valid = validateName() & validateEmail() & validateRole() & validateDoctorFields();
    if (!valid) {
      showAlert("Please correct the highlighted fields before submitting.");
      form.querySelector(".is-invalid")?.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Creating Staff...";
    try {
      const response = await fetch("/api/staff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload())
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if (!response.ok) {
        const message = backendMessage(data.detail);
        if (response.status === 409 && message.toLowerCase().includes("email")) {
          showError(emailInput, "This email address is already registered.");
          emailInput.focus();
        } else if (response.status === 409 && /license|licence|registration/i.test(message)) {
          showError(licenseInput, "This MMC registration number is already registered.");
          licenseInput.focus();
        } else showAlert(message);
        return;
      }
      document.getElementById("confirm-staff-id").textContent = data.staff_id || "-";
      document.getElementById("confirm-full-name").textContent = data.full_name || "-";
      document.getElementById("confirm-role").textContent = roleInput.options[roleInput.selectedIndex].text;
      confirmationModal ? confirmationModal.show() : window.alert("Staff created successfully.");
      form.reset();
    } catch (error) {
      showAlert("Unable to connect to the server. Please try again.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Create Staff";
    }
  });

  toggleDoctorFields();
})();
