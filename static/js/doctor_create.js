(function () {
  "use strict";

  const form = document.getElementById("create-doctor-form");

  if (!form) {
    console.error("Create doctor form was not found.");
    return;
  }

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");

  const fullNameInput = document.getElementById("full_name");
  const emailInput = document.getElementById("email");
  const licenseInput = document.getElementById("license_number");
  const specialtyInput = document.getElementById("specialty");
  const statusInput = document.getElementById("status");

  const confirmationModalElement =
    document.getElementById("confirmation-modal");

  const confirmationModal =
    window.bootstrap && confirmationModalElement
      ? new bootstrap.Modal(confirmationModalElement)
      : null;

  const allowedSpecialties = new Set([
    "General Medicine",
    "Family Medicine",
    "Internal Medicine",
    "Cardiology",
    "Dermatology",
    "Emergency Medicine",
    "Endocrinology",
    "Gastroenterology",
    "General Surgery",
    "Neurology",
    "Obstetrics and Gynaecology",
    "Oncology",
    "Ophthalmology",
    "Orthopaedics",
    "Otorhinolaryngology",
    "Paediatrics",
    "Psychiatry",
    "Radiology",
    "Urology"
  ]);

  const allowedStatuses = new Set([
    "active",
    "inactive"
  ]);

  /*
   * Internal clinic format:
   * MMC- followed by exactly five digits.
   *
   * Valid:   MMC-12345
   * Invalid: MMC12345
   * Invalid: MMC-1234
   * Invalid: ABC-12345
   */
  const licensePattern = /^MMC-\d{5}$/;

  /*
   * A practical email validation pattern.
   * Final email validation must still be performed by the backend.
   */
  const emailPattern =
    /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  /*
   * Allows Unicode letters, spaces, apostrophes, periods and hyphens.
   * This supports names such as:
   *
   * Tan Wei Ming
   * Nur Aisyah
   * O'Connor James
   * Siti Nur-Ain
   * Dr. Ahmad Zaki
   */
  const namePattern =
    /^[\p{L}\p{M}.'’-]+(?:\s+[\p{L}\p{M}.'’-]+)+$/u;

  function showAlert(message) {
    if (!alertBox) {
      return;
    }

    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    if (!alertBox) {
      return;
    }

    alertBox.textContent = "";
    alertBox.classList.add("d-none");
  }

  function getErrorElement(input) {
    return document.getElementById(`${input.id}_error`);
  }

  function showFieldError(input, message) {
    const errorElement = getErrorElement(input);

    input.classList.add("is-invalid");
    input.classList.remove("is-valid");
    input.setAttribute("aria-invalid", "true");

    if (errorElement) {
      errorElement.textContent = message;
      errorElement.style.display = "block";
    }
  }

  function showFieldValid(input) {
    const errorElement = getErrorElement(input);

    input.classList.remove("is-invalid");
    input.classList.add("is-valid");
    input.setAttribute("aria-invalid", "false");

    if (errorElement) {
      errorElement.textContent = "";
      errorElement.style.display = "none";
    }
  }

  function clearFieldState(input) {
    const errorElement = getErrorElement(input);

    input.classList.remove("is-invalid", "is-valid");
    input.removeAttribute("aria-invalid");

    if (errorElement) {
      errorElement.textContent = "";
      errorElement.style.display = "none";
    }
  }

  function normaliseSpaces(value) {
    return value
      .trim()
      .replace(/\s+/g, " ");
  }

  function validateFullName() {
    const fullName = normaliseSpaces(fullNameInput.value);

    if (fullName === "") {
      showFieldError(
        fullNameInput,
        "Doctor full name must be filled in."
      );

      return false;
    }

    const words = fullName.split(" ");

    if (words.length < 2) {
      showFieldError(
        fullNameInput,
        "Doctor full name must contain at least 2 words."
      );

      return false;
    }

    if (!namePattern.test(fullName)) {
      showFieldError(
        fullNameInput,
        "Full name may only contain letters, spaces, apostrophes, periods and hyphens."
      );

      return false;
    }

    if (fullName.length > 120) {
      showFieldError(
        fullNameInput,
        "Doctor full name must not exceed 120 characters."
      );

      return false;
    }

    fullNameInput.value = fullName;
    showFieldValid(fullNameInput);

    return true;
  }

  function validateEmail() {
    const email = emailInput.value.trim().toLowerCase();

    if (email === "") {
      showFieldError(
        emailInput,
        "Email address must be filled in."
      );

      return false;
    }

    if (email.length > 254) {
      showFieldError(
        emailInput,
        "Email address must not exceed 254 characters."
      );

      return false;
    }

    if (!emailPattern.test(email)) {
      showFieldError(
        emailInput,
        "Email format is invalid. Example: doctor@example.com."
      );

      return false;
    }

    emailInput.value = email;
    showFieldValid(emailInput);

    return true;
  }

  function validateLicenseNumber() {
    const licenseNumber =
      licenseInput.value.trim().toUpperCase();

    if (licenseNumber === "") {
      showFieldError(
        licenseInput,
        "MMC registration number must be filled in."
      );

      return false;
    }

    if (!licenseNumber.startsWith("MMC-")) {
      showFieldError(
        licenseInput,
        "Registration number must begin with MMC-."
      );

      return false;
    }

    const numberPart = licenseNumber.substring(4);

    if (!/^\d+$/.test(numberPart)) {
      showFieldError(
        licenseInput,
        "Only numbers are allowed after MMC-. Example: MMC-12345."
      );

      return false;
    }

    if (numberPart.length < 5) {
      showFieldError(
        licenseInput,
        "Registration number must contain exactly 5 digits after MMC-."
      );

      return false;
    }

    if (numberPart.length > 5) {
      showFieldError(
        licenseInput,
        "Registration number cannot contain more than 5 digits after MMC-."
      );

      return false;
    }

    if (!licensePattern.test(licenseNumber)) {
      showFieldError(
        licenseInput,
        "Registration number format is invalid. Use MMC-12345."
      );

      return false;
    }

    licenseInput.value = licenseNumber;
    showFieldValid(licenseInput);

    return true;
  }

  function validateSpecialty() {
    const specialty = specialtyInput.value;

    if (specialty === "") {
      showFieldError(
        specialtyInput,
        "Please select a specialty."
      );

      return false;
    }

    if (!allowedSpecialties.has(specialty)) {
      showFieldError(
        specialtyInput,
        "The selected specialty is invalid."
      );

      return false;
    }

    showFieldValid(specialtyInput);

    return true;
  }

  function validateStatus() {
    const status = statusInput.value;

    if (status === "") {
      showFieldError(
        statusInput,
        "Please select a status."
      );

      return false;
    }

    if (!allowedStatuses.has(status)) {
      showFieldError(
        statusInput,
        "The selected status is invalid."
      );

      return false;
    }

    showFieldValid(statusInput);

    return true;
  }

  function validateForm() {
    const fullNameValid = validateFullName();
    const emailValid = validateEmail();
    const licenseValid = validateLicenseNumber();
    const specialtyValid = validateSpecialty();
    const statusValid = validateStatus();

    return (
      fullNameValid &&
      emailValid &&
      licenseValid &&
      specialtyValid &&
      statusValid
    );
  }

  function collectPayload() {
    return {
      full_name: normaliseSpaces(fullNameInput.value),
      email: emailInput.value.trim().toLowerCase(),
      license_number:
        licenseInput.value.trim().toUpperCase(),
      specialty: specialtyInput.value,

      /*
       * The department field was removed from the page.
       * This fixed value is sent because the current backend
       * DoctorRegister schema still requires department.
       */
      department: "Clinical Services",

      status: statusInput.value
    };
  }

  function showConfirmation(doctor) {
    document.getElementById(
      "confirm-doctor-id"
    ).textContent = doctor.doctor_id || "-";

    document.getElementById(
      "confirm-staff-id"
    ).textContent = doctor.staff_id || "-";

    document.getElementById(
      "confirm-full-name"
    ).textContent = doctor.full_name || "-";

    document.getElementById(
      "confirm-specialty"
    ).textContent = doctor.specialty || "-";

    if (confirmationModal) {
      confirmationModal.show();
    } else {
      window.alert("Doctor created successfully.");
    }
  }

  function getBackendErrorMessage(detail) {
    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map(function (error) {
          return error.msg || "Invalid value.";
        })
        .join(" ");
    }

    return "Doctor could not be created.";
  }

  function handleBackendError(response, data) {
    const detail = data?.detail;
    const message = getBackendErrorMessage(detail);
    const lowerMessage = message.toLowerCase();

    /*
     * HTTP 409 is normally used for duplicate records.
     * The existing service already checks duplicate email
     * and duplicate licence number.
     */
    if (
      response.status === 409 &&
      lowerMessage.includes("email")
    ) {
      showFieldError(
        emailInput,
        "This email address is already registered."
      );

      emailInput.focus();
      return;
    }

    if (
      response.status === 409 &&
      (
        lowerMessage.includes("license") ||
        lowerMessage.includes("licence") ||
        lowerMessage.includes("registration")
      )
    ) {
      showFieldError(
        licenseInput,
        "This MMC registration number is already registered."
      );

      licenseInput.focus();
      return;
    }

    /*
     * Handle FastAPI/Pydantic validation errors.
     */
    if (Array.isArray(detail)) {
      let fieldErrorFound = false;

      detail.forEach(function (error) {
        const location = error.loc || [];
        const fieldName =
          location[location.length - 1];

        switch (fieldName) {
          case "full_name":
            showFieldError(
              fullNameInput,
              error.msg || "Doctor full name is invalid."
            );
            fieldErrorFound = true;
            break;

          case "email":
            showFieldError(
              emailInput,
              "Email format is invalid."
            );
            fieldErrorFound = true;
            break;

          case "license_number":
            showFieldError(
              licenseInput,
              error.msg ||
                "MMC registration number is invalid."
            );
            fieldErrorFound = true;
            break;

          case "specialty":
            showFieldError(
              specialtyInput,
              "The selected specialty is invalid."
            );
            fieldErrorFound = true;
            break;

          case "status":
            showFieldError(
              statusInput,
              "The selected status is invalid."
            );
            fieldErrorFound = true;
            break;

          default:
            break;
        }
      });

      if (fieldErrorFound) {
        showAlert(
          "Please correct the highlighted fields."
        );

        return;
      }
    }

    showAlert(message);
  }

  /*
   * Validate each field after the user leaves it.
   */
  fullNameInput.addEventListener(
    "blur",
    validateFullName
  );

  emailInput.addEventListener(
    "blur",
    validateEmail
  );

  licenseInput.addEventListener(
    "blur",
    validateLicenseNumber
  );

  specialtyInput.addEventListener(
    "change",
    validateSpecialty
  );

  statusInput.addEventListener(
    "change",
    validateStatus
  );

  /*
   * Remove an existing error once the user starts correcting it.
   */
  fullNameInput.addEventListener("input", function () {
    if (fullNameInput.classList.contains("is-invalid")) {
      validateFullName();
    }
  });

  emailInput.addEventListener("input", function () {
    if (emailInput.classList.contains("is-invalid")) {
      validateEmail();
    }
  });

  licenseInput.addEventListener("input", function () {
    /*
     * Automatically convert the registration number
     * to uppercase.
     */
    licenseInput.value =
      licenseInput.value.toUpperCase();

    if (licenseInput.classList.contains("is-invalid")) {
      validateLicenseNumber();
    }
  });

  form.addEventListener(
    "reset",
    function () {
      hideAlert();

      [
        fullNameInput,
        emailInput,
        licenseInput,
        specialtyInput,
        statusInput
      ].forEach(clearFieldState);
    }
  );

  form.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();
      hideAlert();

      const formIsValid = validateForm();

      if (!formIsValid) {
        showAlert(
          "Please correct the highlighted fields before submitting."
        );

        const firstInvalidField =
          form.querySelector(".is-invalid");

        if (firstInvalidField) {
          firstInvalidField.focus();
        }

        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Creating Doctor...";

      try {
        const response = await fetch(
          "/api/staff/admin/doctors",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify(collectPayload())
          }
        );

        let data;

        try {
          data = await response.json();
        } catch (jsonError) {
          data = {};
        }

        if (!response.ok) {
          handleBackendError(response, data);
          return;
        }

        showConfirmation(data);

        form.reset();

        [
          fullNameInput,
          emailInput,
          licenseInput,
          specialtyInput,
          statusInput
        ].forEach(clearFieldState);
      } catch (error) {
        console.error(
          "Create doctor request failed:",
          error
        );

        showAlert(
          "Unable to connect to the server. Please try again."
        );
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Create Doctor";
      }
    }
  );
})();