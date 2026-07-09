(function () {
  "use strict";

  const form = document.getElementById("login-form");
  if (!form) return;

  const alertBox = document.getElementById("form-alert");
  const submitBtn = document.getElementById("submit-btn");

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    hideAlert();

    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
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
        window.location.href = "/patients";
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

  form.addEventListener("submit", handleSubmit);
})();
