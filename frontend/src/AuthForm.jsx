import { useState } from "react";
import { clearChatsCacheForUser, loginUser, registerUser } from "./api";

export function AuthForm({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await registerUser(username.trim(), name.trim(), password, passwordConfirm);
      }
      const tokenResponse = await loginUser(username.trim(), password);
      clearChatsCacheForUser(tokenResponse.user?.id);
      onAuthenticated(tokenResponse.user);
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      let message = "Ошибка авторизации";
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map((d) => d?.msg || "").filter(Boolean).join("; ") || message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrapper">
    <div className="auth-container">
      <div className="auth-brand">
        <img
          className="auth-brand-logo"
          src="/asyncgram-icon.png"
          alt=""
          width={48}
          height={48}
          decoding="async"
        />
        <h1>Asyncgram</h1>
      </div>
      <div className="auth-toggle">
        <button
          type="button"
          className={mode === "login" ? "active" : ""}
          onClick={() => setMode("login")}
        >
          Вход
        </button>
        <button
          type="button"
          className={mode === "register" ? "active" : ""}
          onClick={() => setMode("register")}
        >
          Регистрация
        </button>
      </div>
      <form onSubmit={handleSubmit} className="auth-form">
        <label>
          Логин
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            maxLength={50}
            required
            autoComplete="username"
          />
        </label>
        {mode === "register" && (
          <label>
            Имя (отображается в чате)
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              minLength={1}
              maxLength={100}
              required={mode === "register"}
            />
          </label>
        )}
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            maxLength={128}
            required
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </label>
        {mode === "register" && (
          <label>
            Подтверждение пароля
            <input
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              minLength={8}
              maxLength={128}
              required={mode === "register"}
            />
          </label>
        )}
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={loading}>
          {loading ? "Подождите..." : mode === "login" ? "Войти" : "Зарегистрироваться"}
        </button>
      </form>
    </div>
    </div>
  );
}

