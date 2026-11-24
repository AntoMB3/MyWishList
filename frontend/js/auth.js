/* ==========================================================================
   MyWishList — Autenticación y sesión de usuario (auth.js)
   --------------------------------------------------------------------------
   Gestiona la vista `login.html` (inicio de sesión y registro), el cierre de
   sesión y la información del usuario autenticado en la barra de navegación.
   ========================================================================== */

import {
  clearToken,
  getCurrentUser,
  getToken,
  loginUser,
  registerUser,
} from "./api.js";

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

/* --------------------------------------------------------------------------
   Helpers de sesión y usuario
   -------------------------------------------------------------------------- */

export function getInitials(username) {
  const clean = String(username || "").trim();
  if (!clean) return "??";
  const parts = clean.split(/[_-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase();
}

export async function fetchAuthenticatedUser() {
  if (!getToken()) return null;
  try {
    return await getCurrentUser();
  } catch (error) {
    if (error?.status === 401) {
      clearToken();
    }
    return null;
  }
}

export function logout(redirectUrl = "login.html") {
  clearToken();
  window.location.href = redirectUrl;
}

export function bindLogoutButtons() {
  $$('[data-action="logout"], a[aria-label="Cerrar sesión"]').forEach((el) => {
    el.addEventListener("click", (event) => {
      event.preventDefault();
      logout("login.html");
    });
  });
}

export function updateNavbarUser(user, roleText = "") {
  const chip = $(".navbar .user-chip");
  const avatar = $(".navbar .user-chip__avatar");
  const nameEl = $(".navbar .user-chip__name");
  const roleEl = $(".navbar .user-chip__role");
  const logoutBtn = $('.navbar [aria-label="Cerrar sesión"], .navbar [data-action="logout"]');
  const divider = $(".navbar .navbar__divider");

  if (!user) {
    if (chip) chip.hidden = true;
    if (divider) divider.hidden = true;
    if (logoutBtn) {
      logoutBtn.setAttribute("href", "login.html");
      logoutBtn.setAttribute("aria-label", "Iniciar sesión");
      const span = $("span", logoutBtn);
      if (span) span.textContent = "Iniciar sesión";
    }
    return;
  }

  if (chip) chip.hidden = false;
  if (divider) divider.hidden = false;
  if (avatar) avatar.textContent = getInitials(user.username);
  if (nameEl) nameEl.textContent = user.username;
  if (roleEl && roleText) roleEl.textContent = roleText;
}

/* --------------------------------------------------------------------------
   Vista de Login / Registro (login.html)
   -------------------------------------------------------------------------- */

function getSafeNextUrl() {
  const params = new URLSearchParams(window.location.search);
  const next = params.get("next");
  if (
    next &&
    !next.startsWith("http://") &&
    !next.startsWith("https://") &&
    !next.startsWith("//")
  ) {
    return next;
  }
  return "/";
}

export async function initLoginPage({ showToast }) {
  const existingUser = await fetchAuthenticatedUser();
  if (existingUser) {
    window.location.replace(getSafeNextUrl());
    return;
  }

  const tabs = $$(".tabs__btn");
  const panels = $$("[data-auth-panel]");
  const switches = $$("[data-auth-switch]");
  const title = $("#auth-title");
  const subtitle = $("#auth-subtitle");
  const legalDialog = $("#legal-modal");
  const legalBody = $("#legal-modal-body");

  $$("[data-legal-open]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();

      const section = $(`#legal-${link.dataset.legalOpen}`);
      if (!legalDialog || !legalBody || !section) return;

      if (typeof legalDialog.showModal === "function") {
        if (!legalDialog.open) legalDialog.showModal();
      } else {
        legalDialog.setAttribute("open", "");
      }

      requestAnimationFrame(() => {
        const scrollTop =
          legalBody.scrollTop +
          section.getBoundingClientRect().top -
          legalBody.getBoundingClientRect().top;
        legalBody.scrollTo({ top: Math.max(0, scrollTop), behavior: "smooth" });
        section.focus({ preventScroll: true });
      });
    });
  });

  function setTab(name) {
    tabs.forEach((tab) => {
      const isActive = tab.dataset.authTab === name;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
    });

    panels.forEach((panel) => {
      panel.hidden = panel.dataset.authPanel !== name;
    });

    switches.forEach((item) => {
      item.hidden = item.dataset.authSwitch !== name;
    });

    const activeTab = tabs.find((tab) => tab.dataset.authTab === name);
    if (activeTab) {
      if (title) title.textContent = activeTab.dataset.title;
      if (subtitle) subtitle.textContent = activeTab.dataset.subtitle;
    }
  }

  $$("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.authTab));
  });

  $$("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.togglePassword);
      if (!input) return;

      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      button.setAttribute("aria-pressed", String(isHidden));
      button.setAttribute(
        "aria-label",
        isHidden ? "Ocultar contraseña" : "Mostrar contraseña"
      );
      input.focus();
    });
  });

  const loginForm = $("#login-form");
  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!loginForm.reportValidity()) return;

    const usernameInput = $("#login-username");
    const passwordInput = $("#login-password");
    const rememberInput = $('input[name="remember"]', loginForm);
    const submitBtn = $('button[type="submit"]', loginForm);

    const username = usernameInput?.value.trim() ?? "";
    const password = passwordInput?.value ?? "";
    const remember = rememberInput ? rememberInput.checked : true;

    if (submitBtn) submitBtn.disabled = true;
    try {
      await loginUser({ username, password, remember });
      window.location.href = getSafeNextUrl();
    } catch (error) {
      showToast(error?.message || "No se pudo iniciar sesión.");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });

  const registerForm = $("#register-form");
  const password = $("#register-password");
  const confirmation = $("#register-confirm");

  function validateConfirmation() {
    if (!password || !confirmation) return;
    const mismatch = password.value !== confirmation.value;
    confirmation.setCustomValidity(
      mismatch ? "Las contraseñas no coinciden." : ""
    );
  }

  password?.addEventListener("input", validateConfirmation);
  confirmation?.addEventListener("input", validateConfirmation);

  registerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    validateConfirmation();
    if (!registerForm.reportValidity()) return;

    const usernameInput = $("#register-username");
    const submitBtn = $('button[type="submit"]', registerForm);

    const username = usernameInput?.value.trim() ?? "";
    const pwd = password?.value ?? "";

    if (submitBtn) submitBtn.disabled = true;
    try {
      await registerUser({ username, password: pwd });
      await loginUser({ username, password: pwd, remember: true });
      window.location.href = getSafeNextUrl();
    } catch (error) {
      showToast(error?.message || "No se pudo crear la cuenta.");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });

  $('[data-action="forgot-password"]')?.addEventListener("click", () => {
    showToast("Contacta con el administrador para restablecer tu contraseña.");
  });
}
