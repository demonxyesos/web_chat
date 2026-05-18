import { useCallback, useEffect, useState } from "react";
import {
  LOBBY_PEER_USERNAME,
  deleteMessage,
  deleteUser,
  fetchAdminMessages,
  fetchUsers
} from "./api";

const PAGE_SIZE = 50;

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

export function AdminPanel({ onClose, currentUserId }) {
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [hasMoreMessages, setHasMoreMessages] = useState(true);

  const loadInitial = useCallback(async () => {
    setError("");
    setLoading(true);
    setHasMoreMessages(true);
    try {
      const [u, m] = await Promise.all([
        fetchUsers(),
        fetchAdminMessages(PAGE_SIZE, null)
      ]);
      setUsers(u);
      setMessages(m);
      setHasMoreMessages(m.length >= PAGE_SIZE);
    } catch (e) {
      console.error(e);
      setError("Ошибка загрузки данных админа");
      setUsers([]);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  async function handleLoadMoreMessages() {
    if (loadingMore || !hasMoreMessages || messages.length === 0) return;
    const oldestId = messages.reduce((min, m) => Math.min(min, m.id), messages[0].id);
    setLoadingMore(true);
    try {
      const batch = await fetchAdminMessages(PAGE_SIZE, oldestId);
      if (batch.length === 0) {
        setHasMoreMessages(false);
        return;
      }
      setMessages((prev) => mergeMessagesById(batch, prev));
      if (batch.length < PAGE_SIZE) setHasMoreMessages(false);
    } catch (e) {
      console.error(e);
      setError("Не удалось подгрузить сообщения");
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleDeleteMessage(id) {
    if (!window.confirm("Удалить это сообщение для всех?")) return;
    try {
      await deleteMessage(id);
      setMessages((prev) => prev.filter((m) => m.id !== id));
    } catch (e) {
      console.error(e);
      alert("Не удалось удалить сообщение");
    }
  }

  async function handleDeleteUser(u) {
    if (u.id === currentUserId) return;
    if (u.username === LOBBY_PEER_USERNAME) return;
    if (!window.confirm(`Удалить пользователя ${u.name} (@${u.username})?`)) return;
    try {
      await deleteUser(u.id);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
    } catch (e) {
      console.error(e);
      const detail = e?.response?.data?.detail;
      alert(typeof detail === "string" ? detail : "Не удалось удалить пользователя");
    }
  }

  return (
    <div className="admin-panel admin-panel--drawer">
      <div className="admin-panel-header">
        <h2 id="admin-panel-title" className="admin-panel-title">
          Админ-панель
        </h2>
        <button type="button" className="admin-panel-close" onClick={onClose} aria-label="Закрыть">
          ×
        </button>
      </div>

      <div className="admin-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "users"}
          className={`admin-tab${tab === "users" ? " admin-tab--active" : ""}`}
          onClick={() => setTab("users")}
        >
          Пользователи
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "messages"}
          className={`admin-tab${tab === "messages" ? " admin-tab--active" : ""}`}
          onClick={() => setTab("messages")}
        >
          Сообщения
        </button>
      </div>

      {loading && <p className="admin-panel-loading">Загрузка...</p>}
      {error && <p className="error admin-panel-error">{error}</p>}

      {!loading && tab === "users" && (
        <div className="admin-tab-panel">
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Имя</th>
                  <th>Логин</th>
                  <th>Роль</th>
                  <th>Регистрация</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const canDelete =
                    u.id !== currentUserId && u.username !== LOBBY_PEER_USERNAME;
                  return (
                    <tr key={u.id}>
                      <td>{u.name}</td>
                      <td>
                        <code>{u.username}</code>
                      </td>
                      <td>{u.role}</td>
                      <td>{formatDate(u.created_at)}</td>
                      <td>
                        {canDelete ? (
                          <button type="button" className="admin-row-action" onClick={() => handleDeleteUser(u)}>
                            Удалить
                          </button>
                        ) : (
                          <span className="admin-muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && tab === "messages" && (
        <div className="admin-tab-panel admin-tab-panel--messages">
          {hasMoreMessages && (
            <div className="admin-load-more-row">
              <button type="button" onClick={handleLoadMoreMessages} disabled={loadingMore}>
                {loadingMore ? "Загрузка…" : "Загрузить старые"}
              </button>
            </div>
          )}
          <ul className="admin-message-list">
            {messages.map((m) => (
              <li key={m.id}>
                <div className="admin-msg-body">
                  <div className="admin-msg-meta">
                    <span className="admin-msg-id">#{m.id}</span>
                    <span className="admin-msg-chat">чат {m.chat_id}</span>
                  </div>
                  <div>
                    <strong>{m.author?.name ?? m.author?.username}</strong>
                    {" → "}
                    <span>{m.recipient?.name ?? m.recipient?.username}</span>: {m.content}
                  </div>
                </div>
                <button type="button" onClick={() => handleDeleteMessage(m.id)}>
                  Удалить
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function mergeMessagesById(olderBatch, prevAsc) {
  const map = new Map();
  for (const m of olderBatch) map.set(m.id, m);
  for (const m of prevAsc) map.set(m.id, m);
  return Array.from(map.values()).sort((a, b) => a.id - b.id);
}
