/* ==========================================================================
   MyWishList — Controlador de vistas y renderizado del DOM (app.js)
   --------------------------------------------------------------------------
   Conecta las vistas `index.html` y `wishlist.html` con la API de FastAPI.
   Construye el DOM de forma segura (`document.createElement` + `.textContent`)
   para prevenir XSS.
   ========================================================================== */

import {
  createItem,
  createWishlist,
  deleteItem,
  deleteWishlist,
  fetchProductImage,
  getMyWishlists,
  getSharedWishlist,
  updateItem,
  updateWishlist,
  uploadProductImage,
} from "./api.js";
import {
  bindLogoutButtons,
  fetchAuthenticatedUser,
  getInitials,
  initLoginPage,
  logout,
  updateNavbarUser,
} from "./auth.js";

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

const SVG_NS = "http://www.w3.org/2000/svg";
const PLACEHOLDER_IMAGE = "assets/placeholder.svg";
const PREVIEW_IMAGE = "assets/image-icon.svg";

/* --------------------------------------------------------------------------
   Utilidades de interfaz y formato
   -------------------------------------------------------------------------- */

let toastTimer = null;

export function showToast(message) {
  let toast = $("#toast");

  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");

    const icon = createSvg([
      { tag: "path", attrs: { d: "M20 6 9 17l-5-5" } },
    ], "2.2");

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

function formatDate(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  return date
    .toLocaleDateString("es-ES", {
      day: "numeric",
      month: "short",
      year: "numeric",
    })
    .replace(".", "");
}

function buildShareUrl(shareId) {
  const url = new URL("wishlist.html", window.location.href);
  url.search = "";
  url.searchParams.set("list", shareId);
  return url.toString();
}

function buildWishlistHref(shareId) {
  return `wishlist.html?list=${encodeURIComponent(shareId)}`;
}

function createSvg(children, strokeWidth = "1.8") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", strokeWidth);
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");

  children.forEach(({ tag, attrs }) => {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, val]) => node.setAttribute(key, val));
    svg.appendChild(node);
  });

  return svg;
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
   Construcción segura de tarjetas (Sin innerHTML con datos de usuario)
   -------------------------------------------------------------------------- */

function createWishlistCardElement(wishlist) {
  const shareUrl = buildShareUrl(wishlist.share_id);
  const detailHref = buildWishlistHref(wishlist.share_id);
  const itemCount = Number(wishlist.item_count) || 0;

  const card = document.createElement("article");
  card.className = "wishlist-card";
  card.dataset.id = String(wishlist.id);
  card.dataset.shareId = wishlist.share_id;
  card.dataset.title = wishlist.title;
  card.dataset.description = wishlist.description || "";
  card.dataset.share = shareUrl;
  card.dataset.itemCount = String(itemCount);
  card.dataset.createdAt = wishlist.created_at || "";

  // Top row (icon)
  const top = document.createElement("div");
  top.className = "wishlist-card__top";

  const iconWrap = document.createElement("span");
  iconWrap.className = "wishlist-card__icon";
  iconWrap.setAttribute("aria-hidden", "true");
  iconWrap.appendChild(
    createSvg([
      { tag: "rect", attrs: { x: "3", y: "8", width: "18", height: "4", rx: "1" } },
      { tag: "path", attrs: { d: "M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7" } },
      {
        tag: "path",
        attrs: {
          d: "M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5",
        },
      },
    ])
  );

  top.append(iconWrap);

  // Title
  const h2 = document.createElement("h2");
  h2.className = "wishlist-card__title";
  const titleLink = document.createElement("a");
  titleLink.href = detailHref;
  titleLink.textContent = wishlist.title;
  h2.appendChild(titleLink);

  // Description
  const desc = document.createElement("p");
  desc.className = "wishlist-card__desc";
  desc.textContent = wishlist.description || "Sin descripción por ahora.";

  // Meta (item count + date)
  const meta = document.createElement("div");
  meta.className = "wishlist-card__meta";

  const countMeta = document.createElement("span");
  countMeta.className = "meta-item";
  countMeta.append(
    createSvg([
      {
        tag: "path",
        attrs: {
          d: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z",
        },
      },
      { tag: "path", attrs: { d: "m3.3 7 8.7 5 8.7-5M12 22V12" } },
    ]),
    document.createTextNode(
      `${itemCount} ${itemCount === 1 ? "artículo" : "artículos"}`
    )
  );

  const dateMeta = document.createElement("span");
  dateMeta.className = "meta-item";
  dateMeta.append(
    createSvg([
      { tag: "rect", attrs: { x: "3", y: "4", width: "18", height: "18", rx: "2" } },
      { tag: "path", attrs: { d: "M16 2v4M8 2v4M3 10h18" } },
    ]),
    document.createTextNode(formatDate(wishlist.created_at))
  );

  meta.append(countMeta, dateMeta);

  // Actions
  const actions = document.createElement("div");
  actions.className = "wishlist-card__actions";

  const viewBtn = document.createElement("a");
  viewBtn.className = "btn btn--primary btn--sm";
  viewBtn.href = detailHref;
  viewBtn.textContent = "Ver artículos";

  const tools = document.createElement("div");
  tools.className = "wishlist-card__tools";

  const shareBtn = document.createElement("button");
  shareBtn.className = "btn btn--ghost btn--icon";
  shareBtn.type = "button";
  shareBtn.dataset.action = "share";
  shareBtn.dataset.share = shareUrl;
  shareBtn.title = "Copiar enlace para compartir";
  shareBtn.setAttribute("aria-label", "Copiar enlace para compartir");
  shareBtn.appendChild(
    createSvg([
      { tag: "path", attrs: { d: "M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" } },
      { tag: "path", attrs: { d: "M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" } },
    ])
  );

  const editBtn = document.createElement("button");
  editBtn.className = "btn btn--ghost btn--icon";
  editBtn.type = "button";
  editBtn.dataset.action = "edit-wishlist";
  editBtn.title = "Editar wishlist";
  editBtn.setAttribute("aria-label", "Editar wishlist");
  editBtn.appendChild(
    createSvg([
      { tag: "path", attrs: { d: "M12 20h9" } },
      { tag: "path", attrs: { d: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" } },
    ])
  );

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "btn btn--ghost btn--icon is-danger";
  deleteBtn.type = "button";
  deleteBtn.dataset.action = "delete-wishlist";
  deleteBtn.title = "Eliminar wishlist";
  deleteBtn.setAttribute("aria-label", "Eliminar wishlist");
  deleteBtn.appendChild(
    createSvg([
      {
        tag: "path",
        attrs: {
          d: "M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6",
        },
      },
      { tag: "path", attrs: { d: "M10 11v6M14 11v6" } },
    ])
  );

  tools.append(shareBtn, editBtn, deleteBtn);
  actions.append(viewBtn, tools);

  card.append(top, h2, desc, meta, actions);
  return card;
}

function createItemCardElement(item) {
  const card = document.createElement("article");
  card.className = "item-card";

  // Media
  const media = document.createElement("div");
  media.className = "item-card__media";

  const img = document.createElement("img");
  img.className = "item-card__img";
  img.loading = "lazy";
  img.addEventListener("error", () => {
    if (!img.src.endsWith(PLACEHOLDER_IMAGE)) {
      img.src = PLACEHOLDER_IMAGE;
    }
  });

  const priceTag = document.createElement("span");
  priceTag.className = "price-tag";

  media.append(img, priceTag);

  // Body
  const body = document.createElement("div");
  body.className = "item-card__body";

  const titleEl = document.createElement("h2");
  titleEl.className = "item-card__title";

  const descEl = document.createElement("p");
  descEl.className = "item-card__desc";

  body.append(titleEl, descEl);

  // Footer
  const footer = document.createElement("div");
  footer.className = "item-card__footer";

  const storeLink = document.createElement("a");
  storeLink.className = "btn btn--ghost btn--sm";
  storeLink.target = "_blank";
  storeLink.rel = "noopener noreferrer";
  storeLink.append(
    document.createTextNode("Ver en tienda "),
    createSvg([{ tag: "path", attrs: { d: "M7 17 17 7M7 7h10v10" } }], "2")
  );

  const tools = document.createElement("div");
  tools.className = "item-card__tools";
  tools.setAttribute("data-owner-only", "");

  const editBtn = document.createElement("button");
  editBtn.className = "btn btn--ghost btn--icon";
  editBtn.type = "button";
  editBtn.dataset.action = "edit-item";
  editBtn.title = "Editar artículo";
  editBtn.setAttribute("aria-label", "Editar artículo");
  editBtn.appendChild(
    createSvg([
      { tag: "path", attrs: { d: "M12 20h9" } },
      { tag: "path", attrs: { d: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" } },
    ])
  );

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "btn btn--ghost btn--icon is-danger";
  deleteBtn.type = "button";
  deleteBtn.dataset.action = "delete-item";
  deleteBtn.title = "Eliminar artículo";
  deleteBtn.setAttribute("aria-label", "Eliminar artículo");
  deleteBtn.appendChild(
    createSvg([
      {
        tag: "path",
        attrs: {
          d: "M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6",
        },
      },
      { tag: "path", attrs: { d: "M10 11v6M14 11v6" } },
    ])
  );

  tools.append(editBtn, deleteBtn);
  footer.append(storeLink, tools);

  card.append(media, body, footer);
  applyItemDataToCard(card, item);
  return card;
}

function applyItemDataToCard(card, item) {
  card.dataset.id = String(item.id);
  card.dataset.title = item.title;
  card.dataset.description = item.description || "";
  card.dataset.price = String(item.price);
  card.dataset.url = item.url;
  card.dataset.image = item.image_url || "";

  const image = $(".item-card__img", card);
  if (image) {
    image.src = item.image_url || PLACEHOLDER_IMAGE;
    image.alt = item.title;
  }

  const priceTag = $(".price-tag", card);
  if (priceTag) priceTag.textContent = formatPrice(item.price);

  const title = $(".item-card__title", card);
  if (title) title.textContent = item.title;

  const description = $(".item-card__desc", card);
  if (description) description.textContent = item.description || "Sin descripción.";

  const storeLink = $(".item-card__footer a.btn", card);
  if (storeLink) {
    storeLink.href = /^https?:\/\//i.test(item.url) ? item.url : "#";
  }
}

/* --------------------------------------------------------------------------
   Vista: Mis wishlists (index.html)
   -------------------------------------------------------------------------- */

async function initWishlistsPage() {
  const params = new URLSearchParams(window.location.search);
  const sharedParam = params.get("list");
  if (sharedParam) {
    window.location.replace(buildWishlistHref(sharedParam));
    return;
  }

  bindLogoutButtons();

  const currentUser = await fetchAuthenticatedUser();
  if (!currentUser) {
    window.location.replace("login.html");
    return;
  }

  updateNavbarUser(currentUser, "0 listas");

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

  let editingCard = null;
  let pendingDelete = null;

  function cards() {
    return grid ? $$(".wishlist-card", grid) : [];
  }

  function refreshSummary() {
    const total = cards().length;
    const label = `${total} ${total === 1 ? "lista" : "listas"}`;
    if (countPill) countPill.textContent = label;
    if (userRole) userRole.textContent = label;
    if (emptyState) emptyState.hidden = total > 0;
  }

  function resetForm() {
    editingCard = null;
    form?.reset();
    if (modalTitle) modalTitle.textContent = "Nueva wishlist";
    if (modalSub) {
      modalSub.textContent =
        "Dale un nombre a la lista y, si quieres, una descripción breve.";
    }
    if (submitLabel) submitLabel.textContent = "Crear lista";
  }

  function fillForm(card) {
    editingCard = card;
    if (titleInput) titleInput.value = card.dataset.title ?? "";
    if (descriptionInput) descriptionInput.value = card.dataset.description ?? "";
    if (modalTitle) modalTitle.textContent = "Editar wishlist";
    if (modalSub) {
      modalSub.textContent = "Actualiza el nombre o la descripción de la lista.";
    }
    if (submitLabel) submitLabel.textContent = "Guardar cambios";
  }

  function updateCardInDom(card, wishlist) {
    card.dataset.title = wishlist.title;
    card.dataset.description = wishlist.description || "";

    const titleLink = $(".wishlist-card__title a", card);
    if (titleLink) titleLink.textContent = wishlist.title;

    const desc = $(".wishlist-card__desc", card);
    if (desc) {
      desc.textContent = wishlist.description || "Sin descripción por ahora.";
    }
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

  // Cargar wishlists del backend
  if (grid) grid.replaceChildren();
  try {
    const wishlists = await getMyWishlists();
    if (grid && Array.isArray(wishlists)) {
      wishlists.forEach((wishlist) => {
        grid.appendChild(createWishlistCardElement(wishlist));
      });
    }
  } catch (error) {
    if (error?.status === 401) {
      logout("login.html");
      return;
    }
    showToast(error?.message || "No se pudieron cargar tus wishlists.");
  }

  refreshSummary();

  /* Botones "Nueva wishlist" (cabecera y estado vacío). */
  $$('[data-new="wishlist"]').forEach((button) => {
    button.addEventListener("click", () => {
      resetForm();
      openDialog(modal);
    });
  });

  /* Abrir directamente el formulario de creación (p. ej. ?new=wishlist). */
  if (params.get("new") === "wishlist" && modal) {
    resetForm();
    openDialog(modal);
  }

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
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const title = titleInput?.value.trim() ?? "";
    const description = descriptionInput?.value.trim() ?? "";
    const submitBtn = $('button[type="submit"]', form);

    if (submitBtn) submitBtn.disabled = true;
    try {
      if (editingCard) {
        const wishlistId = Number(editingCard.dataset.id);
        const updated = await updateWishlist(wishlistId, { title, description });
        updateCardInDom(editingCard, updated);
        showToast("Wishlist actualizada.");
      } else if (grid) {
        const created = await createWishlist({ title, description });
        const card = createWishlistCardElement(created);
        grid.prepend(card);
        showToast("Wishlist creada.");
      }

      refreshSummary();
      closeDialog(modal);
      resetForm();
    } catch (error) {
      if (error?.status === 401) {
        logout("login.html");
        return;
      }
      showToast(error?.message || "No se pudo guardar la wishlist.");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });

  /* Eliminar. */
  document.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="delete-wishlist"]');
    if (!button) return;
    const card = button.closest(".wishlist-card");
    if (card) openDelete(card);
  });

  confirmButton?.addEventListener("click", async () => {
    if (!pendingDelete) {
      closeDialog(confirmModal);
      return;
    }

    const card = pendingDelete;
    const title = card.dataset.title;
    const wishlistId = Number(card.dataset.id);

    confirmButton.disabled = true;
    try {
      await deleteWishlist(wishlistId);
      card.remove();
      pendingDelete = null;
      showToast(`“${title}” eliminada.`);
      refreshSummary();
      closeDialog(confirmModal);
    } catch (error) {
      if (error?.status === 401) {
        logout("login.html");
        return;
      }
      showToast(error?.message || "No se pudo eliminar la wishlist.");
    } finally {
      confirmButton.disabled = false;
    }
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
}

/* --------------------------------------------------------------------------
   Vista: Detalle de wishlist y artículos (wishlist.html)
   -------------------------------------------------------------------------- */

async function initWishlistDetailPage() {
  const params = new URLSearchParams(window.location.search);
  const shareId = params.get("list")?.trim() || "";

  const grid = $("#item-grid");
  const countLabel = $("#item-count");
  const emptyState = $("#item-empty");
  const emptyTitle = $("h2", emptyState);
  const emptyText = $("p", emptyState);
  const searchInput = $("#item-search");

  const breadcrumbCurrent = $(".breadcrumb span:last-child");
  const breadcrumbRootLink = $(".breadcrumb a");
  const listTitleEl = $(".list-head__title");
  const listDescEl = $(".list-head__desc");
  const ownerInlineEl = $(".owner-inline");
  const headMetaItems = $$(".list-head__meta .meta-item");
  const shareUrlEl = $("#share-url");
  const createWishlistBtn = $("#create-my-wishlist");
  const backToListsBtn = $('.navbar a[aria-label="Volver a mis listas"]');

  if (grid) grid.replaceChildren();

  const currentUser = await fetchAuthenticatedUser();

  if (currentUser) {
    bindLogoutButtons();
  } else {
    updateNavbarUser(null);
    if (backToListsBtn) backToListsBtn.hidden = true;
    if (breadcrumbRootLink) {
      breadcrumbRootLink.href = "login.html";
      breadcrumbRootLink.lastChild.textContent = " Iniciar sesión";
    }
  }

  if (createWishlistBtn) {
    createWishlistBtn.href = currentUser
      ? "/?new=wishlist"
      : `login.html?next=${encodeURIComponent("/?new=wishlist")}`;
  }

  function renderWishlistNotFound(message) {
    document.body.dataset.viewMode = "visitor";
    if (listTitleEl) listTitleEl.textContent = "Wishlist no disponible";
    if (listDescEl) listDescEl.textContent = message;
    if (breadcrumbCurrent) breadcrumbCurrent.textContent = "No encontrada";
    if (ownerInlineEl) ownerInlineEl.hidden = true;
    headMetaItems.forEach((item) => {
      item.hidden = true;
    });
    const toolbar = $(".toolbar");
    if (toolbar) toolbar.hidden = true;
    const shareBtns = $$('[data-action="share"]');
    shareBtns.forEach((btn) => {
      btn.hidden = true;
    });
    if (emptyState) {
      emptyState.hidden = false;
      if (emptyTitle) emptyTitle.textContent = "No pudimos abrir esta lista";
      if (emptyText) emptyText.textContent = message;
    }
  }

  if (!shareId) {
    if (currentUser) {
      window.location.replace("/");
    } else {
      renderWishlistNotFound(
        "El enlace no incluye un identificador de lista (?list=...)."
      );
    }
    return;
  }

  let wishlist;
  try {
    wishlist = await getSharedWishlist(shareId);
  } catch (error) {
    const msg =
      error?.status === 404 || error?.status === 422
        ? "El enlace compartido no existe o la lista fue eliminada por su autor."
        : error?.message || "No se pudo cargar la wishlist.";
    renderWishlistNotFound(msg);
    return;
  }

  const isOwner = Boolean(
    currentUser &&
      currentUser.username.toLowerCase() ===
        String(wishlist.owner_username || "").toLowerCase()
  );

  // Configurar modo de vista y navbar
  document.body.dataset.viewMode = isOwner ? "owner" : "visitor";

  if (currentUser) {
    updateNavbarUser(
      currentUser,
      isOwner ? "Autor de la lista" : "Visitante"
    );
  }

  // Hidratar cabecera de la wishlist
  document.title = `${wishlist.title} · MyWishList`;
  if (breadcrumbCurrent) breadcrumbCurrent.textContent = wishlist.title;
  if (listTitleEl) listTitleEl.textContent = wishlist.title;
  if (listDescEl) {
    listDescEl.textContent =
      wishlist.description || "Lista de deseos compartida en MyWishList.";
  }

  if (ownerInlineEl) {
    const avatar = document.createElement("span");
    avatar.className = "user-chip__avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = getInitials(wishlist.owner_username);
    ownerInlineEl.replaceChildren(
      avatar,
      document.createTextNode(`Por @${wishlist.owner_username}`)
    );
  }

  const shareUrl = buildShareUrl(wishlist.share_id);
  if (shareUrlEl) shareUrlEl.textContent = shareUrl;
  $$('[data-action="share"]').forEach((btn) => {
    btn.dataset.share = shareUrl;
  });

  if (headMetaItems[1]) {
    headMetaItems[1].replaceChild(
      document.createTextNode(`Creada el ${formatDate(wishlist.created_at)}`),
      headMetaItems[1].lastChild
    );
  }

  // Renderizar artículos
  if (grid && Array.isArray(wishlist.items)) {
    wishlist.items.forEach((item) => {
      grid.appendChild(createItemCardElement(item));
    });
  }

  const modal = $("#item-modal");
  const form = $("#item-form");
  const modalTitle = $("#item-modal-title");
  const modalSub = $("#item-modal-sub");
  const submitLabel = $("#item-submit-label");
  const titleInput = $("#item-title");
  const priceInput = $("#item-price");
  const urlInput = $("#item-url");
  const imageInput = $("#item-image");
  const imageFileInput = $("#item-image-file");
  const imageFetchButton = $("#item-image-fetch");
  const imageUploadButton = $("#item-image-upload");
  const imageClearButton = $("#item-image-clear");
  const imageStatus = $("#item-image-status");
  const imagePreviewText = $("#item-image-preview-text");
  const descriptionInput = $("#item-description");
  const imagePreview = $("#item-image-preview");

  const confirmModal = $("#confirm-modal");
  const confirmTitle = $("#confirm-title");
  const confirmText = $("#confirm-text");
  const confirmButton = $("[data-confirm-delete]", confirmModal);

  let editingCard = null;
  let pendingDelete = null;

  function cards() {
    return grid ? $$(".item-card", grid) : [];
  }

  function refreshCount() {
    const all = cards();
    const visible = all.filter((card) => !card.hidden).length;
    const query = searchInput?.value.trim() ?? "";
    const totalLabel = `${all.length} ${all.length === 1 ? "artículo" : "artículos"}`;

    if (countLabel) {
      countLabel.textContent = query
        ? `${visible} de ${all.length} artículos`
        : totalLabel;
    }

    if (headMetaItems[0]) {
      headMetaItems[0].replaceChild(
        document.createTextNode(totalLabel),
        headMetaItems[0].lastChild
      );
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
            ? isOwner
              ? "Agrega tu primer artículo para empezar a llenar esta wishlist."
              : "El autor aún no ha agregado artículos a esta wishlist."
            : "Prueba con otro término de búsqueda.";
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

      const haystack =
        `${card.dataset.title ?? ""} ${card.dataset.description ?? ""}`.toLowerCase();
      card.hidden = !haystack.includes(query);
    });

    refreshCount();
  }

  searchInput?.addEventListener("input", filterCards);

  function isUsableImage(value) {
    return (
      /^https?:\/\//i.test(value) ||
      /^\/media\/[0-9a-f-]+\.webp$/i.test(value)
    );
  }

  function applyImagePreview(value) {
    const normalized = isUsableImage(value ?? "") ? value.trim() : "";
    if (imagePreview) imagePreview.src = normalized || PREVIEW_IMAGE;
    if (imageClearButton) imageClearButton.hidden = !normalized;
    if (imagePreviewText) {
      imagePreviewText.textContent = normalized
        ? "Vista previa de la imagen."
        : "Sin imagen. La tarjeta usará una ilustración de respaldo.";
    }
  }

  function setImageValue(value, message) {
    const normalized = isUsableImage(value ?? "") ? value.trim() : "";
    if (imageInput) imageInput.value = normalized;
    applyImagePreview(normalized);
    if (message && imageStatus) imageStatus.textContent = message;
  }

  /* Enlace pegado a mano: solo se previsualiza, sin reescribir el campo. */
  imageInput?.addEventListener("input", () => {
    const value = imageInput.value.trim();
    applyImagePreview(value);
    if (imageStatus) {
      imageStatus.textContent = isUsableImage(value)
        ? "Enlace de imagen listo."
        : "Pega un enlace http(s) de imagen, o usa los botones.";
    }
  });

  async function handleImageFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      showToast("Elige un archivo de imagen.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast("La imagen no puede pesar más de 5 MB.");
      return;
    }

    if (imageUploadButton) imageUploadButton.disabled = true;
    if (imageStatus) imageStatus.textContent = "Comprimiendo y subiendo la foto…";

    try {
      const data = await uploadProductImage(file);
      setImageValue(
        data?.image_url ?? "",
        "Foto lista y guardada en el servidor."
      );
    } catch (error) {
      if (error?.status === 401) {
        logout("login.html");
        return;
      }
      if (imageStatus) imageStatus.textContent = "No se pudo subir la foto.";
      showToast(error?.message || "No se pudo subir la foto.");
    } finally {
      if (imageUploadButton) imageUploadButton.disabled = false;
    }
  }

  imageFetchButton?.addEventListener("click", async () => {
    const url = urlInput?.value.trim() ?? "";
    if (!url) {
      urlInput?.focus();
      showToast("Primero pega el enlace del producto.");
      return;
    }

    const originalLabel = imageFetchButton.textContent;
    imageFetchButton.disabled = true;
    imageFetchButton.textContent = "Buscando…";
    if (imageStatus) imageStatus.textContent = "Buscando la imagen en el enlace…";

    try {
      const data = await fetchProductImage(url);
      if (data?.image_url) {
        setImageValue(data.image_url, "Imagen encontrada en el enlace del producto.");
      } else if (imageStatus) {
        imageStatus.textContent =
          "No se encontró una imagen en ese enlace. Puedes subir una foto.";
      }
    } catch (error) {
      if (error?.status === 401) {
        logout("login.html");
        return;
      }
      if (imageStatus) {
        imageStatus.textContent =
          "No se pudo leer el enlace. Puedes subir una foto.";
      }
      showToast(error?.message || "No se pudo buscar la imagen.");
    } finally {
      imageFetchButton.disabled = false;
      imageFetchButton.textContent = originalLabel;
    }
  });

  imageUploadButton?.addEventListener("click", () => imageFileInput?.click());

  imageFileInput?.addEventListener("change", async () => {
    const file = imageFileInput.files?.[0];
    if (file) await handleImageFile(file);
    imageFileInput.value = "";
  });

  imageClearButton?.addEventListener("click", () => {
    setImageValue("", "Imagen quitada. La tarjeta usará la ilustración de respaldo.");
  });

  /* Pegar una imagen copiada o una captura de pantalla con Ctrl+V. */
  modal?.addEventListener("paste", (event) => {
    const items = [...(event.clipboardData?.items ?? [])];
    const imageItem = items.find((item) => item.type.startsWith("image/"));
    if (!imageItem) return;
    const file = imageItem.getAsFile();
    if (!file) return;
    event.preventDefault();
    handleImageFile(file);
  });

  function resetForm() {
    editingCard = null;
    form?.reset();
    setImageValue(
      "",
      "Pega el enlace del producto y pulsa «Buscar imagen», pega el enlace directo de la imagen, o sube una foto."
    );
    if (modalTitle) modalTitle.textContent = "Nuevo artículo";
    if (modalSub) {
      modalSub.textContent =
        "Completa los datos del producto que quieres guardar.";
    }
    if (submitLabel) submitLabel.textContent = "Guardar artículo";
  }

  function fillForm(card) {
    editingCard = card;
    if (titleInput) titleInput.value = card.dataset.title ?? "";
    if (priceInput) priceInput.value = card.dataset.price ?? "";
    if (urlInput) urlInput.value = card.dataset.url ?? "";
    if (descriptionInput) descriptionInput.value = card.dataset.description ?? "";
    setImageValue(card.dataset.image ?? "");
    if (modalTitle) modalTitle.textContent = "Editar artículo";
    if (modalSub) modalSub.textContent = "Actualiza los datos del artículo.";
    if (submitLabel) submitLabel.textContent = "Guardar cambios";
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

  if (isOwner) {
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

    /* Formulario de artículo (Crear / Editar). */
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;

      const imageValue = imageInput?.value.trim() ?? "";
      if (imageValue && !isUsableImage(imageValue)) {
        imageInput?.focus();
        showToast("El enlace de la imagen debe empezar por http:// o https://.");
        return;
      }

      const payload = {
        title: titleInput?.value.trim() ?? "",
        price: priceInput?.value.trim() ?? "0",
        url: urlInput?.value.trim() ?? "",
        image_url: imageValue || null,
        description: descriptionInput?.value.trim() ?? "",
      };

      const submitBtn = $('button[type="submit"]', form);
      if (submitBtn) submitBtn.disabled = true;

      try {
        if (editingCard) {
          const itemId = Number(editingCard.dataset.id);
          const updated = await updateItem(wishlist.id, itemId, payload);
          applyItemDataToCard(editingCard, updated);
          showToast("Artículo actualizado.");
        } else if (grid) {
          const created = await createItem(wishlist.id, payload);
          const card = createItemCardElement(created);
          grid.prepend(card);
          showToast("Artículo agregado.");
        }

        closeDialog(modal);
        resetForm();
        filterCards();
      } catch (error) {
        if (error?.status === 401) {
          logout("login.html");
          return;
        }
        showToast(error?.message || "No se pudo guardar el artículo.");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    /* Eliminar un artículo. */
    document.addEventListener("click", (event) => {
      const button = event.target.closest('[data-action="delete-item"]');
      if (!button) return;
      const card = button.closest(".item-card");
      if (card) openDelete(card);
    });

    confirmButton?.addEventListener("click", async () => {
      if (!pendingDelete) {
        closeDialog(confirmModal);
        return;
      }

      const card = pendingDelete;
      const title = card.dataset.title;
      const itemId = Number(card.dataset.id);

      confirmButton.disabled = true;
      try {
        await deleteItem(wishlist.id, itemId);
        card.remove();
        pendingDelete = null;
        showToast(`“${title}” eliminado.`);
        filterCards();
        closeDialog(confirmModal);
      } catch (error) {
        if (error?.status === 401) {
          logout("login.html");
          return;
        }
        showToast(error?.message || "No se pudo eliminar el artículo.");
      } finally {
        confirmButton.disabled = false;
      }
    });
  }

  /* Compartir (disponible para dueño y visitante). */
  document.addEventListener("click", async (event) => {
    const button = event.target.closest('[data-action="share"]');
    if (!button) return;

    const copied = await copyToClipboard(button.dataset.share ?? shareUrl);
    showToast(
      copied
        ? "Enlace copiado al portapapeles."
        : "No se pudo copiar el enlace en este navegador."
    );
  });

  refreshCount();
}

/* --------------------------------------------------------------------------
   Arranque de la aplicación
   -------------------------------------------------------------------------- */

function init() {
  initDialogs();

  switch (document.body.dataset.page) {
    case "login":
      initLoginPage({ showToast });
      break;
    case "wishlists":
      initWishlistsPage();
      break;
    case "wishlist":
      initWishlistDetailPage();
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
