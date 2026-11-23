/* ==========================================================================
   MyWishList — Cliente HTTP y gestión de token JWT (api.js)
   --------------------------------------------------------------------------
   Centraliza todas las llamadas `fetch` a la API REST de FastAPI, adjuntando
   el token Bearer cuando existe y normalizando los mensajes de error.
   ========================================================================== */

const TOKEN_STORAGE_KEY = "mywishlist_token";

/* --------------------------------------------------------------------------
   Almacenamiento del token JWT
   -------------------------------------------------------------------------- */

export function getToken() {
  try {
    return (
      window.localStorage.getItem(TOKEN_STORAGE_KEY) ||
      window.sessionStorage.getItem(TOKEN_STORAGE_KEY) ||
      null
    );
  } catch {
    return null;
  }
}

export function setToken(token, remember = true) {
  try {
    clearToken();
    const storage = remember ? window.localStorage : window.sessionStorage;
    storage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    /* Si el navegador bloquea storage, se ignora silenciosamente. */
  }
}

export function clearToken() {
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* Ignorado. */
  }
}

/* --------------------------------------------------------------------------
   Error HTTP enriquecido y cliente fetch
   -------------------------------------------------------------------------- */

export class ApiError extends Error {
  constructor(message, status, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function formatValidationErrors(detail) {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) => {
        if (!entry || typeof entry !== "object") return null;
        const field = Array.isArray(entry.loc)
          ? entry.loc.filter((part) => part !== "body").join(".")
          : "";
        const msg = entry.msg || "Valor inválido";
        return field ? `${field}: ${msg}` : msg;
      })
      .filter(Boolean);

    if (messages.length > 0) return messages.join(" · ");
  }

  return "Los datos enviados no son válidos.";
}

export async function apiFetch(endpoint, options = {}) {
  const {
    method = "GET",
    body,
    headers: customHeaders = {},
    auth = true,
  } = options;

  const headers = new Headers(customHeaders);
  headers.set("Accept", "application/json");

  if (auth) {
    const token = getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  let payload = body;
  if (body !== undefined && body !== null && !(body instanceof FormData)) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (typeof body !== "string") {
      payload = JSON.stringify(body);
    }
  }

  let response;
  try {
    response = await window.fetch(endpoint, {
      method,
      headers,
      body: payload,
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar con el servidor. Verifica tu conexión.",
      0
    );
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const detail = data?.detail ?? null;
    const message =
      response.status === 422
        ? formatValidationErrors(detail)
        : typeof detail === "string"
          ? detail
          : `Error HTTP ${response.status}`;

    throw new ApiError(message, response.status, detail);
  }

  return data;
}

/* --------------------------------------------------------------------------
   Endpoints de Autenticación (/api/auth)
   -------------------------------------------------------------------------- */

export async function registerUser({ username, password }) {
  return apiFetch("/api/auth/register", {
    method: "POST",
    auth: false,
    body: { username, password },
  });
}

export async function loginUser({ username, password, remember = true }) {
  const data = await apiFetch("/api/auth/login", {
    method: "POST",
    auth: false,
    body: { username, password },
  });
  if (data?.access_token) {
    setToken(data.access_token, remember);
  }
  return data;
}

export async function getCurrentUser() {
  return apiFetch("/api/auth/me");
}

/* --------------------------------------------------------------------------
   Endpoints de Wishlists (/api/wishlists)
   -------------------------------------------------------------------------- */

export async function getMyWishlists() {
  return apiFetch("/api/wishlists/mine");
}

export async function createWishlist({ title, description }) {
  return apiFetch("/api/wishlists", {
    method: "POST",
    body: {
      title,
      description: description || null,
    },
  });
}

export async function updateWishlist(wishlistId, { title, description }) {
  return apiFetch(`/api/wishlists/${encodeURIComponent(wishlistId)}`, {
    method: "PUT",
    body: {
      title,
      description: description || null,
    },
  });
}

export async function deleteWishlist(wishlistId) {
  return apiFetch(`/api/wishlists/${encodeURIComponent(wishlistId)}`, {
    method: "DELETE",
  });
}

export async function getSharedWishlist(shareId) {
  return apiFetch(`/api/wishlists/${encodeURIComponent(shareId)}`, {
    auth: false,
  });
}

/* --------------------------------------------------------------------------
   Endpoints de Artículos (/api/wishlists/{wishlist_id}/items)
   -------------------------------------------------------------------------- */

export async function createItem(
  wishlistId,
  { title, price, url, image_url, description }
) {
  return apiFetch(
    `/api/wishlists/${encodeURIComponent(wishlistId)}/items`,
    {
      method: "POST",
      body: {
        title,
        price,
        url,
        image_url,
        description: description || null,
      },
    }
  );
}

export async function updateItem(
  wishlistId,
  itemId,
  { title, price, url, image_url, description }
) {
  return apiFetch(
    `/api/wishlists/${encodeURIComponent(wishlistId)}/items/${encodeURIComponent(itemId)}`,
    {
      method: "PUT",
      body: {
        title,
        price,
        url,
        image_url,
        description: description || null,
      },
    }
  );
}

export async function deleteItem(wishlistId, itemId) {
  return apiFetch(
    `/api/wishlists/${encodeURIComponent(wishlistId)}/items/${encodeURIComponent(itemId)}`,
    {
      method: "DELETE",
    }
  );
}
