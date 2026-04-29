import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { api } from "./api";
import { RssIcon, LogOutIcon } from "./components/icons";
import { Button } from "./components/ui";
import LoginPage from "./pages/LoginPage";
import FeedsPage from "./pages/FeedsPage";
import FeedEditorPage from "./pages/FeedEditorPage";
import "./styles.css";

function AppShell() {
  const [auth, setAuth] = useState<boolean | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.me()
      .then(() => setAuth(true))
      .catch(() => setAuth(false));
  }, []);

  async function handleLogout() {
    await api.logout();
    setAuth(false);
    navigate("/login", { replace: true });
  }

  if (auth === null) {
    return <div className="login-page"><p style={{ color: "var(--text-tertiary)" }}>Loading...</p></div>;
  }

  if (!auth) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <RssIcon width={18} height={18} />
          <span>Own New Newsletter</span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOutIcon /> Log out
        </Button>
      </header>
      <Routes>
        <Route path="/" element={<FeedsPage onLogout={handleLogout} />} />
        <Route path="/feeds/new" element={<FeedEditorPage />} />
        <Route path="/feeds/:id/edit" element={<FeedEditorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter basename="/admin">
      <AppShell />
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
