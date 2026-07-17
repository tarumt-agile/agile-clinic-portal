(function () {
  "use strict";

  const root = document.getElementById("doctor-detail-root");

  if (!root) {
    console.error("Doctor detail page root was not found.");
    return;
  }

  const doctorId = root.dataset.doctorId;

  const loadingElement = document.getElementById(
    "doctor-detail-loading"
  );

  const contentElement = document.getElementById(
    "doctor-detail-content"
  );

  const errorAlert = document.getElementById(
    "doctor-detail-alert"
  );

  const successAlert = document.getElementById(
    "doctor-success-alert"
  );

  const updateAlert = document.getElementById(
    "doctor-update-alert"
  );

  const notFoundBox = document.getElementById(
    "doctor-not-found"
  );

  const editButton = document.getElementById(
    "edit-doctor-button"
  );

  const editSection = document.getElementById(
    "doctor-edit-section"
  );

  const editForm = document.getElementById(
    "edit-doctor-form"
  );

  const cancelButton = document.getElementById(
    "cancel-edit-button"
  );

  const saveButton = document.getElementById(
    "save-doctor-button"
  );

  const fullNameInput = document.getElementById(
    "edit-full-name"
  );

  const emailInput = document.getElementById(
    "edit-email"
  );

  const licenseInput = document.getElementById(
    "edit-license-number"
  );

  const specialtyInput = document.getElementById(
    "edit-specialty"
  );

  const statusInput = document.getElementById(
    "edit-status"
  );

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

  const emailPattern =
    /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  const licensePattern =
    /^MMC-\d{5}$/;

  const namePattern =
    /^[\p{L}\p{M}.'’-]+(?:\s+[\p{L}\p{M}.'’-]+)+$/u;

  let currentDoctor = null;

  function setText(elementId, value, fallback = "—") {
    const element = document.getElementById(elementId);

    if (!element) {
      return;
    }

    if (
      value === null ||
      value === undefined ||
      value === ""
    ) {
      element.textContent = fallback;
      return;
    }

    element.textContent = String(value);
  }

  function normaliseSpaces(value) {
    return String(value ?? "")
      .trim()
      .replace(/\s+/g, " ");
  }

  function hideUpdateAlert() {
    if (!updateAlert) {
      return;
    }

    updateAlert.textContent = "";
    updateAlert.classList.add("d-none");
  }

  function showUpdateAlert(message) {
    if (!updateAlert) {
      showErrorAlert(message);
      return;
    }

    updateAlert.textContent = message;
    updateAlert.classList.remove("d-none");
  }

  function focusInvalidField(input) {
    if (!input) {
      return;
    }

    input.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });

    window.setTimeout(function () {
      input.focus({
        preventScroll: true
      });
    }, 250);
  }
  
  function hideAlerts() {
    if (errorAlert) {
      errorAlert.textContent = "";
      errorAlert.classList.add("d-none");
    }

    if (successAlert) {
      successAlert.textContent = "";
      successAlert.classList.add("d-none");
    }

    hideUpdateAlert();
  }

  function showErrorAlert(message) {
    if (successAlert) {
      successAlert.classList.add("d-none");
      successAlert.textContent = "";
    }

    if (errorAlert) {
      errorAlert.textContent = message;
      errorAlert.classList.remove("d-none");
    }
  }

  function showSuccessAlert(message) {
    if (errorAlert) {
      errorAlert.classList.add("d-none");
      errorAlert.textContent = "";
    }

    if (successAlert) {
      successAlert.textContent = message;
      successAlert.classList.remove("d-none");

      successAlert.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    }
  }

  function hideLoading() {
    if (loadingElement) {
      loadingElement.classList.add("d-none");
    }
  }

  function getInitials(fullName) {
    const words = normaliseSpaces(fullName)
      .split(" ")
      .filter(Boolean);

    if (words.length === 0) {
      return "DR";
    }

    if (words.length === 1) {
      return words[0]
        .slice(0, 2)
        .toUpperCase();
    }

    return (
      words[0][0] +
      words[words.length - 1][0]
    ).toUpperCase();
  }

  function formatDate(dateValue) {
    if (!dateValue) {
      return "—";
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
      return String(dateValue);
    }

    return new Intl.DateTimeFormat("en-MY", {
      day: "2-digit",
      month: "long",
      year: "numeric"
    }).format(date);
  }

  function renderStatus(status) {
    const badge = document.getElementById(
      "doctor-status-badge"
    );

    if (!badge) {
      return;
    }

    const normalisedStatus = String(status ?? "")
      .trim()
      .toLowerCase();

    const isActive =
      normalisedStatus === "active";

    badge.textContent = isActive
      ? "Active"
      : "Inactive";

    badge.classList.remove(
      "doctor-status-active",
      "doctor-status-inactive"
    );

    badge.classList.add(
      isActive
        ? "doctor-status-active"
        : "doctor-status-inactive"
    );
  }

  function renderDoctor(doctor) {
    currentDoctor = doctor;

    setText(
      "doctor-heading-id",
      doctor.doctor_id
    );

    setText(
      "doctor-full-name",
      doctor.full_name
    );

    setText(
      "doctor-specialty-heading",
      doctor.specialty
    );

    setText(
      "doctor-email-heading",
      doctor.email
    );

    setText(
      "doctor-avatar-text",
      getInitials(doctor.full_name)
    );

    renderStatus(doctor.status);

    setText(
      "view-doctor-id",
      doctor.doctor_id
    );

    setText(
      "view-license-number",
      doctor.license_number
    );

    setText(
      "view-specialty",
      doctor.specialty
    );

    setText(
      "view-department",
      doctor.department || "Clinical Services"
    );

    setText(
      "view-doctor-status",
      doctor.status
    );

    setText(
      "view-staff-id",
      doctor.staff_id
    );

    setText(
      "view-full-name",
      doctor.full_name
    );

    setText(
      "linked-staff-id",
      doctor.staff_id
    );

    setText(
      "view-created-at",
      formatDate(doctor.created_at)
    );

    const emailLink =
      document.getElementById("view-email");

    if (emailLink) {
      emailLink.textContent =
        doctor.email || "—";

      if (doctor.email) {
        emailLink.href =
          `mailto:${doctor.email}`;
      } else {
        emailLink.removeAttribute("href");
      }
    }

    hideLoading();

    if (contentElement) {
      contentElement.classList.remove("d-none");
    }

    if (editButton) {
      editButton.classList.remove("d-none");
    }
  }

  function getErrorElement(input) {
    return document.getElementById(
      `${input.id}-error`
    );
  }

  function showFieldError(input, message) {
    const errorElement =
      getErrorElement(input);

    input.classList.add("is-invalid");
    input.classList.remove("is-valid");

    input.setAttribute(
      "aria-invalid",
      "true"
    );

    if (errorElement) {
      errorElement.textContent = message;
      errorElement.classList.add(
        "is-visible"
      );
    }
  }

  function showFieldValid(input) {
    const errorElement = getErrorElement(input);

    hideUpdateAlert();

    input.classList.remove("is-invalid");
    input.classList.add("is-valid");

    input.setAttribute("aria-invalid", "false");

    if (errorElement) {
      errorElement.textContent = "";
    }
  }

  function clearFieldState(input) {
    const errorElement =
      getErrorElement(input);

    input.classList.remove(
      "is-invalid",
      "is-valid"
    );

    input.removeAttribute(
      "aria-invalid"
    );

    if (errorElement) {
      errorElement.textContent = "";
      errorElement.classList.remove(
        "is-visible"
      );
    }
  }

  function clearAllFieldStates() {
    [
      fullNameInput,
      emailInput,
      licenseInput,
      specialtyInput,
      statusInput
    ].forEach(function (input) {
      if (input) {
        clearFieldState(input);
      }
    });
  }

  function populateEditForm() {
    if (!currentDoctor) {
      return;
    }

    fullNameInput.value =
      currentDoctor.full_name || "";

    emailInput.value =
      currentDoctor.email || "";

    licenseInput.value =
      currentDoctor.license_number || "";

    specialtyInput.value =
      currentDoctor.specialty || "";

    statusInput.value =
      currentDoctor.status || "";

    clearAllFieldStates();
  }

  function enterEditMode() {
    hideAlerts();
    populateEditForm();

    editSection.classList.remove("d-none");
    editButton.classList.add("d-none");

    editSection.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  }

  function leaveEditMode() {
    editSection.classList.add("d-none");
    editButton.classList.remove("d-none");

    clearAllFieldStates();
  }

  function validateFullName() {
    const fullName = normaliseSpaces(
      fullNameInput.value
    );

    if (fullName === "") {
      showFieldError(
        fullNameInput,
        "Doctor full name must be filled in."
      );

      return false;
    }

    const words =
      fullName.split(" ");

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
    const email =
      emailInput.value
        .trim()
        .toLowerCase();

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
      licenseInput.value
        .trim()
        .toUpperCase();

    if (licenseNumber === "") {
      showFieldError(
        licenseInput,
        "MMC registration number must be filled in."
      );

      return false;
    }

    if (
      !licenseNumber.startsWith("MMC-")
    ) {
      showFieldError(
        licenseInput,
        "Registration number must begin with MMC-."
      );

      return false;
    }

    const numberPart =
      licenseNumber.substring(4);

    if (numberPart === "") {
      showFieldError(
        licenseInput,
        "Enter exactly 5 digits after MMC-."
      );

      return false;
    }

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

    if (
      !licensePattern.test(
        licenseNumber
      )
    ) {
      showFieldError(
        licenseInput,
        "Registration number format is invalid. Use MMC-12345."
      );

      return false;
    }

    licenseInput.value =
      licenseNumber;

    showFieldValid(licenseInput);

    return true;
  }

  function validateSpecialty() {
    const specialty =
      specialtyInput.value;

    if (specialty === "") {
      showFieldError(
        specialtyInput,
        "Please select a specialty."
      );

      return false;
    }

    if (
      !allowedSpecialties.has(
        specialty
      )
    ) {
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
    const status =
      statusInput.value;

    if (status === "") {
      showFieldError(
        statusInput,
        "Please select a status."
      );

      return false;
    }

    if (
      !allowedStatuses.has(status)
    ) {
      showFieldError(
        statusInput,
        "The selected status is invalid."
      );

      return false;
    }

    showFieldValid(statusInput);

    return true;
  }

  function validateEditForm() {
    const fullNameValid =
      validateFullName();

    const emailValid =
      validateEmail();

    const licenseValid =
      validateLicenseNumber();

    const specialtyValid =
      validateSpecialty();

    const statusValid =
      validateStatus();

    return (
      fullNameValid &&
      emailValid &&
      licenseValid &&
      specialtyValid &&
      statusValid
    );
  }

  function collectUpdatePayload() {
    return {
      full_name: normaliseSpaces(
        fullNameInput.value
      ),

      email: emailInput.value
        .trim()
        .toLowerCase(),

      license_number:
        licenseInput.value
          .trim()
          .toUpperCase(),

      specialty:
        specialtyInput.value,

      status:
        statusInput.value
    };
  }

  function getBackendErrorMessage(detail) {
    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map(function (error) {
          return (
            error.msg ||
            "Invalid value."
          );
        })
        .join(" ");
    }

    return (
      "Doctor details could not be updated."
    );
  }

  function handleBackendError(
    response,
    data
  ) {
    const detail = data?.detail;

    const message =
      getBackendErrorMessage(detail);

    const lowerMessage =
      message.toLowerCase();

    if (
      response.status === 409 &&
      lowerMessage.includes("email")
    ) {
      showFieldError(
        emailInput,
        "This email address is already registered."
      );

      showUpdateAlert(
        "Please correct the highlighted email address."
      );

      focusInvalidField(emailInput);
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

      showUpdateAlert(
        "Please correct the highlighted registration number."
      );

      focusInvalidField(licenseInput);
      return;
    }

    if (Array.isArray(detail)) {
      let fieldErrorFound = false;

      detail.forEach(function (error) {
        const location =
          error.loc || [];

        const fieldName =
          location[
            location.length - 1
          ];

        switch (fieldName) {
          case "full_name":
            showFieldError(
              fullNameInput,
              error.msg ||
                "Doctor full name is invalid."
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
        showUpdateAlert(
          "Please correct the highlighted fields."
        );

        focusInvalidField(
          editForm.querySelector(".is-invalid")
        );

        return;
      }
    }

    showUpdateAlert(message);

    if (updateAlert) {
      updateAlert.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    }
  }

  async function loadDoctor() {
    if (!doctorId) {
      hideLoading();

      if (notFoundBox) {
        notFoundBox.classList.remove(
          "d-none"
        );
      }

      return;
    }

    try {
      const response = await fetch(
        `/api/staff/doctors/${encodeURIComponent(
          doctorId
        )}`
      );

      if (response.status === 404) {
        hideLoading();

        if (notFoundBox) {
          notFoundBox.classList.remove(
            "d-none"
          );
        }

        return;
      }

      if (!response.ok) {
        throw new Error(
          `Doctor request failed with status ${response.status}`
        );
      }

      const doctor =
        await response.json();

      renderDoctor(doctor);
    } catch (error) {
      console.error(
        "Unable to load doctor details:",
        error
      );

      hideLoading();

      showErrorAlert(
        "Unable to load this doctor profile."
      );
    }
  }

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

  fullNameInput.addEventListener(
    "input",
    function () {
      if (
        fullNameInput.classList.contains(
          "is-invalid"
        )
      ) {
        validateFullName();
      }
    }
  );

  emailInput.addEventListener(
    "input",
    function () {
      if (
        emailInput.classList.contains(
          "is-invalid"
        )
      ) {
        validateEmail();
      }
    }
  );

  licenseInput.addEventListener(
    "input",
    function () {
      licenseInput.value =
        licenseInput.value.toUpperCase();

      if (
        licenseInput.classList.contains(
          "is-invalid"
        )
      ) {
        validateLicenseNumber();
      }
    }
  );

  editButton.addEventListener(
    "click",
    enterEditMode
  );

  cancelButton.addEventListener(
    "click",
    leaveEditMode
  );

  editForm.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();
      hideAlerts();

      const formIsValid =
        validateEditForm();

      if (!formIsValid) {
        showUpdateAlert(
          "Please correct the highlighted fields before saving."
        );

        focusInvalidField(
          editForm.querySelector(".is-invalid")
        );

        return;
      }

      saveButton.disabled = true;
      saveButton.textContent =
        "Saving...";

      try {
        const response = await fetch(
          `/api/staff/doctors/${encodeURIComponent(
            doctorId
          )}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type":
                "application/json"
            },
            body: JSON.stringify(
              collectUpdatePayload()
            )
          }
        );

        let data = {};

        try {
          data =
            await response.json();
        } catch (jsonError) {
          data = {};
        }

        if (!response.ok) {
          handleBackendError(
            response,
            data
          );

          return;
        }

        renderDoctor(data);
        leaveEditMode();

        showSuccessAlert(
          "Doctor details were updated successfully."
        );
      } catch (error) {
        console.error(
          "Unable to update doctor:",
          error
        );

        showUpdateAlert(
          "Unable to connect to the server. Please try again."
        );

        if (updateAlert) {
          updateAlert.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
        }
      } finally {
        saveButton.disabled = false;
        saveButton.textContent =
          "Save Changes";
      }
    }
  );

  loadDoctor();
})();