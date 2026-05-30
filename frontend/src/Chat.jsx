import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE,
  LOBBY_PEER_USERNAME,
  createChatWebSocket,
  createMessage,
  deleteChat,
  deleteMyAccount,
  deleteMyMessage,
  fetchChatMessages,
  fetchChats,
  searchUsers,
  setStoredToken,
  updateMeName,
  updateMessage,
  uploadFile
} from "./api";
import { AdminPanel } from "./AdminPanel";

function storageKeyForUser(userId) {
  return `recent_chats_user_${userId}`;
}

function chatsCacheKeyForUser(userId) {
  return `chats_cache_user_${userId}`;
}

function mergeMessagesById(prev, incoming) {
  const map = new Map(prev.map((m) => [m.id, m]));
  for (const m of incoming) map.set(m.id, m);
  return Array.from(map.values()).sort((a, b) => a.id - b.id);
}

const MESSAGE_LOG_UNIX_TIME = false;

const CHAT_EMPTY_BLURB = {
  lead: "Asyncgram. Место силы AsyncGroup.",
  body:
    "Единое пространство для координации топовых экспертов в сфере информационной безопасности. Когда безопасность — это не работа, а цифровое искусство, инструменты общения должны быть безупречными.",
};

const CRT_STATUS_LINES = [
  "[init] chat_session: ok tty=pts/0",
  "[net] lo: 127.0.0.1/8 mtu 65536 qdisc noop state UNKNOWN",
  "[kth] load avg: 0.07 0.04 0.01 tasks: 42/128",
  "[sys] uptime 03:41:22 | idle=99.2%",
  "[dmesg] random: crng init done",
];

function formatMessageLogTime(iso) {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  if (MESSAGE_LOG_UNIX_TIME) return String(Math.floor(d.getTime() / 1000));
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function wsMessageTargetsOpenThread(msg, openChatId, activePeer, lobbyUser, me) {
  if (!activePeer || msg.chat_id == null) return false;
  if (openChatId != null && msg.chat_id === openChatId) return true;
  const a = msg.author?.username;
  const r = msg.recipient?.username;
  if (!a || !r) return false;
  if (activePeer === lobbyUser && (r === lobbyUser || a === lobbyUser)) {
    return true;
  }
  if (activePeer === lobbyUser) return false;
  if (!me) return false;
  return (a === me && r === activePeer) || (a === activePeer && r === me);
}

const FULL_CHATS_REFRESH_MS = 2500;

function buildUserFromWsPart(u, fallbackIso) {
  if (!u || typeof u.id !== "number") return null;
  return {
    id: u.id,
    username: u.username,
    name: u.name ?? u.username,
    role: u.role ?? "user",
    created_at: u.created_at ?? fallbackIso,
  };
}

function upsertChatListFromIncomingMessage(prev, msg, currentUser) {
  if (!msg.chat_id) return prev;
  const me = currentUser.username;
  const a = msg.author?.username;
  const r = msg.recipient?.username;
  if (!a || !r) return prev;
  const created = typeof msg.created_at === "string" ? msg.created_at : new Date().toISOString();
  const authorFull = buildUserFromWsPart(msg.author, created);
  const recipientFull = buildUserFromWsPart(msg.recipient, created);
  if (!authorFull || !recipientFull) return prev;
  const isGlobalRoom =
    recipientFull.username === LOBBY_PEER_USERNAME || authorFull.username === LOBBY_PEER_USERNAME;
  const peer = isGlobalRoom
    ? recipientFull.username === LOBBY_PEER_USERNAME
      ? recipientFull
      : authorFull
    : a === me
      ? recipientFull
      : authorFull;
  const lastMessage = {
    ...msg,
    created_at: created,
    edited_at: msg.edited_at ?? null,
    reply_to: msg.reply_to ?? null,
    author: authorFull,
    recipient: recipientFull,
  };
  const updatedChat = {
    id: msg.chat_id,
    peer,
    updated_at: created,
    last_message: lastMessage,
    is_global: isGlobalRoom,
  };
  const rest = prev.filter((c) => c.id !== msg.chat_id);
  return [updatedChat, ...rest];
}

function patchChatListAfterEdit(prev, msg) {
  const cid = msg.chat_id;
  if (!cid) return prev;
  return prev.map((c) => {
    if (c.id !== cid) return c;
    if (!c.last_message || c.last_message.id !== msg.id) {
      return { ...c, updated_at: msg.edited_at || c.updated_at };
    }
    return {
      ...c,
      updated_at: msg.edited_at || c.updated_at,
      last_message: { ...c.last_message, content: msg.content, edited_at: msg.edited_at },
    };
  });
}

function patchChatListAfterDelete(prev, msg) {
  const cid = msg.chat_id;
  const mid = msg.id;
  if (!cid || mid == null) return prev;
  return prev.map((c) => {
    if (c.id !== cid) return c;
    if (!c.last_message || c.last_message.id !== mid) return c;
    return { ...c, last_message: null };
  });
}

export function Chat({ currentUser, onLogout }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [peerQuery, setPeerQuery] = useState("");
  const [peerResults, setPeerResults] = useState([]);
  const [activePeer, setActivePeer] = useState("");
  const [serverChats, setServerChats] = useState([]);
  const serverChatsRef = useRef(serverChats);
  const [unreadByPeer, setUnreadByPeer] = useState({});
  const [status, setStatus] = useState("Подключение...");
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");
  const [replyTo, setReplyTo] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsName, setSettingsName] = useState(currentUser.name || "");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [confirmDeletePeer, setConfirmDeletePeer] = useState(null);
  const [deleteCountdown, setDeleteCountdown] = useState(0);
  const [crtStatusIdx, setCrtStatusIdx] = useState(0);
  const [adminPanelOpen, setAdminPanelOpen] = useState(false);
  const [isNarrowViewport, setIsNarrowViewport] = useState(false);
  const [sidebarDrawerOpen, setSidebarDrawerOpen] = useState(false);
  const wsRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const bottomRef = useRef(null);
  const activePeerRef = useRef("");
  const currentUserRef = useRef(currentUser);
  const lastMessageIdRef = useRef(0);
  const activeChatIdRef = useRef(null);
  const chatsRefreshTimerRef = useRef(null);
  const prevMessagesLenRef = useRef(0);
  const prevLastMsgIdRef = useRef(null);
  const chatHeaderRef = useRef(null);
  const chatContainerRef = useRef(null);

  useLayoutEffect(() => {
    const headerEl = chatHeaderRef.current;
    const containerEl = chatContainerRef.current;
    if (!headerEl || !containerEl) return;

    function syncDrawerTop() {
      if (!window.matchMedia("(max-width: 768px)").matches) {
        containerEl.style.removeProperty("--chat-drawer-top");
        return;
      }
      const h = Math.ceil(headerEl.getBoundingClientRect().height);
      containerEl.style.setProperty("--chat-drawer-top", `${h}px`);
    }

    syncDrawerTop();
    const ro = new ResizeObserver(syncDrawerTop);
    ro.observe(headerEl);
    window.addEventListener("resize", syncDrawerTop);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", syncDrawerTop);
    };
  }, [
    isNarrowViewport,
    currentUser.name,
    currentUser.role,
    status,
    sidebarDrawerOpen,
    settingsOpen,
    adminPanelOpen
  ]);

  const sortedServerChats = useMemo(() => {
    const arr = [...serverChats];
    arr.sort((a, b) => {
      const ag = a.is_global || a.peer?.username === LOBBY_PEER_USERNAME ? 1 : 0;
      const bg = b.is_global || b.peer?.username === LOBBY_PEER_USERNAME ? 1 : 0;
      if (ag !== bg) return bg - ag;
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });
    return arr;
  }, [serverChats]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) return;
    const id = window.setInterval(
      () => setCrtStatusIdx((i) => (i + 1) % CRT_STATUS_LINES.length),
      5500
    );
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    lastMessageIdRef.current = 0;
    prevMessagesLenRef.current = 0;
    prevLastMsgIdRef.current = null;
  }, [activePeer]);

  useLayoutEffect(() => {
    serverChatsRef.current = serverChats;
    currentUserRef.current = currentUser;
    activePeerRef.current = activePeer;
    activeChatIdRef.current =
      serverChats.find((c) => c.peer?.username === activePeer)?.id ?? null;
  }, [serverChats, activePeer, currentUser]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const sync = () => {
      const narrow = mq.matches;
      setIsNarrowViewport(narrow);
      if (!narrow) setSidebarDrawerOpen(false);
    };
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!sidebarDrawerOpen) return;
    function onKey(e) {
      if (e.key === "Escape") setSidebarDrawerOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sidebarDrawerOpen]);

  useEffect(() => {
    if (!isNarrowViewport || !sidebarDrawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isNarrowViewport, sidebarDrawerOpen]);

  function selectPeer(username) {
    setActivePeer(username);
    setConfirmDeletePeer(null);
    setDeleteCountdown(0);
    if (window.matchMedia("(max-width: 768px)").matches) setSidebarDrawerOpen(false);
  }

  function closeActiveChat() {
    setActivePeer("");
    setConfirmDeletePeer(null);
    setDeleteCountdown(0);
    if (isNarrowViewport) setSidebarDrawerOpen(false);
  }

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(chatsCacheKeyForUser(currentUser.id));
      if (!raw) return;
      const cached = JSON.parse(raw);
      if (Array.isArray(cached)) {
        setServerChats(cached);
      }
    } catch {
    }
  }, [currentUser.id]);

  useEffect(() => {
    let cancelled = false;
    async function loadChats() {
      try {
        const chats = await fetchChats();
        if (cancelled) return;
        setServerChats(chats);
        try {
          window.localStorage.setItem(chatsCacheKeyForUser(currentUser.id), JSON.stringify(chats));
        } catch {
        }
      } catch (e) {
        console.error(e);
        if (!cancelled) setServerChats([]);
      }
    }
    loadChats();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser.id]);

  function persistChatsCache(chats) {
    try {
      const uid = currentUserRef.current?.id ?? currentUser.id;
      window.localStorage.setItem(chatsCacheKeyForUser(uid), JSON.stringify(chats));
    } catch {
    }
  }

  function scheduleFullChatsRefresh() {
    if (chatsRefreshTimerRef.current != null) return;
    chatsRefreshTimerRef.current = window.setTimeout(async () => {
      chatsRefreshTimerRef.current = null;
      try {
        const chats = await fetchChats();
        setServerChats(chats);
        persistChatsCache(chats);
      } catch {
      }
    }, FULL_CHATS_REFRESH_MS);
  }

  useEffect(
    () => () => {
      if (chatsRefreshTimerRef.current != null) {
        window.clearTimeout(chatsRefreshTimerRef.current);
        chatsRefreshTimerRef.current = null;
      }
    },
    []
  );

  useEffect(() => {
    if (!adminPanelOpen) return;
    function onKey(e) {
      if (e.key === "Escape") setAdminPanelOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [adminPanelOpen]);

  useEffect(() => {
    function onVisibility() {
      if (document.visibilityState === "visible") scheduleFullChatsRefresh();
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;

    function connect() {
      try {
        const ws = createChatWebSocket();
        wsRef.current = ws;
        setStatus("Подключено");

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            const me = currentUserRef.current?.username;
            const activeChatId = activeChatIdRef.current;
            const openChatId =
              activeChatId ??
              serverChatsRef.current.find((c) => c.peer?.username === activePeerRef.current)?.id ??
              null;

            const threadOpenForDeleteOrEdit =
              (openChatId != null && msg.chat_id === openChatId) ||
              serverChatsRef.current.some(
                (c) => c.id === msg.chat_id && c.peer?.username === activePeerRef.current
              );

            if (msg.type === "message_deleted") {
              if (threadOpenForDeleteOrEdit) {
                setMessages((prev) => prev.filter((m) => m.id !== msg.id));
              }
              setServerChats((prev) => patchChatListAfterDelete(prev, msg));
              scheduleFullChatsRefresh();
              return;
            }
            if (msg.type === "message_edited") {
              if (threadOpenForDeleteOrEdit || wsMessageTargetsOpenThread(msg, openChatId, activePeerRef.current, LOBBY_PEER_USERNAME, me)) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === msg.id
                      ? {
                          ...m,
                          content: msg.content,
                          edited_at: msg.edited_at
                        }
                      : m
                  )
                );
              }
              setServerChats((prev) => patchChatListAfterEdit(prev, msg));
              scheduleFullChatsRefresh();
              return;
            }

            const a = msg.author?.username;
            const r = msg.recipient?.username;
            const other = a === me ? r : a;

            if (other) {
              setServerChats((prev) =>
                upsertChatListFromIncomingMessage(prev, msg, currentUserRef.current)
              );
              scheduleFullChatsRefresh();

              const isGlobalMsg =
                msg.chat_id != null &&
                (r === LOBBY_PEER_USERNAME || a === LOBBY_PEER_USERNAME);
              if (isGlobalMsg) {
                if (activePeerRef.current !== LOBBY_PEER_USERNAME) {
                  setUnreadByPeer((prev) => ({
                    ...prev,
                    [LOBBY_PEER_USERNAME]: (prev[LOBBY_PEER_USERNAME] || 0) + 1
                  }));
                }
              } else if (other !== activePeerRef.current) {
                setUnreadByPeer((prev) => ({
                  ...prev,
                  [other]: (prev[other] || 0) + 1
                }));
              }
            }

            const appendToFeed = wsMessageTargetsOpenThread(
              msg,
              openChatId,
              activePeerRef.current,
              LOBBY_PEER_USERNAME,
              me
            );
            if (appendToFeed) {
              setMessages((prev) => mergeMessagesById(prev, [msg]));
              if (typeof msg.id === "number") lastMessageIdRef.current = msg.id;
            }
          } catch (e) {
            console.error("Bad WS message", e);
          }
        };

        ws.onopen = () => {
          setStatus("Подключено");
        };

        ws.onclose = () => {
          if (!active) return;
          setStatus("Отключено, попытка переподключения...");
          setTimeout(connect, 2000);
        };

        ws.onerror = () => {
          setStatus("Ошибка соединения");
        };
      } catch (e) {
        console.error(e);
        setStatus("Не удалось подключиться");
      }
    }

    connect();

    return () => {
      active = false;
      if (wsRef.current) {
        wsRef.current.close(1000);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!activePeer) return;
    let cancelled = false;
    let tick = 0;
    const interval = window.setInterval(async () => {
      if (cancelled || document.visibilityState === "hidden") return;
      tick += 1;
      const wsOpen = wsRef.current?.readyState === WebSocket.OPEN;
      if (wsOpen && tick % 10 !== 0) return;
      try {
        const history = await fetchChatMessages(activePeer, 50);
        if (cancelled) return;
        const list = Array.isArray(history) ? history : [];
        const lastId = list.length ? list[list.length - 1].id : 0;
        if (lastId && lastId !== lastMessageIdRef.current) {
          setMessages((prev) => mergeMessagesById(prev, list));
          lastMessageIdRef.current = Math.max(lastMessageIdRef.current, lastId);
          setUnreadByPeer((prev) => ({ ...prev, [activePeer]: 0 }));
        }
      } catch {
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [activePeer, fetchChatMessages]);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      const q = peerQuery.trim();
      if (!q) {
        setPeerResults([]);
        return;
      }
      try {
        const res = await searchUsers(q);
        if (!cancelled) setPeerResults(res);
      } catch (e) {
        console.error(e);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [peerQuery]);

  useEffect(() => {
    let cancelled = false;
    if (!activePeer) {
      setMessages([]);
      setPendingFile(null);
      return;
    }
    setMessages([]);

    async function loadHistory() {
      try {
        const history = await fetchChatMessages(activePeer, 50);
        if (cancelled) return;
        const list = Array.isArray(history) ? history : [];
        setMessages(mergeMessagesById([], list));
        if (list.length) {
          lastMessageIdRef.current = Math.max(
            lastMessageIdRef.current,
            list[list.length - 1].id
          );
        }
        setUnreadByPeer((prev) => ({ ...prev, [activePeer]: 0 }));
      } catch (e) {
        console.error(e);
      }
    }
    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [activePeer]);

  useEffect(() => {
    setEditingId(null);
    setEditText("");
    setReplyTo(null);
  }, [activePeer]);

  useEffect(() => {
    const last = messages[messages.length - 1];
    const lastId = last?.id ?? null;
    const len = messages.length;
    const shouldScroll =
      lastId != null &&
      (lastId !== prevLastMsgIdRef.current || len > prevMessagesLenRef.current);
    prevMessagesLenRef.current = len;
    prevLastMsgIdRef.current = lastId;
    if (!shouldScroll) return;
    const id = window.requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    });
    return () => window.cancelAnimationFrame(id);
  }, [messages]);

  async function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      alert("Файл слишком большой (макс. 10 МБ)");
      e.target.value = "";
      return;
    }
    try {
      setUploading(true);
      const result = await uploadFile(file);
      setPendingFile(result);
    } catch (err) {
      console.error(err);
      alert("Не удалось загрузить файл");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function sendMessage(e) {
    e.preventDefault();
    const text = input.trim();
    if (!activePeer) return;
    if (!text && !pendingFile) return;
    const payload = {
      content: text,
      to: activePeer,
      reply_to_id: replyTo ? replyTo.id : null,
    };
    if (pendingFile) {
      payload.file_url = pendingFile.file_url;
      payload.file_name = pendingFile.file_name;
      payload.file_type = pendingFile.file_type;
      payload.file_size = pendingFile.file_size;
    }
    createMessage(payload)
      .then((created) => {
        setMessages((prev) => mergeMessagesById(prev, [created]));
        if (typeof created.id === "number") {
          lastMessageIdRef.current = Math.max(lastMessageIdRef.current, created.id);
        }
        scheduleFullChatsRefresh();
      })
      .catch((err) => {
        console.error(err);
        alert("Не удалось отправить сообщение");
      });
    setInput("");
    setReplyTo(null);
    setPendingFile(null);
  }

  useEffect(() => {
    if (confirmDeletePeer === null || deleteCountdown <= 0) return;
    const timer = setTimeout(() => setDeleteCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [confirmDeletePeer, deleteCountdown]);

  function requestDeleteChat(peerUsername) {
    if (peerUsername === LOBBY_PEER_USERNAME) return;
    if (confirmDeletePeer === peerUsername) {
      setConfirmDeletePeer(null);
      setDeleteCountdown(0);
      return;
    }
    setConfirmDeletePeer(peerUsername);
    setDeleteCountdown(5);
  }

  async function handleDeleteChatByPeer(peerUsername) {
    if (peerUsername === LOBBY_PEER_USERNAME) return;
    setConfirmDeletePeer(null);
    setDeleteCountdown(0);
    try {
      const chat = serverChats.find((c) => c.peer?.username === peerUsername);
      if (!chat) return;
      await deleteChat(chat.id);
      setServerChats((prev) => {
        const next = prev.filter((c) => c.id !== chat.id);
        persistChatsCache(next);
        return next;
      });
      setUnreadByPeer((prev) => {
        const next = { ...prev };
        delete next[peerUsername];
        return next;
      });
      if (activePeer === peerUsername) {
        setActivePeer("");
        setMessages([]);
      }
    } catch (e) {
      console.error(e);
      alert("Не удалось удалить чат");
    }
  }

  function handleLogout() {
    setStoredToken("");
    onLogout();
  }

  async function handleSaveSettings(e) {
    e.preventDefault();
    const name = settingsName.trim();
    if (!name) return;
    try {
      setSettingsSaving(true);
      const updated = await updateMeName(name);
      setSettingsName(updated.name || name);
      currentUserRef.current = { ...currentUserRef.current, name: updated.name };
      alert("Имя сохранено");
    } catch (e) {
      console.error(e);
      alert("Не удалось сохранить имя");
    } finally {
      setSettingsSaving(false);
    }
  }

  async function handleDeleteAccount() {
    if (!window.confirm("Точно удалить аккаунт? Действие необратимо.")) return;
    try {
      await deleteMyAccount();
      handleLogout();
    } catch (e) {
      console.error(e);
      alert("Не удалось удалить аккаунт");
    }
  }

  function handleReplyToMessage(m) {
    setReplyTo(m);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }

  function startEdit(m) {
    setEditingId(m.id);
    setEditText(m.content || "");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditText("");
  }

  async function saveEdit(messageId) {
    const text = editText.trim();
    if (!text) return;
    try {
      const updated = await updateMessage(messageId, text);
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, ...updated } : m))
      );
      cancelEdit();
    } catch (e) {
      console.error(e);
      alert("Не удалось сохранить");
    }
  }

  async function handleDeleteMessage(messageId) {
    if (!window.confirm("Удалить это сообщение?")) return;
    try {
      await deleteMyMessage(messageId);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      if (editingId === messageId) cancelEdit();
      scheduleFullChatsRefresh();
    } catch (e) {
      console.error(e);
      alert("Не удалось удалить");
    }
  }

  return (
    <div className="chat-container" ref={chatContainerRef}>
      <header className="chat-header" ref={chatHeaderRef}>
        {isNarrowViewport && (
          <button
            type="button"
            className="sidebar-drawer-toggle"
            onClick={() => setSidebarDrawerOpen((o) => !o)}
            aria-expanded={sidebarDrawerOpen}
            aria-controls="chat-sidebar"
            aria-label={sidebarDrawerOpen ? "Закрыть список чатов" : "Открыть список чатов"}
          >
            ☰
          </button>
        )}
        <div className="chat-header-brand">
          <img
            className="chat-header-logo"
            src="/asyncgram-icon.png"
            alt=""
            width={40}
            height={40}
            decoding="async"
          />
          <div className="chat-header-titles">
            <div className="chat-title">Asyncgram</div>
            <div className="chat-subtitle">
              Вы вошли как <strong>{currentUser.name}</strong> ({currentUser.role})
            </div>
          </div>
        </div>
        <div className="chat-status">
          <span>{status}</span>
          {currentUser.role === "admin" && (
            <button
              type="button"
              style={{ marginRight: 8 }}
              onClick={() => setAdminPanelOpen(true)}
              aria-label="Админ-панель"
            >
              [ADM]
            </button>
          )}
          <button
            type="button"
            style={{ marginRight: 8 }}
            onClick={() => setSettingsOpen((v) => !v)}
            aria-label="Настройки"
          >
            [CFG]
          </button>
          <button type="button" onClick={handleLogout} aria-label="Выйти">
            [OUT]
          </button>
        </div>
      </header>
      {isNarrowViewport && sidebarDrawerOpen ? (
        <div
          className="chat-sidebar-backdrop"
          role="presentation"
          aria-hidden
          onClick={() => setSidebarDrawerOpen(false)}
        />
      ) : null}
      <div
        className={
          "chat-shell" +
          (isNarrowViewport ? " chat-shell--narrow" : "") +
          (isNarrowViewport && sidebarDrawerOpen ? " chat-shell--sidebar-open" : "")
        }
      >
        <aside className="chat-sidebar" id="chat-sidebar">
          <div className="sidebar-top">
            <div className="search-bar">
              <div className="search-icon" aria-hidden="true">
                ⌕
              </div>
              <input
                type="text"
                placeholder="Поиск собеседника…"
                value={peerQuery}
                onChange={(e) => setPeerQuery(e.target.value)}
              />
              {peerQuery.trim() && (
                <button
                  type="button"
                  className="search-clear"
                  onClick={() => {
                    setPeerQuery("");
                    setPeerResults([]);
                  }}
                  aria-label="Очистить поиск"
                >
                  ×
                </button>
              )}
            </div>

            {peerResults.length > 0 && (
              <div className="search-results">
                {peerResults.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    className="search-result"
                    onClick={() => {
                      selectPeer(u.username);
                      setPeerResults([]);
                      setPeerQuery("");
                    }}
                  >
                    <span className="sr-name">{u.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="sidebar-section-title">Чаты</div>
          <div className="chat-list">
            {sortedServerChats.length === 0 ? (
              <div className="chat-list-empty">Пока нет диалогов. Найдите пользователя сверху.</div>
            ) : (
              sortedServerChats.map((c) => {
                const u = c.peer?.username;
                const displayName = c.peer?.name || c.peer?.username;
                if (!u) return null;
                const unread = unreadByPeer[u] || 0;
                const active = u === activePeer;
                const isGlobalRow = c.is_global || u === LOBBY_PEER_USERNAME;
                return (
                  <button
                    key={c.id}
                    type="button"
                    className={`chat-list-item${active ? " active" : ""}${isGlobalRow ? " chat-list-item--global" : ""}`}
                    onClick={() => selectPeer(u)}
                  >
                    <div className="cli-main">
                      <div className="cli-title">{displayName}</div>
                      <div className="cli-subtitle">
                        {isGlobalRow ? "Общий чат" : active ? "Открыт" : "Диалог"}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {unread > 0 && <div className="cli-badge">{unread}</div>}
                      {confirmDeletePeer === u ? (
                        <div className="delete-confirm-row" onClick={(e) => { e.stopPropagation(); }}>
                          <span className="delete-confirm-text">Удалить?</span>
                          <button
                            type="button"
                            className="delete-confirm-yes"
                            disabled={deleteCountdown > 0}
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              handleDeleteChatByPeer(u);
                            }}
                          >
                            {deleteCountdown > 0 ? deleteCountdown : "Да"}
                          </button>
                          <button
                            type="button"
                            className="delete-confirm-no"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setConfirmDeletePeer(null);
                              setDeleteCountdown(0);
                            }}
                          >
                            Нет
                          </button>
                        </div>
                      ) : !isGlobalRow ? (
                        <button
                          type="button"
                          className="sidebar-delete-chat"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            requestDeleteChat(u);
                          }}
                          aria-label={`Удалить чат с ${displayName}`}
                        >
                          ×
                        </button>
                      ) : null}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        <section className="chat-content">
          <div className="chat-peer-banner">
            <div className="chat-peer-banner-text">
              <div className="cpb-title">
                {activePeer
                  ? (() => {
                      const chat = serverChats.find((c) => c.peer?.username === activePeer);
                      const dn = chat?.peer?.name || chat?.peer?.username || activePeer;
                      return `Диалог с ${dn}`;
                    })()
                  : isNarrowViewport
                    ? "Откройте меню «☰» и выберите чат"
                    : "Выберите чат слева"}
              </div>
              <div className="cpb-subtitle">
                {activePeer === LOBBY_PEER_USERNAME
                  ? "Сообщения видны всем зарегистрированным пользователям"
                  : activePeer
                    ? "Сообщения видны только вам двоим"
                    : isNarrowViewport
                      ? "Начните с поиска в меню «☰»"
                      : "Начните с поиска пользователя по имени"}
              </div>
            </div>
            {activePeer ? (
              <button
                type="button"
                className="chat-peer-banner-close"
                onClick={closeActiveChat}
                aria-label="Закрыть чат"
                title="Закрыть диалог (чат останется в списке)"
              >
                [ЗАКР]
              </button>
            ) : null}
          </div>

          <main className="chat-main">
            {!activePeer ? (
              <div
                className="chat-empty-state"
                role="region"
                aria-label="О сервисе Asyncgram"
              >
                <p className="chat-empty-state-lead">{CHAT_EMPTY_BLURB.lead}</p>
                <p className="chat-empty-state-body">{CHAT_EMPTY_BLURB.body}</p>
              </div>
            ) : (
            <ul className="message-list">
              {messages.map((m) => {
                const own = m.author?.id === currentUser.id;
                const uname = m.author?.username ?? "?";
                const userAt = `${uname}@local`;
                const replyHint =
                  m.reply_to && m.reply_to.content
                    ? ` (re: ${(m.reply_to.content || "").slice(0, 48)}${(m.reply_to.content || "").length > 48 ? "…" : ""})`
                    : "";
                return (
                  <li
                    key={m.id}
                    className={own ? "message message--terminal own-message" : "message message--terminal"}
                  >
                    <div className="message-meta">
                      <span className="message-log-line">
                        [{formatMessageLogTime(m.created_at)}]
                        {m.author?.role === "admin" ? " [ADMIN]" : ""}{" "}
                        <span className="message-log-prompt">{userAt}</span>
                        {" >>"}
                        {replyHint}
                        {m.edited_at ? (
                          <span className="message-edited"> [edited]</span>
                        ) : null}
                      </span>
                      {editingId !== m.id && (
                        <span className="message-actions">
                          <button
                            type="button"
                            className="msg-action"
                            onClick={() => handleReplyToMessage(m)}
                            aria-label="Ответить на сообщение"
                          >
                            [REPLY]
                          </button>
                          {own && (
                            <>
                              <button
                                type="button"
                                className="msg-action"
                                onClick={() => startEdit(m)}
                                aria-label="Изменить сообщение"
                              >
                                [EDIT]
                              </button>
                              <button
                                type="button"
                                className="msg-action msg-action-danger"
                                onClick={() => handleDeleteMessage(m.id)}
                                aria-label="Удалить сообщение"
                              >
                                [DEL]
                              </button>
                            </>
                          )}
                        </span>
                      )}
                    </div>
                    <hr className="message-sep" aria-hidden="true" />
                    {m.reply_to && m.reply_to.author && (
                      <div className="message-reply-block">
                        <div className="message-reply-author">
                          re @{m.reply_to.author.name || m.reply_to.author.username || "msg"}
                        </div>
                        <div className="message-reply-snippet">
                          {m.reply_to.content?.slice(0, 120)}
                        </div>
                      </div>
                    )}
                    {m.file_url && (
                      <div className="message-attachment">
                        {(m.file_type || "").startsWith("image/") ? (
                          <a href={API_BASE + m.file_url} target="_blank" rel="noopener noreferrer">
                            <img
                              src={API_BASE + m.file_url}
                              alt={m.file_name || "image"}
                              className="attachment-image"
                            />
                          </a>
                        ) : (m.file_type || "").startsWith("video/") ? (
                          <video
                            src={API_BASE + m.file_url}
                            controls
                            className="attachment-video"
                          />
                        ) : (m.file_type || "").startsWith("audio/") ? (
                          <audio
                            src={API_BASE + m.file_url}
                            controls
                            className="attachment-audio"
                          />
                        ) : (
                          <a
                            href={API_BASE + m.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="attachment-file"
                          >
                            <span className="attachment-file-icon">[FILE]</span>
                            <span className="attachment-file-info">
                              <span className="attachment-file-name">{m.file_name || "file"}</span>
                              {m.file_size != null && (
                                <span className="attachment-file-size">
                                  {m.file_size < 1024
                                    ? m.file_size + " Б"
                                    : m.file_size < 1048576
                                      ? (m.file_size / 1024).toFixed(1) + " КБ"
                                      : (m.file_size / 1048576).toFixed(1) + " МБ"}
                                </span>
                              )}
                            </span>
                          </a>
                        )}
                      </div>
                    )}
                    {own && editingId === m.id ? (
                      <div className="message-edit-row">
                        <input
                          type="text"
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          maxLength={4000}
                          className="message-edit-input"
                        />
                        <button type="button" onClick={() => saveEdit(m.id)}>
                          [OK]
                        </button>
                        <button type="button" onClick={cancelEdit}>
                          [X]
                        </button>
                      </div>
                    ) : (
                      m.content && <div className="message-content message-body-line">{m.content}</div>
                    )}
                  </li>
                );
              })}
              <div ref={bottomRef} />
            </ul>
            )}
          </main>

          {activePeer ? (
            <>
              {pendingFile && (
                <div className="pending-file-preview">
                  <div className="pending-file-info">
                    {(pendingFile.file_type || "").startsWith("image/") ? (
                      <img
                        src={API_BASE + pendingFile.file_url}
                        alt={pendingFile.file_name}
                        className="pending-file-thumb"
                      />
                    ) : (
                      <span className="pending-file-icon">📎</span>
                    )}
                    <span className="pending-file-name">{pendingFile.file_name}</span>
                  </div>
                  <button
                    type="button"
                    className="pending-file-remove"
                    onClick={() => setPendingFile(null)}
                    aria-label="Убрать файл"
                  >
                    ×
                  </button>
                </div>
              )}
              <form className="chat-input-row" onSubmit={sendMessage}>
                <input
                  id="chat-file-input"
                  ref={fileInputRef}
                  type="file"
                  className="chat-file-input-hidden"
                  onChange={handleFileSelect}
                  disabled={uploading}
                />
                <button
                  type="button"
                  className="attach-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  title="Прикрепить файл к сообщению (до 10 МБ)"
                  aria-label="Прикрепить файл к сообщению, максимум 10 мегабайт"
                >
                  {uploading ? (
                    <span className="attach-btn-loading" aria-live="polite">
                      …
                    </span>
                  ) : (
                    <span className="attach-btn-inner">
                      <svg
                        className="attach-icon"
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                      </svg>
                      <span className="attach-text">Файл</span>
                    </span>
                  )}
                </button>
                <div className="chat-input-wrap">
                  <input
                    ref={inputRef}
                    type="text"
                    placeholder="ввод…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    maxLength={4000}
                  />
                  <span className="chat-input-caret-glow" aria-hidden="true">
                    █
                  </span>
                </div>
                <button type="submit">[SEND]</button>
              </form>
            </>
          ) : null}
        </section>
      </div>

      <pre className="crt-statusbar" aria-hidden="true">
        {CRT_STATUS_LINES[crtStatusIdx % CRT_STATUS_LINES.length]}
      </pre>

      {settingsOpen && (
        <div className="settings-panel" role="dialog" aria-modal="true" aria-labelledby="settings-panel-title">
          <div className="settings-panel-header">
            <span id="settings-panel-title" className="settings-panel-title">
              Настройки
            </span>
            <button
              type="button"
              className="settings-panel-close"
              onClick={() => setSettingsOpen(false)}
              aria-label="Закрыть настройки"
            >
              ×
            </button>
          </div>
          <form onSubmit={handleSaveSettings}>
            <div className="settings-row">
              <label>
                Имя
                <input
                  type="text"
                  value={settingsName}
                  onChange={(e) => setSettingsName(e.target.value)}
                  maxLength={100}
                />
              </label>
            </div>
            <div className="settings-actions">
              <button type="submit" disabled={settingsSaving}>
                {settingsSaving ? "Сохранение..." : "Сохранить"}
              </button>
              <button
                type="button"
                className="settings-danger"
                onClick={handleDeleteAccount}
              >
                Удалить аккаунт
              </button>
            </div>
          </form>
        </div>
      )}
      {replyTo && (
        <div className="reply-preview">
          <div className="reply-preview-main">
            <div className="reply-preview-title">
              Ответ на {replyTo.author?.name || "сообщение"}
            </div>
            <div className="reply-preview-snippet">
              {replyTo.content ? replyTo.content.slice(0, 120) : ""}
            </div>
          </div>
          <button
            type="button"
            className="reply-preview-close"
            onClick={() => setReplyTo(null)}
            aria-label="Отменить ответ"
          >
            ×
          </button>
        </div>
      )}

      {adminPanelOpen && currentUser.role === "admin" && (
        <div
          className="admin-overlay"
          role="presentation"
          onClick={() => setAdminPanelOpen(false)}
        >
          <div
            className="admin-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-panel-title"
            onClick={(e) => e.stopPropagation()}
          >
            <AdminPanel onClose={() => setAdminPanelOpen(false)} currentUserId={currentUser.id} />
          </div>
        </div>
      )}
    </div>
  );
}

