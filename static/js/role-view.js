(function () {
  "use strict";

  // Cosmetic "viewing as" filter for the nav bar only - no real login/session
  // exists yet. This does NOT protect any page or API; every URL is still
  // directly reachable no matter what's selected here. Purely a demo/testing
  // convenience until real auth lands.
  const STORAGE_KEY = "clinic-portal-viewing-as";

  const switcher = document.getElementById("role-switcher");
  if (!switcher) return;

  function applyRole(role) {
    document.querySelectorAll(".nav-link[data-role]").forEach((link) => {
      const matches = role === "all" || link.dataset.role === role;
      link.classList.toggle("d-none", !matches);
    });
  }

  const savedRole = localStorage.getItem(STORAGE_KEY) || "all";
  switcher.value = savedRole;
  applyRole(savedRole);

  switcher.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEY, switcher.value);
    applyRole(switcher.value);
  });
})();
