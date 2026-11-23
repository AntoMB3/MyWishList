/* ==========================================================================
   MyWishList — Interacción visual de la Fase 1
   --------------------------------------------------------------------------
   Este módulo NO realiza peticiones al backend. Solo maqueta y simula el
   comportamiento de la interfaz con datos de ejemplo:

   - Login: pestañas login/registro, mostrar contraseña y redirección.
   - Mis wishlists: modales, creación/edición/borrado simulados y compartir.
   - Artículos: búsqueda, cambio de vista (dueño/visitante), modales y CRUD
     simulado en el DOM.

   En la Fase 2, la lógica de red vivirá en `api.js`, la sesión en `auth.js`
   y el renderizado real en `app.js`.
   ========================================================================== */

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

const PLACEHOLDER_IMAGE = "assets/placeholder.svg";
const PREVIEW_IMAGE = "assets/image-icon.svg";

/* --------------------------------------------------------------------------
   Utilidades generales
   -------------------------------------------------------------------------- */

let toastTimer = null;

function showToast(message) {
  let toast = $("#toast");

  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");

    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("fill", "none");
    icon.setAttribute("stroke", "currentColor");
    icon.setAttribute("stroke-width", "2.2");
    icon.setAttribute("stroke-linecap", "round");
    icon.setAttribute("stroke-linejoin", "round");
    icon.setAttribute("aria-hidden", "true");

    const check = document.createElementNS("http://www.w3.org/2000/svg", "path");
    check.setAttribute("d", "M20 6 9 17l-5-5");
    icon.appendChild(check);

    const text = document.createElement("span");
    text.className = "toast__text";

    toast.append(icon, text);
    document.body.appendChild(toast);
  }

  $(".toast__text", toast).textContent = message;
  toast.classList.add("is-visible");

  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("is-visible");
  }, 2800);
}

async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* Seguimos con el fallback. */
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-1000px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();

  let success = false;
  try {
    success = document.execCommand("copy");
  } catch {
    success = false;
  }

  textarea.remove();
  return success;
}

function formatPrice(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(Number(value) || 0);
}

function randomShareId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID().replaceAll("-", "");
  }
  return Math.random().toString(16).slice(2).padEnd(32, "0").slice(0, 32);
}

function todayLabel() {
  const label = new Date().toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return label.replace(".", "");
}

function setMetaText(metaItem, text) {
  if (!metaItem) return;
  metaItem.replaceChild(document.createTextNode(text), metaItem.lastChild);
}

/* --------------------------------------------------------------------------
   Modales (<dialog>)
   -------------------------------------------------------------------------- */

function openDialog(dialog) {
  if (!dialog) return;

  if (typeof dialog.showModal === "function") {
    if (!dialog.open) dialog.showModal();
  } else {
    dialog.setAttribute("open", "");
  }

  requestAnimationFrame(() => {
    const firstField = dialog.querySelector("input, textarea, select");
    if (firstField && !firstField.closest("[hidden]")) firstField.focus();
  });
}

function closeDialog(dialog) {
  if (!dialog) return;
  if (typeof dialog.close === "function") {
    if (dialog.open) dialog.close();
  } else {
    dialog.removeAttribute("open");
  }
}

function initDialogs() {
  $$("[data-close]").forEach((button) => {
    button.addEventListener("click", () => closeDialog(button.closest("dialog")));
  });

  $$("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog(dialog);
    });
  });
}

/* --------------------------------------------------------------------------
   Login
   -------------------------------------------------------------------------- */

function initLogin() {
  const tabs = $$(".tabs__btn");
  const panels = $$("[data-auth-panel]");
  const switches = $$("[data-auth-switch]");
  const title = $("#auth-title");
  const subtitle = $("#auth-subtitle");

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
  loginForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!loginForm.reportValidity()) return;
    window.location.href = "index.html";
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

  registerForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!registerForm.reportValidity()) return;
    window.location.href = "index.html";
  });

  $('[data-action="forgot-password"]')?.addEventListener("click", () => {
    showToast("Te enviaríamos un correo para restablecerla (demo).");
  });
}

/* --------------------------------------------------------------------------
   Mis wishlists
   -------------------------------------------------------------------------- */

function initWishlists() {
  const grid = $("#wishlist-grid");
  const countPill = $("#wishlist-count");
  const userRole = $(".user-chip__role");
  const emptyState = $("#wishlist-empty");

  const modal = $("#wishlist-modal");
  const form = $("#wishlist-form");
  const modalTitle = $("#wishlist-modal-title");
  const modalSub = $("#wishlist-modal-sub");
  const submitLabel = $("#wishlist-submit-label");
  const titleInput = $("#wishlist-title");
  const descriptionInput = $("#wishlist-description");

  const confirmModal = $("#confirm-modal");
  const confirmTitle = $("#confirm-title");
  const confirmText = $("#confirm-text");
  const confirmButton = $("[data-confirm-delete]", confirmModal);

  const template = grid?.firstElementChild?.cloneNode(true) ?? null;

  let editingCard = null;
  let pendingDelete = null;

  function cards() {
    return grid ? $$(".wishlist-card", grid) : [];
  }

  function refreshSummary() {
    const total = cards().length;
    if (countPill) countPill.textContent = `${total} ${total === 1 ? "lista" : "listas"}`;
    if (userRole) userRole.textContent = `${total} ${total === 1 ? "lista" : "listas"}`;
    if (emptyState) emptyState.hidden = total > 0;
  }

  function resetForm() {
    editingCard = null;
    form?.reset();
    if (modalTitle) modalTitle.textContent = "Nueva wishlist";
    if (modalSub) modalSub.textContent = "Dale un nombre a la lista y, si quieres, una descripción breve.";
    if (submitLabel) submitLabel.textContent = "Crear lista";
  }

  function fillForm(card) {
    editingCard = card;
    if (titleInput) titleInput.value = card.dataset.title ?? "";
    if (descriptionInput) descriptionInput.value = card.dataset.description ?? "";
    if (modalTitle) modalTitle.textContent = "Editar wishlist";
    if (modalSub) modalSub.textContent = "Actualiza el nombre o la descripción de la lista.";
    if (submitLabel) submitLabel.textContent = "Guardar cambios";
  }

  function createCard(title, description) {
    if (!template) return null;

    const card = template.cloneNode(true);
    const shareId = randomShareId();
    const shareUrl = `http://localhost:8000/?list=${shareId}`;

    card.dataset.title = title;
    card.dataset.description = description;
    card.dataset.share = shareUrl;

    const titleLink = $(".wishlist-card__title a", card);
    if (titleLink) titleLink.textContent = title;

    const desc = $(".wishlist-card__desc", card);
    if (desc) desc.textContent = description || "Sin descripción por ahora.";

    const badge = $(".badge", card);
    if (badge) {
      badge.className = "badge badge--soft";
      badge.textContent = "Privada";
    }

    const meta = $$(".wishlist-card__meta .meta-item", card);
    setMetaText(meta[0], "0 artículos");
    setMetaText(meta[1], todayLabel());

    $$('[data-action="share"]', card).forEach((button) => {
      button.dataset.share = shareUrl;
    });

    return card;
  }

  function updateCard(card, title, description) {
    card.dataset.title = title;
    card.dataset.description = description;

    const titleLink = $(".wishlist-card__title a", card);
    if (titleLink) titleLink.textContent = title;

    const desc = $(".wishlist-card__desc", card);
    if (desc) desc.textContent = description || "Sin descripción por ahora.";
  }

  function openDelete(card) {
    pendingDelete = card;
    const title = card.dataset.title ?? "esta lista";
    if (confirmTitle) confirmTitle.textContent = "¿Eliminar wishlist?";
    if (confirmText) {
      confirmText.replaceChildren(
        document.createTextNode("¿Seguro que quieres eliminar "),
        Object.assign(document.createElement("strong"), { textContent: title }),
        document.createTextNode(" y todos sus artículos?")
      );
    }
    openDialog(confirmModal);
  }

  /* Botones "Nueva wishlist" (cabecera y estado vacío). */
  $$('[data-new="wishlist"]').forEach((button) => {
    button.addEventListener("click", () => {
      resetForm();
      openDialog(modal);
    });
  });

  /* Editar una tarjeta existente. */
  document.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="edit-wishlist"]');
    if (!button || !grid) return;
    const card = button.closest(".wishlist-card");
    if (!card) return;
    fillForm(card);
    openDialog(modal);
  });

  /* Formulario de creación / edición. */
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const title = titleInput?.value.trim() ?? "";
    const description = descriptionInput?.value.trim() ?? "";

    if (editingCard) {
      updateCard(editingCard, title, description);
      showToast("Wishlist actualizada (demo).");
    } else if (grid) {
      const card = createCard(title, description);
      if (card) {
        grid.prepend(card);
        showToast("Wishlist creada (demo).");
      }
    }

    refreshSummary();
    closeDialog(modal);
    resetForm();
  });

  /* Eliminar. */
  document.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="delete-wishlist"]');
    if (!button) return;
    const card = button.closest(".wishlist-card");
    if (card) openDelete(card);
  });

  confirmButton?.addEventListener("click", () => {
    if (pendingDelete) {
      const title = pendingDelete.dataset.title;
      pendingDelete.remove();
      pendingDelete = null;
      showToast(`“${title}” eliminada (demo).`);
      refreshSummary();
    }
    closeDialog(confirmModal);
  });

  /* Compartir. */
  document.addEventListener("click", async (event) => {
    const button = event.target.closest('[data-action="share"]');
    if (!button) return;

    const url = button.dataset.share ?? "";
    const copied = await copyToClipboard(url);
    showToast(
      copied
        ? "Enlace copiado al portapapeles."
        : "No se pudo copiar el enlace en este navegador."
    );
  });

  refreshSummary();
}

/* --------------------------------------------------------------------------
   Artículos de una wishlist
   -------------------------------------------------------------------------- */

function initWishlistItems() {
  const grid = $("#item-grid");
  const countLabel = $("#item-count");
  const emptyState = $("#item-empty");
  const emptyTitle = $("h2", emptyState);
  const emptyText = $("p", emptyState);
  const searchInput = $("#item-search");

  const modal = $("#item-modal");
  const form = $("#item-form");
  const modalTitle = $("#item-modal-title");
  const modalSub = $("#item-modal-sub");
  const submitLabel = $("#item-submit-label");
  const titleInput = $("#item-title");
  const priceInput = $("#item-price");
  const urlInput = $("#item-url");
  const imageInput = $("#item-image");
  const descriptionInput = $("#item-description");
  const imagePreview = $("#item-image-preview");

  const confirmModal = $("#confirm-modal");
  const confirmTitle = $("#confirm-title");
  const confirmText = $("#confirm-text");
  const confirmButton = $("[data-confirm-delete]", confirmModal);

  const template = grid?.firstElementChild?.cloneNode(true) ?? null;

  let editingCard = null;
  let pendingDelete = null;

  function cards() {
    return grid ? $$(".item-card", grid) : [];
  }

  function refreshCount() {
    const all = cards();
    const visible = all.filter((card) => !card.hidden).length;
    const query = searchInput?.value.trim() ?? "";

    if (countLabel) {
      countLabel.textContent = query
        ? `${visible} de ${all.length} artículos`
        : `${all.length} ${all.length === 1 ? "artículo" : "artículos"}`;
    }

    if (emptyState) {
      emptyState.hidden = visible > 0;
      if (emptyTitle) {
        emptyTitle.textContent =
          all.length === 0 ? "Esta lista está vacía" : "No encontramos artículos";
      }
      if (emptyText) {
        emptyText.textContent =
          all.length === 0
            ? "Agrega tu primer artículo para empezar a llenar esta wishlist."
            : "Prueba con otro término de búsqueda o agrega un artículo nuevo a la lista.";
      }
    }
  }

  function filterCards() {
    const query = (searchInput?.value ?? "").trim().toLowerCase();

    cards().forEach((card) => {
      if (!query) {
        card.hidden = false;
        return;
      }

      const haystack = `${card.dataset.title ?? ""} ${card.dataset.description ?? ""}`.toLowerCase();
      card.hidden = !haystack.includes(query);
    });

    refreshCount();
  }

  searchInput?.addEventListener("input", filterCards);

  function updatePreview() {
    if (!imagePreview) return;
    const value = imageInput?.value.trim() ?? "";
    const isUsable =
      /^https?:\/\//i.test(value) || value.startsWith("assets/");
    imagePreview.src = isUsable ? value : PREVIEW_IMAGE;
  }

  imageInput?.addEventListener("input", updatePreview);

  function resetForm() {
    editingCard = null;
    form?.reset();
    if (imagePreview) imagePreview.src = PREVIEW_IMAGE;
    if (modalTitle) modalTitle.textContent = "Nuevo artículo";
    if (modalSub) modalSub.textContent = "Completa los datos del producto que quieres guardar.";
    if (submitLabel) submitLabel.textContent = "Guardar artículo";
  }

  function fillForm(card) {
    editingCard = card;
    if (titleInput) titleInput.value = card.dataset.title ?? "";
    if (priceInput) priceInput.value = card.dataset.price ?? "";
    if (urlInput) urlInput.value = card.dataset.url ?? "";
    if (imageInput) imageInput.value = card.dataset.image ?? "";
    if (descriptionInput) descriptionInput.value = card.dataset.description ?? "";
    updatePreview();
    if (modalTitle) modalTitle.textContent = "Editar artículo";
    if (modalSub) modalSub.textContent = "Actualiza los datos del artículo.";
    if (submitLabel) submitLabel.textContent = "Guardar cambios";
  }

  function applyData(card, data) {
    card.dataset.title = data.title;
    card.dataset.description = data.description;
    card.dataset.price = data.price;
    card.dataset.url = data.url;
    card.dataset.image = data.image;

    const image = $(".item-card__img", card);
    if (image) {
      image.src = data.image;
      image.alt = data.title;
    }

    const priceTag = $(".price-tag", card);
    if (priceTag) priceTag.textContent = formatPrice(data.price);

    const title = $(".item-card__title", card);
    if (title) title.textContent = data.title;

    const description = $(".item-card__desc", card);
    if (description) description.textContent = data.description || "Sin descripción.";

    const storeLink = $(".item-card__footer .btn", card);
    if (storeLink) storeLink.href = data.url;
  }

  function createCard(data) {
    if (!template) return null;
    const card = template.cloneNode(true);
    card.hidden = false;
    applyData(card, data);
    return card;
  }

  function openDelete(card) {
    pendingDelete = card;
    const title = card.dataset.title ?? "este artículo";
    if (confirmTitle) confirmTitle.textContent = "¿Eliminar artículo?";
    if (confirmText) {
      confirmText.replaceChildren(
        document.createTextNode("¿Seguro que quieres eliminar "),
        Object.assign(document.createElement("strong"), { textContent: title }),
        document.createTextNode(" de la lista?")
      );
    }
    openDialog(confirmModal);
  }

  /* Botón "Nuevo artículo". */
  $$('[data-new="item"]').forEach((button) => {
    button.addEventListener("click", () => {
      resetForm();
      openDialog(modal);
    });
  });

  /* Editar un artículo. */
  document.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="edit-item"]');
    if (!button) return;
    const card = button.closest(".item-card");
    if (!card) return;
    fillForm(card);
    openDialog(modal);
  });

  /* Formulario de artículo. */
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const data = {
      title: titleInput?.value.trim() ?? "",
      price: priceInput?.value.trim() ?? "0",
      url: urlInput?.value.trim() ?? "",
      image: imageInput?.value.trim() ?? "",
      description: descriptionInput?.value.trim() ?? "",
    };

    if (editingCard) {
      applyData(editingCard, data);
      showToast("Artículo actualizado (demo).");
    } else if (grid) {
      const card = createCard(data);
      if (card) {
        grid.prepend(card);
        showToast("Artículo agregado (demo).");
      }
    }

    closeDialog(modal);
    resetForm();
    filterCards();
  });

  /* Eliminar un artículo. */
  document.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="delete-item"]');
    if (!button) return;
    const card = button.closest(".item-card");
    if (card) openDelete(card);
  });

  confirmButton?.addEventListener("click", () => {
    if (pendingDelete) {
      const title = pendingDelete.dataset.title;
      pendingDelete.remove();
      pendingDelete = null;
      showToast(`“${title}” eliminado (demo).`);
      filterCards();
    }
    closeDialog(confirmModal);
  });

  /* Compartir. */
  document.addEventListener("click", async (event) => {
    const button = event.target.closest('[data-action="share"]');
    if (!button) return;

    const copied = await copyToClipboard(button.dataset.share ?? "");
    showToast(
      copied
        ? "Enlace copiado al portapapeles."
        : "No se pudo copiar el enlace en este navegador."
    );
  });

  /* Cambio entre vista dueño y vista visitante. */
  $$("[data-view-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.viewToggle;
      document.body.dataset.viewMode = mode;

      $$("[data-view-toggle]").forEach((item) => {
        const isActive = item === button;
        item.classList.toggle("is-active", isActive);
        item.setAttribute("aria-pressed", String(isActive));
      });

      showToast(
        mode === "visitor"
          ? "Vista visitante: así verá la lista quien reciba el enlace."
          : "Vista dueño: puedes crear, editar y eliminar artículos."
      );
    });
  });

  refreshCount();
}

/* --------------------------------------------------------------------------
   Arranque
   -------------------------------------------------------------------------- */

function init() {
  initDialogs();

  switch (document.body.dataset.page) {
    case "login":
      initLogin();
      break;
    case "wishlists":
      initWishlists();
      break;
    case "wishlist":
      initWishlistItems();
      break;
    default:
      break;
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
