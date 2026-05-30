# Asyncgram — доклад по разработке

Полное описание проекта: что было сделано, как устроена микросервисная архитектура, как работают сервисы, база данных, realtime и деплой.

---

## 1. О проекте

**Asyncgram** — веб-чат в стиле терминала (React + FastAPI) с:

- регистрацией и авторизацией;
- личными диалогами 1:1;
- общим чатом (lobby) для всех пользователей;
- отправкой файлов (до 10 МБ);
- ответами на сообщения (reply), редактированием и удалением;
- админ-панелью для модерации;
- доставкой сообщений в реальном времени через WebSocket.

**Стек:**

| Слой | Технологии |
|---|---|
| Frontend | React 18, Vite, Axios |
| Backend | 5 микросервисов на FastAPI |
| БД | PostgreSQL (prod) / SQLite (dev) |
| Realtime | Redis pub/sub + WebSocket |
| Gateway | nginx |
| Деплой | systemd на VPS, SFTP |

---

## 2. Что было сделано: от монолита к микросервисам

### 2.1. Исходное состояние

Изначально проект был **модульным монолитом** — один процесс FastAPI (`backend/main.py`), который включал:

- все HTTP-роуты (auth, chats, admin, upload);
- WebSocket endpoint с in-memory `ConnectionManager`;
- одну общую базу данных;
- упрощённую авторизацию (токен = строковый `user_id`).

Проблемы такой архитектуры:

1. **WebSocket state in-memory** — нельзя масштабировать горизонтально и нельзя вызывать push из другого процесса.
2. **Жёсткая связность** — роуты чата и админки напрямую вызывали `manager.send_to()` внутри того же процесса.
3. **Единая точка отказа** — падение одного модуля валит всё приложение.

### 2.2. Целевая архитектура

Проект переработан в **5 независимых микросервисов** + API Gateway (nginx):

```mermaid
flowchart TB
  subgraph client [Клиент]
    FE[React Frontend]
  end

  subgraph edge [API Gateway]
    GW[nginx :8080]
  end

  subgraph services [Микросервисы]
    AuthSvc["auth-service :8001"]
    ChatSvc["chat-service :8002"]
    WsSvc["ws-gateway :8003"]
    MediaSvc["media-service :8004"]
    AdminSvc["admin-service :8005"]
  end

  subgraph infra [Инфраструктура]
    Redis[(Redis pub/sub)]
    PG[(PostgreSQL / SQLite)]
    FS[uploads/]
  end

  FE --> GW
  GW --> AuthSvc
  GW --> ChatSvc
  GW --> MediaSvc
  GW --> AdminSvc
  FE -->|WebSocket| GW
  GW --> WsSvc

  AuthSvc --> PG
  ChatSvc --> PG
  ChatSvc --> Redis
  AdminSvc --> Redis
  Redis --> WsSvc
  WsSvc --> FE
  MediaSvc --> FS
```

### 2.3. Ключевые решения при миграции

| Было (монолит) | Стало (микросервисы) |
|---|---|
| Dev-токен = `user_id` | JWT с `sub`, `role`, `exp` |
| WS отправка из HTTP-роутов | Redis pub/sub → ws-gateway |
| Клиент шлёт сообщения по WS | Клиент шлёт по HTTP, WS только для получения |
| Один `backend/main.py` | 5 сервисов в `services/` |
| In-memory ConnectionManager | ws-gateway + Redis subscriber |
| Один процесс uvicorn | 5 systemd unit-файлов |

Монолитный каталог `backend/` **удалён**. Вся логика перенесена в `services/` и `packages/common/`.

---

## 3. Структура репозитория

```text
chat/
├── infra/
│   ├── nginx/asyncgram.conf          # маршрутизация API Gateway
│   ├── systemd/asyncgram-*.service   # unit-файлы для VPS
│   └── env.example                   # шаблон переменных окружения
├── packages/
│   └── common/asyncgram_common/      # общая библиотека (JWT, Redis, CORS)
├── services/
│   ├── auth_service/                 # :8001 — пользователи, JWT
│   ├── chat_service/                 # :8002 — чаты, сообщения
│   ├── ws_gateway/                   # :8003 — WebSocket
│   ├── media_service/                # :8004 — файлы
│   └── admin_service/                # :8005 — модерация
├── frontend/                         # React UI
├── scripts/
│   ├── dev_run_all.ps1               # локальный запуск всех сервисов
│   ├── deploy_chat_sftp.py           # деплой по SFTP
│   └── ssh_restart_site.py           # перезапуск systemd units
├── tests/test_smoke_microservices.py # smoke-тесты
├── docker-compose.yml                # опционально: Redis + Postgres
└── requirements.txt
```

---

## 4. Микросервисы: кто за что отвечает

### 4.1. auth-service (порт 8001)

**Ответственность:** регистрация, логин, JWT, профиль пользователя.

**Файлы:** `services/auth_service/app/`

| Endpoint | Метод | Описание |
|---|---|---|
| `/auth/register` | POST | регистрация нового пользователя |
| `/auth/token` | POST | логин, выдача JWT |
| `/users/me` | GET | текущий пользователь |
| `/users/me` | PATCH | смена отображаемого имени |
| `/users/me` | DELETE | мягкое удаление аккаунта |
| `/internal/users` | GET | список пользователей (admin only) |
| `/internal/users/{id}` | DELETE | удаление пользователя (admin only) |

**Бизнес-правила:**

- первый зарегистрированный пользователь получает роль `admin`;
- имя `__lobby__` зарезервировано;
- пароли хешируются через bcrypt (passlib);
- при старте создаётся системный пользователь `__lobby__` (Общий чат).

**Пример выдачи JWT** (`packages/common/asyncgram_common/jwt.py`):

```python
def create_access_token(subject: int, role: str) -> str:
    payload = {
        "sub": str(subject),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
```

---

### 4.2. chat-service (порт 8002)

**Ответственность:** чаты, сообщения, поиск пользователей, публикация realtime-событий.

| Endpoint | Метод | Описание |
|---|---|---|
| `/messages` | POST | создать сообщение |
| `/messages/{id}` | PATCH | редактировать своё сообщение |
| `/messages/{id}` | DELETE | удалить своё сообщение |
| `/chats` | GET | список диалогов с last_message |
| `/chats/{username}/messages` | GET | история сообщений |
| `/chats/{id}` | DELETE | удалить диалог |
| `/users/search` | GET | поиск собеседника |
| `/internal/messages` | GET | лента для админки |
| `/internal/messages/{id}` | DELETE | удаление сообщения админом |

**После каждой мутации** (create / edit / delete) сервис публикует событие в Redis:

```python
# services/chat_service/app/routes.py
msg, chat, author, recipient, reply_to = service.create_message(current.id, msg_in)
event = service.build_created_event(msg, chat, author, recipient, reply_to)
await event_bus.publish(event)
```

**Типы событий:**

| type | broadcast | Описание |
|---|---|---|
| `message.created` | true/false | новое сообщение |
| `message.edited` | true/false | редактирование |
| `message.deleted` | true/false | удаление |

Для общего чата (`__lobby__`) — `broadcast: true` (всем подключённым).  
Для личного диалога — `target_user_ids: [author_id, recipient_id]`.

При старте chat-service создаёт **глобальный чат** (`is_global=1`), если системный пользователь lobby уже существует.

---

### 4.3. ws-gateway (порт 8003)

**Ответственность:** WebSocket-соединения и доставка событий клиентам.

**Не имеет доступа к БД.** Только:

1. принимает WebSocket `/ws/chat?token=<JWT>`;
2. валидирует JWT локально (без запроса в auth-service);
3. подписан на Redis-канал `chat.events`;
4. рассылает payload подключённым клиентам.

```mermaid
sequenceDiagram
  participant Chat as chat-service
  participant Redis as Redis
  participant WS as ws-gateway
  participant Client as Browser

  Chat->>Redis: publish ChatEvent
  Redis->>WS: message on chat.events
  alt broadcast=true
    WS->>Client: send_json всем
  else target_user_ids
    WS->>Client: send_json конкретным user_id
  end
```

**ConnectionManager** (`services/ws_gateway/app/connections.py`):

```python
class ConnectionManager:
    active_connections: dict[int, WebSocket]  # user_id → websocket

    async def send_to(self, user_id, message): ...
    async def broadcast_json(self, message): ...
```

Клиент **не отправляет** сообщения через WebSocket — только **получает** push. Отправка идёт через HTTP `POST /messages`.

---

### 4.4. media-service (порт 8004)

**Ответственность:** загрузка и раздача файлов.

| Endpoint | Описание |
|---|---|
| `POST /upload` | загрузка файла (multipart, max 10 МБ) |
| `GET /uploads/{filename}` | статическая раздача |

**Whitelist расширений:** jpg, png, gif, mp4, pdf, doc, zip и др.

Файлы сохраняются в `uploads/` (на VPS: `/opt/chat/uploads/`).  
В сообщении хранится только ссылка (`file_url`, `file_name`, `file_type`, `file_size`).

---

### 4.5. admin-service (порт 8005)

**Ответственность:** модерация. **Не имеет своей БД** — проксирует запросы в internal API других сервисов.

```mermaid
flowchart LR
  AdminUI[AdminPanel.jsx] --> AdminSvc[admin-service]
  AdminSvc -->|"GET /internal/users"| AuthSvc[auth-service]
  AdminSvc -->|"DELETE /internal/users/{id}"| AuthSvc
  AdminSvc -->|"GET /internal/messages"| ChatSvc[chat-service]
  AdminSvc -->|"DELETE /internal/messages/{id}"| ChatSvc
  ChatSvc --> Redis
```

| Endpoint | Куда проксирует |
|---|---|
| `GET /admin/users` | auth-service `/internal/users` |
| `DELETE /admin/users/{id}` | auth-service `/internal/users/{id}` |
| `GET /admin/messages` | chat-service `/internal/messages` |
| `DELETE /admin/messages/{id}` | chat-service `/internal/messages/{id}` |

Доступ только для JWT с `role=admin`. Тот же токен пробрасывается в internal endpoints.

---

## 5. Общая библиотека `asyncgram_common`

Пакет `packages/common/asyncgram_common/` — код, общий для всех сервисов:

| Модуль | Назначение |
|---|---|
| `jwt.py` | создание и валидация JWT |
| `passwords.py` | bcrypt hash/verify |
| `auth_deps.py` | FastAPI dependencies: `CurrentTokenUser`, `AdminTokenUser` |
| `events.py` | Pydantic-модель `ChatEvent` |
| `redis_bus.py` | `EventBus` — publish/subscribe через Redis |
| `config.py` | переменные окружения (JWT_SECRET, DATABASE_URL, REDIS_URL) |
| `constants.py` | `LOBBY_USERNAME`, `CHAT_EVENTS_CHANNEL` |
| `app_factory.py` | CORS middleware, `/health` endpoint |

**Формат события Redis:**

```json
{
  "type": "message.created",
  "broadcast": false,
  "target_user_ids": [1, 2],
  "payload": {
    "id": 42,
    "chat_id": 5,
    "content": "Привет!",
    "author": { "id": 1, "username": "alice", "name": "Alice" },
    "recipient": { "id": 2, "username": "bob", "name": "Bob" }
  }
}
```

---

## 6. База данных

### 6.1. Стратегия хранения

Используется **эволюционный подход**: одна PostgreSQL, разделение по **schema**:

```text
PostgreSQL (asyncgram)
├── auth.users          ← владелец: auth-service
├── chat.chats          ← владелец: chat-service
└── chat.messages       ← владелец: chat-service
```

Для **локальной разработки** — SQLite (`sqlite:///./database.db`), таблицы без schema-префикса.

### 6.2. Таблица `auth.users`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `username` | VARCHAR(50) UNIQUE | логин |
| `name` | VARCHAR(100) UNIQUE | отображаемое имя |
| `password_hash` | VARCHAR(255) | bcrypt |
| `role` | VARCHAR(20) | `user` / `admin` |
| `created_at` | DATETIME | |
| `is_deleted` | INTEGER | мягкое удаление (0/1) |

**Writer:** только auth-service.  
**Reader:** chat-service (read-only mapping для отображения author/recipient).

### 6.3. Таблица `chat.chats`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `user_a_id` | INTEGER | участник (меньший id) |
| `user_b_id` | INTEGER | участник (больший id) |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | для сортировки списка чатов |
| `is_deleted` | INTEGER | мягкое удаление |
| `is_global` | INTEGER | 1 = общий чат |

**Уникальность:** `(user_a_id, user_b_id)` — один диалог на пару.  
Пары сортируются (`sorted([a, b])`), чтобы `(1,2)` и `(2,1)` были одной записью.

### 6.4. Таблица `chat.messages`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `content` | TEXT | текст (до 4000 символов) |
| `created_at` | DATETIME | |
| `edited_at` | DATETIME NULL | время редактирования |
| `is_deleted` | INTEGER | мягкое удаление |
| `chat_id` | INTEGER FK | → chats.id |
| `author_id` | INTEGER | логическая ссылка на auth.users |
| `recipient_id` | INTEGER | логическая ссылка на auth.users |
| `reply_to_message_id` | INTEGER FK NULL | → messages.id |
| `file_url` | VARCHAR(500) NULL | |
| `file_name` | VARCHAR(255) NULL | |
| `file_type` | VARCHAR(100) NULL | |
| `file_size` | INTEGER NULL | |

**Индекс:** `(chat_id, is_deleted, created_at)` — быстрая выборка истории.

### 6.5. ER-диаграмма

```mermaid
erDiagram
  USERS ||--o{ MESSAGES : "author_id"
  USERS ||--o{ MESSAGES : "recipient_id"
  CHATS ||--o{ MESSAGES : "chat_id"
  MESSAGES ||--o| MESSAGES : "reply_to"

  USERS {
    int id PK
    string username UK
    string name UK
    string password_hash
    string role
    int is_deleted
  }

  CHATS {
    int id PK
    int user_a_id
    int user_b_id
    int is_global
    int is_deleted
    datetime updated_at
  }

  MESSAGES {
    int id PK
    int chat_id FK
    int author_id
    int recipient_id
    int reply_to_message_id FK
    text content
    int is_deleted
  }
```

### 6.6. Системные сущности

При старте сервисов автоматически создаются:

1. **Пользователь `__lobby__`** (auth-service) — системный аккаунт для общего чата.
2. **Глобальный чат** (chat-service) — `is_global=1`, peer = `__lobby__`.

---

## 7. Аутентификация и авторизация

### 7.1. Поток регистрации и логина

```mermaid
sequenceDiagram
  participant UI as Frontend
  participant GW as nginx
  participant Auth as auth-service

  UI->>GW: POST /auth/register
  GW->>Auth: register
  Auth->>Auth: bcrypt hash password
  Auth-->>UI: UserOut

  UI->>GW: POST /auth/token
  GW->>Auth: login
  Auth->>Auth: verify password + create JWT
  Auth-->>UI: { access_token, user }
  UI->>UI: localStorage.setItem("access_token")
```

### 7.2. Проверка JWT в других сервисах

Каждый сервис валидирует JWT **локально** через shared `JWT_SECRET` — без запроса в auth-service:

```python
# packages/common/asyncgram_common/auth_deps.py
def get_token_user(token: str) -> TokenUser:
    payload = decode_token_payload(token)  # jwt.decode(...)
    return TokenUser(user_id=int(payload["sub"]), role=payload["role"])
```

### 7.3. Роли

| Роль | Возможности |
|---|---|
| `user` | чаты, сообщения, профиль |
| `admin` | + админ-панель, internal endpoints |

---

## 8. Realtime: полный цикл сообщения

```mermaid
sequenceDiagram
  participant UI as Frontend
  participant GW as nginx
  participant Chat as chat-service
  participant DB as Database
  participant Redis as Redis
  participant WS as ws-gateway
  participant Peer as Другой клиент

  Note over UI,Peer: Отправка
  UI->>GW: POST /messages { to, content }
  GW->>Chat: create_message
  Chat->>DB: INSERT message
  Chat->>Redis: publish ChatEvent
  Chat-->>UI: MessageOut (HTTP response)
  UI->>UI: mergeMessagesById (мгновенный UI)

  Note over Redis,Peer: Доставка
  Redis->>WS: chat.events
  WS->>UI: WebSocket push
  WS->>Peer: WebSocket push

  Note over UI: Fallback
  UI->>GW: GET /chats/{user}/messages (polling каждые 3 сек)
```

**Fallback:** если WebSocket отключён, `Chat.jsx` подтягивает историю по HTTP каждые 3 секунды.

---

## 9. Frontend

### 9.1. Структура

| Файл | Назначение |
|---|---|
| `main.jsx` | bootstrap, проверка сессии |
| `AuthForm.jsx` | логин / регистрация |
| `Chat.jsx` | основной UI: чаты, сообщения, WS, settings |
| `AdminPanel.jsx` | админ-панель (users + messages) |
| `api.js` | все HTTP/WS вызовы |
| `BinaryRainBackground.jsx` | фоновая анимация |

### 9.2. API-слой (`frontend/src/api.js`)

```javascript
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (import.meta.env.DEV ? `http://${API_HOST}:${API_PORT}` : window.location.origin);

// JWT автоматически добавляется через axios interceptor
api.interceptors.request.use((config) => {
  config.headers.Authorization = `Bearer ${getStoredToken()}`;
  return config;
});
```

### 9.3. Отправка сообщений (HTTP, не WS)

```javascript
// frontend/src/Chat.jsx
createMessage({ content: text, to: activePeer, reply_to_id, ...fileFields })
  .then((created) => {
    setMessages((prev) => mergeMessagesById(prev, [created]));
    scheduleFullChatsRefresh();
  });
```

### 9.4. WebSocket — только приём

```javascript
const ws = createChatWebSocket();  // ws://host/ws/chat?token=...
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "message_deleted") { ... }
  if (msg.type === "message_edited") { ... }
  // обычное сообщение — append в ленту
};
```

---

## 10. API Gateway (nginx)

Единая точка входа `:8080`. Конфиг: `infra/nginx/asyncgram.conf`.

| Path | Upstream | Порт |
|---|---|---|
| `/auth/*` | asyncgram_auth | 8001 |
| `/users/me` | asyncgram_auth | 8001 |
| `/chats/*`, `/messages` | asyncgram_chat | 8002 |
| `/users/search` | asyncgram_chat | 8002 |
| `/upload`, `/uploads/*` | asyncgram_media | 8004 |
| `/admin/*` | asyncgram_admin | 8005 |
| `/ws/chat` | asyncgram_ws | 8003 |

WebSocket proxy настроен с `Upgrade` / `Connection: upgrade` и `proxy_read_timeout 86400`.

---

## 11. Деплой (без Docker)

### 11.1. Что нужно на VPS

- Python 3.11+, venv в `/opt/chat/venv`
- PostgreSQL, Redis (системные пакеты)
- nginx
- 5 systemd unit-файлов из `infra/systemd/`

### 11.2. Процесс деплоя

```mermaid
flowchart LR
  Dev[Разработчик] -->|SFTP| VPS["VPS /opt/chat"]
  VPS --> Systemd[systemctl restart asyncgram-*]
  Systemd --> Services[5 микросервисов]
  Nginx[nginx reload] --> Services
```

1. **SFTP:** `scripts/deploy_chat_sftp.py` — архивирует проект, заливает, распаковывает. Сохраняет `.env`, `venv/`, `uploads/`, `database.db`.
2. **systemd:** unit-файлы → `/etc/systemd/system/`, `systemctl enable --now asyncgram-{auth,chat,ws,media,admin}`.
3. **nginx:** `infra/nginx/asyncgram.conf` → sites-enabled, `nginx -t && systemctl reload nginx`.
4. **Перезапуск:** `scripts/ssh_restart_site.py`.

### 11.3. Переменные окружения

Шаблон: `infra/env.example`

```env
JWT_SECRET=change-me-to-a-long-random-string
DATABASE_URL=postgresql://asyncgram:password@127.0.0.1:5432/asyncgram
REDIS_URL=redis://127.0.0.1:6379/0
AUTH_SERVICE_URL=http://127.0.0.1:8001
CHAT_SERVICE_URL=http://127.0.0.1:8002
UPLOAD_DIR=/opt/chat/uploads
```

---

## 12. Локальная разработка

### 12.1. Установка

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 12.2. Redis

Нужен Redis на `127.0.0.1:6379`. Опционально через Docker:

```powershell
docker compose up -d redis
```

### 12.3. Переменные и запуск

```powershell
$env:PYTHONPATH = "$PWD;$PWD\packages\common"
$env:JWT_SECRET = "dev-secret"
$env:DATABASE_URL = "sqlite:///./database.db"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"

.\scripts\dev_run_all.ps1
```

### 12.4. Frontend

```powershell
cd frontend
npm install
$env:VITE_API_BASE = "http://127.0.0.1:8080"
npm run dev
```

Открыть: `http://127.0.0.1:5173`

---

## 13. Примеры API-запросов

### Регистрация

```bash
curl -X POST http://127.0.0.1:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","name":"Alice","password":"secret12345","password_confirm":"secret12345"}'
```

### Логин

```bash
curl -X POST http://127.0.0.1:8080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=secret12345&grant_type=password"
```

### Отправка сообщения

```bash
curl -X POST http://127.0.0.1:8080/messages \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"to":"bob","content":"Привет!"}'
```

### Загрузка файла

```bash
curl -X POST http://127.0.0.1:8080/upload \
  -H "Authorization: Bearer <JWT>" \
  -F "file=@picture.png"
```

### WebSocket (получение)

```javascript
const ws = new WebSocket("ws://127.0.0.1:8080/ws/chat?token=" + token);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## 14. Тестирование

Smoke-тесты проверяют JWT, импорт всех сервисов и схему событий:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\packages\common"
$env:JWT_SECRET = "test-secret"
$env:DATABASE_URL = "sqlite:///./test_smoke.db"
python -m unittest tests.test_smoke_microservices -v
```

---

## 15. Итоги

| Критерий | Статус |
|---|---|
| 5 независимых микросервисов | ✅ |
| JWT-авторизация (bcrypt + HS256) | ✅ |
| Realtime через Redis pub/sub | ✅ |
| WebSocket только для получения | ✅ |
| API Gateway (nginx) | ✅ |
| Деплой без Docker (systemd) | ✅ |
| Мягкое удаление (users, chats, messages) | ✅ |
| Общий чат + личные диалоги | ✅ |
| Файлы, reply, edit, admin | ✅ |
| Монолит удалён | ✅ |

Проект готов к production-деплою на VPS через systemd + nginx. Docker используется только опционально для локального Redis/PostgreSQL.
