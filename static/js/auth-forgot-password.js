(function () {
  "use strict";

  const alertBox = document.getElementById("form-alert");
  const successBox = document.getElementById("form-success");

  function showAlert(message) {
    successBox.classList.add("d-none");
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function showSuccess(message) {
    alertBox.classList.add("d-none");
    successBox.textContent = message;
    successBox.classList.remove("d-none");
  }

  function detailMessage(body, fallback) {
    return typeof body.detail === "string" ? body.detail : fallback;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
    const submitBtn = document.getElementById("forgot-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.get("email")?.trim() }),
      });

      const body = await response.json().catch(() => ({}));
      if (response.ok) {
        showSuccess(body.message || "If that email is registered, we've sent a reset link.");
        form.reset();
      } else {
        showAlert(detailMessage(body, "Something went wrong. Please try again."));
      }
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  const form = document.getElementById("forgot-password-form");
  if (form) form.addEventListener("submit", handleSubmit);
})();
