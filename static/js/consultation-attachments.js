(function () {
  "use strict";

  const root = document.getElementById("record-detail-root");
  if (!root) return;

  const recordId = root.dataset.recordId;

  const alertBox = document.getElementById("attachments-alert");
  const uploadForm = document.getElementById("attachment-upload-form");
  const fileInput = document.getElementById("attachment-file-input");
  const uploadBtn = document.getElementById("attachment-upload-btn");
  const listEl = document.getElementById("attachment-list");

  const MAX_SIZE_BYTES = 5 * 1024 * 1024;
  const ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png"];

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function renderAttachments(items) {
    if (items.length === 0) {
      listEl.innerHTML = '<p class="text-muted mb-0">No attachments yet.</p>';
      return;
    }

    listEl.innerHTML = items
      .map(
        (item) => `
          <div class="d-flex justify-content-between align-items-center border rounded p-2 mb-2">
            <div>
              <a href="/api/attachments/${item.id}/download">${escapeHtml(item.original_filename)}</a>
              <div class="small text-muted">
                ${formatSize(item.size_bytes)} - uploaded by ${escapeHtml(item.uploaded_by_name)}
                on ${new Date(item.created_at).toLocaleString()}
              </div>
            </div>
          </div>
        `
      )
      .join("");
  }

  async function loadAttachments() {
    try {
      const response = await fetch(`/api/attachments?record_id=${encodeURIComponent(recordId)}`);
      if (!response.ok) throw new Error("Request failed");
      renderAttachments(await response.json());
    } catch (err) {
      showAlert("Unable to load attachments.");
    }
  }

  async function handleUpload(event) {
    event.preventDefault();
    hideAlert();

    const file = fileInput.files[0];
    if (!file) return;

    if (!ALLOWED_TYPES.includes(file.type)) {
      showAlert("Unsupported file type. Only PDF, JPG, and PNG files are accepted.");
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      showAlert("File is too large. The maximum size is 5 MB.");
      return;
    }

    const formData = new FormData();
    formData.append("consultation_record_id", recordId);
    formData.append("file", file);

    uploadBtn.disabled = true;
    try {
      const response = await fetch("/api/attachments", {
        method: "POST",
        body: formData,
      });

      if (response.status === 201) {
        uploadForm.reset();
        await loadAttachments();
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(body.detail || "Upload failed. Please try again.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      uploadBtn.disabled = false;
    }
  }

  uploadForm.addEventListener("submit", handleUpload);
  loadAttachments();
})();
