(function () {
  "use strict";

  const root = document.getElementById("profile-root");
  if (!root) return;

  function byId(id) {
    return document.getElementById(id);
  }

  const nameInput = byId("profile-full-name-input");
  const emailInput = byId("profile-email-input");

  const currentPasswordInput = byId("current-password-input");
  const newPasswordInput = byId("new-password-input");
  const confirmPasswordInput = byId("confirm-password-input");

  const roleLabels = {
    doctor: "Doctor",
    nurse: "Nurse",
    receptionist: "Receptionist",
    admin: "Administration",
  };

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const namePattern = /^[\p{L}\p{M}.'’-]+(?:\s+[\p{L}\p{M}.'’-]+)+$/u;

  function normaliseSpaces(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function setText(id, value) {
    const element = byId(id);
    if (element) element.textContent = value || "—";
  }

  function formatRole(role) {
    return roleLabels[role] || role;
  }

  function getInitials(name) {
    const words = normaliseSpaces(name).split(" ");
    const firstLetter = words[0]?.[0] || "S";
    const lastLetter = words.length > 1 ? words[words.length - 1][0] : "T";
    return (firstLetter + lastLetter).toUpperCase();
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

  function showFieldError(input, message) {
    input.classList.add("is-invalid");
    input.classList.remove("is-valid");
    const errorElement = byId(input.id + "-error");
    if (errorElement) errorElement.textContent = message;
    return false;
  }

  function showFieldValid(input) {
    input.classList.remove("is-invalid");
    input.classList.add("is-valid");
    const errorElement = byId(input.id + "-error");
    if (errorElement) errorElement.textContent = "";
    return true;
  }

  function renderProfile(profile) {
    setText("profile-full-name", profile.full_name);
    setText("profile-role-heading", formatRole(profile.role));
    setText("profile-email-heading", profile.email);
    setText("profile-avatar-text", getInitials(profile.full_name));

    nameInput.value = profile.full_name || "";
    emailInput.value = profile.email || "";
    [nameInput, emailInput].forEach((input) => input.classList.remove("is-valid", "is-invalid"));

    byId("profile-loading").classList.add("d-none");
    byId("profile-content").classList.remove("d-none");
  }

  async function loadProfile() {
    try {
      const response = await fetch("/api/staff/me");
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Your profile could not be loaded.");
      }
      renderProfile(payload);
    } catch (error) {
      byId("profile-loading").classList.add("d-none");
      showAlert("profile-alert", error.message);
    }
  }

  function validateProfileForm() {
    let isValid = true;

    const fullName = normaliseSpaces(nameInput.value);
    const email = emailInput.value.trim().toLowerCase();

    if (!namePattern.test(fullName)) {
      isValid = showFieldError(
        nameInput,
        "Full name must contain at least 2 words and valid characters."
      );
    } else {
      nameInput.value = fullName;
      showFieldValid(nameInput);
    }

    if (!emailPattern.test(email)) {
      isValid = showFieldError(emailInput, "Enter a valid email address.");
    } else {
      emailInput.value = email;
      showFieldValid(emailInput);
    }

    return isValid;
  }

  byId("edit-profile-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    hideAlert("profile-update-alert");
    hideAlert("profile-success-alert");

    if (!validateProfileForm()) return;

    const saveButton = byId("save-profile-button");
    saveButton.disabled = true;
    saveButton.textContent = "Saving...";

    try {
      const response = await fetch("/api/staff/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: nameInput.value,
          email: emailInput.value,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string" ? result.detail : "Your profile could not be updated."
        );
      }

      renderProfile(result);
      showAlert("profile-success-alert", "Profile updated successfully.");
    } catch (error) {
      showAlert("profile-update-alert", error.message);
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = "Save Changes";
    }
  });

  byId("change-password-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    hideAlert("password-update-alert");
    hideAlert("password-success-alert");

    let isValid = true;

    if (!currentPasswordInput.value) {
      isValid = showFieldError(currentPasswordInput, "Enter your current password.");
    } else {
      showFieldValid(currentPasswordInput);
    }

    if (!newPasswordInput.value || newPasswordInput.value.length < 8) {
      isValid = showFieldError(newPasswordInput, "New password must be at least 8 characters.");
    } else {
      showFieldValid(newPasswordInput);
    }

    if (!confirmPasswordInput.value || confirmPasswordInput.value !== newPasswordInput.value) {
      isValid = showFieldError(confirmPasswordInput, "Passwords do not match.");
    } else {
      showFieldValid(confirmPasswordInput);
    }

    if (!isValid) return;

    const saveButton = byId("save-password-button");
    saveButton.disabled = true;
    saveButton.textContent = "Changing...";

    try {
      const response = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPasswordInput.value,
          new_password: newPasswordInput.value,
          confirm_password: confirmPasswordInput.value,
        }),
      });

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string" ? result.detail : "Your password could not be changed."
        );
      }

      byId("change-password-form").reset();
      [currentPasswordInput, newPasswordInput, confirmPasswordInput].forEach((input) =>
        input.classList.remove("is-valid", "is-invalid")
      );
      showAlert("password-success-alert", "Password changed successfully.");
    } catch (error) {
      showAlert("password-update-alert", error.message);
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = "Change Password";
    }
  });

  loadProfile();
})();
