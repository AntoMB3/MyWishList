/* ==========================================================================
   MyWishList — Autenticación y sesión de usuario (auth.js)
   --------------------------------------------------------------------------
   Gestiona la vista `login.html` (inicio de sesión y registro), el cierre de
   sesión y la información del usuario autenticado en la barra de navegación.
   ========================================================================== */

import {
  changePassword,
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
  const authOnly = $$(".navbar [data-auth-only]");

  if (!user) {
    if (chip) chip.hidden = true;
    if (divider) divider.hidden = true;
    authOnly.forEach((el) => {
      el.hidden = true;
    });
    const menu = $(".navbar #user-menu");
    if (menu) menu.hidden = true;
    const trigger = $(".navbar #user-menu-trigger");
    trigger?.setAttribute("aria-expanded", "false");
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
  authOnly.forEach((el) => {
    el.hidden = false;
  });
  if (avatar) avatar.textContent = getInitials(user.username);
  if (nameEl) nameEl.textContent = user.username;
  if (roleEl && roleText) roleEl.textContent = roleText;
}

/* --------------------------------------------------------------------------
   Mostrar/ocultar contraseñas (login y modal de cambio)
   -------------------------------------------------------------------------- */

function bindPasswordToggles(scope = document) {
  $$("[data-toggle-password]", scope).forEach((button) => {
    if (button.dataset.bound === "true") return;
    button.dataset.bound = "true";

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
}

/* --------------------------------------------------------------------------
   Menú de cuenta (chip del usuario en la navbar)
   -------------------------------------------------------------------------- */

export function initUserMenu() {
  const trigger = $("#user-menu-trigger");
  const menu = $("#user-menu");
  if (!trigger || !menu) return;

  function setOpen(open) {
    menu.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open) {
      const firstItem = $(".user-menu__item", menu);
      firstItem?.focus();
    }
  }

  function close({ restoreFocus = false } = {}) {
    if (menu.hidden) return;
    setOpen(false);
    if (restoreFocus) trigger.focus();
  }

  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    setOpen(menu.hidden);
  });

  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      if (menu.hidden) {
        event.preventDefault();
        setOpen(true);
      }
    } else if (event.key === "Escape") {
      close({ restoreFocus: true });
    }
  });

  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close({ restoreFocus: true });
    }
  });

  // Al elegir una acción del menú se cierra y deja paso al modal/botón.
  menu.addEventListener("click", (event) => {
    if (event.target.closest(".user-menu__item")) close();
  });

  document.addEventListener("click", (event) => {
    if (menu.hidden) return;
    if (menu.contains(event.target) || trigger.contains(event.target)) return;
    close();
  });

  // Cerrar también cuando el foco sale del menú (navegación con Tab).
  document.addEventListener("focusin", (event) => {
    if (menu.hidden) return;
    if (menu.contains(event.target) || trigger.contains(event.target)) return;
    close();
  });
}

/* --------------------------------------------------------------------------
   Modal: cambiar contraseña (index.html y wishlist.html)
   -------------------------------------------------------------------------- */

export function initPasswordModal({ showToast } = {}) {
  const modal = $("#password-modal");
  const form = $("#password-form");
  if (!modal || !form) return;

  const currentInput = $("#password-current");
  const newInput = $("#password-new");
  const confirmInput = $("#password-confirm");
  const submitBtn = $('button[type="submit"]', form);

  bindPasswordToggles(modal);

  function validateConfirmation() {
    if (!newInput || !confirmInput) return;
    const mismatch = newInput.value !== confirmInput.value;
    confirmInput.setCustomValidity(
      mismatch ? "Las contraseñas no coinciden." : ""
    );
  }

  function resetForm() {
    form.reset();
    if (confirmInput) confirmInput.setCustomValidity("");
  }

  newInput?.addEventListener("input", validateConfirmation);
  confirmInput?.addEventListener("input", validateConfirmation);

  $$('[data-modal-open="password-modal"]').forEach((button) => {
    button.addEventListener("click", () => {
      resetForm();
      if (typeof modal.showModal === "function") {
        if (!modal.open) modal.showModal();
      } else {
        modal.setAttribute("open", "");
      }
      requestAnimationFrame(() => currentInput?.focus());
    });
  });

  modal.addEventListener("close", resetForm);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    validateConfirmation();
    if (!form.reportValidity()) return;

    const currentPassword = currentInput?.value ?? "";
    const newPassword = newInput?.value ?? "";

    if (newPassword === currentPassword) {
      showToast("La nueva contraseña debe ser diferente de la actual.");
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    try {
      await changePassword({ currentPassword, newPassword });
      if (typeof modal.close === "function") {
        modal.close();
      } else {
        modal.removeAttribute("open");
      }
      resetForm();
      showToast("Contraseña actualizada. Se cerraron las demás sesiones.");
    } catch (error) {
      if (error?.status === 401) {
        logout("login.html");
        return;
      }
      showToast(error?.message || "No se pudo actualizar la contraseña.");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
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

  bindPasswordToggles();

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
    showToast(
      "Pide al administrador una contraseña temporal y cámbiala al entrar en la aplicación."
    );
  });
}
