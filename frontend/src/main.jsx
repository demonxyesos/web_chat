import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BinaryRainBackground } from "./BinaryRainBackground";
import { AuthForm } from "./AuthForm";
import { Chat } from "./Chat";
import { fetchMe, getStoredToken, setStoredToken } from "./api";
import "./styles.css";

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      const token = getStoredToken();
      if (!token) {
        setChecking(false);
        return;
      }
      try {
        const me = await fetchMe();
        setCurrentUser(me);
      } catch {
        setStoredToken("");
      } finally {
        setChecking(false);
      }
    }
    checkAuth();
  }, []);

  useEffect(() => {
    async function refreshMe() {
      if (!getStoredToken()) return;
      try {
        const me = await fetchMe();
        setCurrentUser(me);
      } catch {
        setStoredToken("");
        setCurrentUser(null);
      }
    }
    function onVisible() {
      if (document.visibilityState === "visible") refreshMe();
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  return (
    <>
      <BinaryRainBackground />
      <div className="crt-scanlines" aria-hidden="true" />
      <div className="app-root">
        {checking ? (
          <div className="center-screen">
            <div className="loader" />
            <p>Проверка сессии...</p>
          </div>
        ) : !currentUser ? (
          <AuthForm onAuthenticated={setCurrentUser} />
        ) : (
          <Chat currentUser={currentUser} onLogout={() => setCurrentUser(null)} />
        )}
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

