(function () {
  "use strict";

  const alertBox = document.getElementById("form-alert");

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function detailMessage(body, fallback) {
    return typeof body.detail === "string" ? body.detail : fallback;
  }

  function getTokenFromUrl() {
    return new URLSearchParams(window.location.search).get("token") || "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;

    const newPassword = document.getElementById("reset-new-password").value;
    const confirmPassword = document.getElementById("reset-confirm-password").value;

    if (!form.checkValidity() || newPassword !== confirmPassword) {
      form.classList.add("was-validated");
      if (newPassword !== confirmPassword) {
        showAlert("Passwords do not match.");
      }
      return;
    }

    const submitBtn = document.getElementById("reset-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: getTokenFromUrl(),
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });

      if (response.ok) {
        window.location.href = "/auth/login";
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(detailMessage(body, "Something went wrong. Please try again."));
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  const form = document.getElementById("reset-password-form");
  if (form) form.addEventListener("submit", handleSubmit);
})();
