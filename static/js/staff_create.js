(function () {
  "use strict";

  const form = document.getElementById(
    "create-staff-form"
  );

  if (!form) {
    console.error("Create staff form was not found.");
    return;
  }

  const alertBox = document.getElementById(
    "staff-form-alert"
  );

  const submitButton = document.getElementById(
    "submit-staff-button"
  );

  const fullNameInput = document.getElementById(
    "full_name"
  );

  const emailInput = document.getElementById(
    "email"
  );

  const roleInput = document.getElementById(
    "role"
  );

  const confirmationModalElement =
    document.getElementById(
      "staff-confirmation-modal"
    );

  const confirmationModal =
    window.bootstrap && confirmationModalElement
      ? window.bootstrap.Modal.getOrCreateInstance(
          confirmationModalElement
        )
      : null;

  const fields = [
    fullNameInput,
    emailInput,
    roleInput
  ];

  const allowedRoles = new Set([
    "admin",
    "nurse",
    "receptionist",
    "pharmacist"
  ]);

  /*
   * Practical email validation.
   * Backend validation is still required.
   */
  const emailPattern =
    /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  /*
   * Allows Unicode letters, accents, spaces,
   * apostrophes, periods and hyphens.
   *
   * Examples:
   * Tan Wei Ming
   * Nur Aisyah
   * O'Connor James
   * Siti Nur-Ain
   * Ahmad bin Ali
   */
  const namePattern = /^[\p{L}\p{M}.'’ -]+$/u;

  function normaliseSpaces(value) {
    return value
      .trim()
      .replace(/\s+/g, " ");
  }

  function getErrorElement(input) {
    return document.getElementById(
      `${input.id}_error`
    );
  }

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

  function showFieldError(input, message) {
    const errorElement = getErrorElement(input);

    input.classList.remove("is-valid");
    input.classList.add("is-invalid");
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

    input.classList.remove(
      "is-invalid",
      "is-valid"
    );

    input.removeAttribute("aria-invalid");

    if (errorElement) {
      errorElement.textContent = "";
      errorElement.style.display = "none";
    }
  }

  function focusFirstInvalidField() {
    const firstInvalidField =
      form.querySelector(".is-invalid");

    if (!firstInvalidField) {
      return;
    }

    firstInvalidField.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });

    window.setTimeout(function () {
      firstInvalidField.focus({
        preventScroll: true
      });
    }, 250);
  }

  function validateFullName() {
    const fullName = normaliseSpaces(
      fullNameInput.value
    );

    fullNameInput.value = fullName;

    if (fullName === "") {
      showFieldError(
        fullNameInput,
        "Staff full name must be filled in."
      );

      return false;
    }

    const words = fullName
      .split(" ")
      .filter(Boolean);

    if (words.length < 2) {
      showFieldError(
        fullNameInput,
        "Staff full name must contain at least 2 words."
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
        "Staff full name must not exceed 120 characters."
      );

      return false;
    }

    showFieldValid(fullNameInput);
    return true;
  }

  function validateEmail() {
    const email = emailInput.value
      .trim()
      .toLowerCase();

    emailInput.value = email;

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
        "Email format is invalid. Example: staff@example.com."
      );

      return false;
    }

    showFieldValid(emailInput);
    return true;
  }

  function validateRole() {
    const role = roleInput.value;

    if (role === "") {
      showFieldError(
        roleInput,
        "Please select a staff role."
      );

      return false;
    }

    if (!allowedRoles.has(role)) {
      showFieldError(
        roleInput,
        "The selected staff role is invalid."
      );

      return false;
    }

    showFieldValid(roleInput);
    return true;
  }

  function validateForm() {
    const fullNameValid = validateFullName();
    const emailValid = validateEmail();
    const roleValid = validateRole();

    return (
      fullNameValid &&
      emailValid &&
      roleValid
    );
  }

  function collectPayload() {
    return {
      full_name: normaliseSpaces(
        fullNameInput.value
      ),
      email: emailInput.value
        .trim()
        .toLowerCase(),
      role: roleInput.value
    };
  }

  function formatRole(role) {
    const labels = {
      admin: "Administrator",
      nurse: "Nurse",
      receptionist: "Receptionist",
      pharmacist: "Pharmacist"
    };

    return labels[role] || role || "—";
  }

  function showConfirmation(staff) {
    const staffIdElement =
      document.getElementById(
        "confirmation-staff-id"
      );

    const fullNameElement =
      document.getElementById(
        "confirmation-full-name"
      );

    const emailElement =
      document.getElementById(
        "confirmation-email"
      );

    const roleElement =
      document.getElementById(
        "confirmation-role"
      );

    if (staffIdElement) {
      staffIdElement.textContent =
        staff.staff_id || "—";
    }

    if (fullNameElement) {
      fullNameElement.textContent =
        staff.full_name || "—";
    }

    if (emailElement) {
      emailElement.textContent =
        staff.email || "—";
    }

    if (roleElement) {
      roleElement.textContent =
        formatRole(staff.role);
    }

    if (confirmationModal) {
      confirmationModal.show();
    } else {
      window.alert(
        "Staff account created successfully."
      );
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

    return "Staff account could not be created.";
  }

  function cleanBackendMessage(message) {
    return String(message || "Invalid value.")
      .replace(/^Value error,\s*/i, "");
  }

  function handleBackendError(response, data) {
    const detail = data?.detail;
    const message =
      getBackendErrorMessage(detail);

    const lowerMessage =
      message.toLowerCase();

    /*
     * Duplicate email returned by the service.
     */
    if (
      response.status === 409 &&
      lowerMessage.includes("email")
    ) {
      showFieldError(
        emailInput,
        "This email address is already registered."
      );

      showAlert(
        "Please use a different email address."
      );

      focusFirstInvalidField();
      return;
    }

    /*
     * FastAPI and Pydantic field errors.
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
              cleanBackendMessage(
                error.msg ||
                "Staff full name is invalid."
              )
            );

            fieldErrorFound = true;
            break;

          case "email":
            showFieldError(
              emailInput,
              cleanBackendMessage(
                error.msg ||
                "Email address is invalid."
              )
            );

            fieldErrorFound = true;
            break;

          case "role":
            showFieldError(
              roleInput,
              cleanBackendMessage(
                error.msg ||
                "The selected staff role is invalid."
              )
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

        focusFirstInvalidField();
        return;
      }
    }

    showAlert(message);

    if (alertBox) {
      alertBox.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    }
  }

  /*
   * Validate after leaving each text field.
   */
  fullNameInput.addEventListener(
    "blur",
    validateFullName
  );

  emailInput.addEventListener(
    "blur",
    validateEmail
  );

  roleInput.addEventListener(
    "change",
    validateRole
  );

  /*
   * Dynamically revalidate fields while the user
   * corrects an existing error.
   */
  fullNameInput.addEventListener(
    "input",
    function () {
      hideAlert();

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
      hideAlert();

      if (
        emailInput.classList.contains(
          "is-invalid"
        )
      ) {
        validateEmail();
      }
    }
  );

  roleInput.addEventListener(
    "change",
    function () {
      hideAlert();

      if (
        roleInput.classList.contains(
          "is-invalid"
        )
      ) {
        validateRole();
      }
    }
  );

  form.addEventListener(
    "reset",
    function () {
      window.setTimeout(function () {
        hideAlert();

        fields.forEach(clearFieldState);

        fullNameInput.focus();
      }, 0);
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

        focusFirstInvalidField();
        return;
      }

      const originalButtonText =
        submitButton.textContent;

      submitButton.disabled = true;
      submitButton.textContent =
        "Creating Staff...";

      try {
        const response = await fetch(
          "/api/staff",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify(
              collectPayload()
            )
          }
        );

        let data;

        try {
          data = await response.json();
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

        showConfirmation(data);

        form.reset();

        fields.forEach(clearFieldState);

      } catch (error) {
        console.error(
          "Create staff request failed:",
          error
        );

        showAlert(
          "Unable to connect to the server. Please try again."
        );

        if (alertBox) {
          alertBox.scrollIntoView({
            behavior: "smooth",
            block: "center"
          });
        }
      } finally {
        submitButton.disabled = false;
        submitButton.textContent =
          originalButtonText;
      }
    }
  );
})();