import axios from "axios";

const API_HOST = import.meta.env.VITE_API_HOST || window.location.hostname;
const API_PORT = import.meta.env.VITE_API_PORT || "8000";
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (import.meta.env.DEV ? `http://${API_HOST}:${API_PORT}` : window.location.origin);

function coerceChatList(data) {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object" && Array.isArray(data.chats)) return data.chats;
  return [];
}

export const LOBBY_PEER_USERNAME = "__lobby__";

export function getStoredToken() {
  return window.localStorage.getItem("access_token") || "";
}

export function setStoredToken(token) {
  if (token) {
    window.localStorage.setItem("access_token", token);
  } else {
    window.localStorage.removeItem("access_token");
  }
}

export function clearChatsCacheForUser(userId) {
  if (userId == null) return;
  try {
    window.localStorage.removeItem(`chats_cache_user_${userId}`);
    window.localStorage.removeItem(`recent_chats_user_${userId}`);
  } catch {
    // ignore
  }
}

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json"
  }
});

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = String(error?.config?.url || "");
    if (error?.response?.status === 401 && (url.includes("/users/me") || url.includes("/auth/"))) {
      setStoredToken("");
    }
    return Promise.reject(error);
  }
);

export async function createMessage(payload) {
  const { data } = await api.post("/messages", payload);
  return data;
}

export async function registerUser(username, name, password, passwordConfirm) {
  return api.post("/auth/register", {
    username,
    name,
    password,
    password_confirm: passwordConfirm
  });
}

export async function loginUser(username, password) {
  const params = new URLSearchParams();
  params.set("username", username);
  params.set("password", password);
  params.set("grant_type", "password");
  const { data } = await axios.post(`${API_BASE}/auth/token`, params.toString(), {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    }
  });
  setStoredToken(data.access_token);
  return data;
}

export async function fetchMe() {
  const { data } = await api.get("/users/me");
  return data;
}

export async function searchUsers(username) {
  const { data } = await api.get("/users/search", { params: { username } });
  return data;
}

export async function fetchChatMessages(username, limit = 50) {
  const { data } = await api.get(`/chats/${encodeURIComponent(username)}/messages`, {
    params: { limit }
  });
  return data;
}

export async function fetchChats() {
  const { data } = await api.get("/chats");
  return coerceChatList(data);
}

export async function deleteChat(chatId) {
  await api.delete(`/chats/${chatId}`);
}

export async function fetchUsers() {
  const { data } = await api.get("/admin/users");
  return data;
}

export async function fetchAdminMessages(limit = 50, beforeId = null) {
  const params = { limit };
  if (beforeId != null) params.before_id = beforeId;
  const { data } = await api.get("/admin/messages", { params });
  return data;
}

export async function deleteMessage(id) {
  await api.delete(`/admin/messages/${id}`);
}

export async function deleteUser(userId) {
  await api.delete(`/admin/users/${userId}`);
}

export async function updateMeName(name) {
  const { data } = await api.patch("/users/me", { name });
  return data;
}

export async function deleteMyAccount() {
  await api.delete("/users/me");
}

export async function updateMessage(messageId, content) {
  const { data } = await api.patch(`/messages/${messageId}`, { content });
  return data;
}

export async function deleteMyMessage(messageId) {
  await api.delete(`/messages/${messageId}`);
}

export async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export function createChatWebSocket() {
  const token = getStoredToken();
  if (!token) {
    throw new Error("No token");
  }
  let apiUrl;
  try {
    apiUrl = new URL(API_BASE);
  } catch {
    apiUrl = new URL(`http://${API_HOST}:${API_PORT}`);
  }
  const wsProtocol = apiUrl.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(
    `${wsProtocol}://${apiUrl.host}/ws/chat?token=${encodeURIComponent(token)}`
  );
  return ws;
}

