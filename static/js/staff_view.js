(function () {
  "use strict";

  const root = document.getElementById(
    "staff-detail-root"
  );

  if (!root) {
    return;
  }

  const staffId = root.dataset.staffId;

  function byId(id) {
    return document.getElementById(id);
  }

  const form = byId("edit-staff-form");
  const nameInput = byId("edit-full-name");
  const emailInput = byId("edit-email");
  const roleInput = byId("edit-role");
  const activeInput = byId("edit-is-active");

  const licenseInput = byId(
    "edit-license-number"
  );

  const specialtyInput = byId(
    "edit-specialty"
  );

  const doctorStatusInput = byId(
    "edit-doctor-status"
  );

  let currentStaff = null;

  const roleLabels = {
    doctor: "Doctor",
    nurse: "Nurse (Receptionist)",
    admin: "Administration"
  };

  const emailPattern =
    /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  const namePattern =
    /^[\p{L}\p{M}.'’-]+(?:\s+[\p{L}\p{M}.'’-]+)+$/u;

  const licensePattern =
    /^MMC-\d{5}$/;

  function normaliseSpaces(value) {
    return String(value || "")
      .trim()
      .replace(/\s+/g, " ");
  }

  function setText(id, value) {
    const element = byId(id);

    if (element) {
      element.textContent = value || "—";
    }
  }

  function formatRole(role) {
    return roleLabels[role] || role;
  }

  function formatDate(value) {
    if (!value) {
      return "—";
    }

    return new Intl.DateTimeFormat(
      "en-MY",
      {
        day: "2-digit",
        month: "long",
        year: "numeric"
      }
    ).format(new Date(value));
  }

  function showAlert(id, message) {
    const element = byId(id);

    element.textContent = message;
    element.classList.remove("d-none");
  }

  function hideAlert(id) {
    const element = byId(id);

    element.textContent = "";
    element.classList.add("d-none");
  }

  function getInitials(name) {
    const words = normaliseSpaces(
      name
    ).split(" ");

    const firstLetter =
      words[0]?.[0] || "S";

    const lastLetter =
      words.length > 1
        ? words[words.length - 1][0]
        : "T";

    return (
      firstLetter + lastLetter
    ).toUpperCase();
  }

  function showFieldError(
    input,
    message
  ) {
    input.classList.add("is-invalid");
    input.classList.remove("is-valid");

    const errorElement = byId(
      input.id + "-error"
    );

    if (errorElement) {
      errorElement.textContent = message;
    }

    return false;
  }

  function showFieldValid(input) {
    input.classList.remove("is-invalid");
    input.classList.add("is-valid");

    const errorElement = byId(
      input.id + "-error"
    );

    if (errorElement) {
      errorElement.textContent = "";
    }

    return true;
  }

  function renderStaff(staff) {
    currentStaff = staff;

    setText(
      "staff-heading-id",
      staff.staff_id
    );

    setText(
      "staff-full-name",
      staff.full_name
    );

    setText(
      "staff-role-heading",
      formatRole(staff.role)
    );

    setText(
      "staff-email-heading",
      staff.email
    );

    setText(
      "staff-avatar-text",
      getInitials(staff.full_name)
    );

    setText(
      "view-staff-id",
      staff.staff_id
    );

    setText(
      "view-full-name",
      staff.full_name
    );

    setText(
      "view-role",
      formatRole(staff.role)
    );

    setText(
      "view-created-at",
      formatDate(staff.created_at)
    );

    setText(
      "view-account-status",
      staff.is_active
        ? "Active"
        : "Inactive"
    );

    const emailLink = byId(
      "view-email"
    );

    emailLink.textContent = staff.email;
    emailLink.href =
      "mailto:" + staff.email;

    const statusBadge = byId(
      "staff-status-badge"
    );

    statusBadge.textContent =
      staff.is_active
        ? "Active"
        : "Inactive";

    statusBadge.className =
      "staff-status-badge " +
      (
        staff.is_active
          ? "active"
          : "inactive"
      );

    const isDoctor =
      staff.role === "doctor";

    byId(
      "doctor-information-card"
    ).classList.toggle(
      "d-none",
      !isDoctor
    );

    byId(
      "doctor-edit-fields"
    ).classList.toggle(
      "d-none",
      !isDoctor
    );

    if (isDoctor) {
      setText(
        "view-license-number",
        staff.license_number
      );

      setText(
        "view-specialty",
        staff.specialty
      );

      setText(
        "view-department",
        staff.department
      );

      setText(
        "view-doctor-status",
        staff.doctor_status
      );
    }

    byId(
      "staff-detail-loading"
    ).classList.add("d-none");

    byId(
      "staff-detail-content"
    ).classList.remove("d-none");

    byId(
      "edit-staff-button"
    ).classList.remove("d-none");
  }

  function populateForm() {
    nameInput.value =
      currentStaff.full_name || "";

    emailInput.value =
      currentStaff.email || "";

    roleInput.value =
      formatRole(currentStaff.role);

    activeInput.value =
      String(currentStaff.is_active);

    licenseInput.value =
      currentStaff.license_number || "";

    specialtyInput.value =
      currentStaff.specialty || "";

    doctorStatusInput.value =
      currentStaff.doctor_status ||
      "active";

    [
      nameInput,
      emailInput,
      licenseInput,
      specialtyInput
    ].forEach(function (input) {
      input.classList.remove(
        "is-valid",
        "is-invalid"
      );
    });
  }

  function validateForm() {
    let isValid = true;

    const fullName = normaliseSpaces(
      nameInput.value
    );

    const email = emailInput.value
      .trim()
      .toLowerCase();

    if (!namePattern.test(fullName)) {
      isValid = showFieldError(
        nameInput,
        "Full name must contain at least " +
        "2 words and valid characters."
      );
    } else {
      nameInput.value = fullName;
      showFieldValid(nameInput);
    }

    if (!emailPattern.test(email)) {
      isValid = showFieldError(
        emailInput,
        "Enter a valid email address."
      );
    } else {
      emailInput.value = email;
      showFieldValid(emailInput);
    }

    if (currentStaff.role === "doctor") {
      const licenseNumber =
        licenseInput.value
          .trim()
          .toUpperCase();

      if (
        !licensePattern.test(
          licenseNumber
        )
      ) {
        isValid = showFieldError(
          licenseInput,
          "Use the format MMC-12345."
        );
      } else {
        licenseInput.value =
          licenseNumber;

        showFieldValid(licenseInput);
      }

      if (!specialtyInput.value) {
        isValid = showFieldError(
          specialtyInput,
          "Please select a specialty."
        );
      } else {
        showFieldValid(
          specialtyInput
        );
      }
    }

    return isValid;
  }

  async function loadStaff() {
    try {
      const response = await fetch(
        "/api/staff/" +
        encodeURIComponent(staffId)
      );

      const payload =
        await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ||
          "Staff details could not be loaded."
        );
      }

      renderStaff(payload);

    } catch (error) {
      byId(
        "staff-detail-loading"
      ).classList.add("d-none");

      showAlert(
        "staff-detail-alert",
        error.message
      );
    }
  }

  byId(
    "edit-staff-button"
  ).addEventListener(
    "click",
    function () {
      hideAlert(
        "staff-success-alert"
      );

      populateForm();

      byId(
        "staff-edit-section"
      ).classList.remove("d-none");

      byId(
        "edit-staff-button"
      ).classList.add("d-none");
    }
  );

  byId(
    "cancel-edit-button"
  ).addEventListener(
    "click",
    function () {
      byId(
        "staff-edit-section"
      ).classList.add("d-none");

      byId(
        "edit-staff-button"
      ).classList.remove("d-none");

      hideAlert(
        "staff-update-alert"
      );
    }
  );

  form.addEventListener(
    "submit",
    async function (event) {
      event.preventDefault();

      hideAlert(
        "staff-update-alert"
      );

      if (!validateForm()) {
        return;
      }

      const saveButton = byId(
        "save-staff-button"
      );

      saveButton.disabled = true;
      saveButton.textContent =
        "Saving...";

      const payload = {
        full_name: nameInput.value,
        email: emailInput.value,
        is_active:
          activeInput.value === "true",
        license_number: null,
        specialty: null,
        doctor_status: null
      };

      if (
        currentStaff.role === "doctor"
      ) {
        payload.license_number =
          licenseInput.value;

        payload.specialty =
          specialtyInput.value;

        payload.doctor_status =
          doctorStatusInput.value;
      }

      try {
        const response = await fetch(
          "/api/staff/" +
          encodeURIComponent(staffId),
          {
            method: "PATCH",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify(payload)
          }
        );

        const result =
          await response.json();

        if (!response.ok) {
          throw new Error(
            typeof result.detail ===
              "string"
              ? result.detail
              : "Staff details could not " +
                "be updated."
          );
        }

        renderStaff(result);

        byId(
          "staff-edit-section"
        ).classList.add("d-none");

        showAlert(
          "staff-success-alert",
          "Staff details updated successfully."
        );

      } catch (error) {
        showAlert(
          "staff-update-alert",
          error.message
        );

      } finally {
        saveButton.disabled = false;
        saveButton.textContent =
          "Save Changes";
      }
    }
  );

  loadStaff();
})();