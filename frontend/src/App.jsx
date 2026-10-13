
import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = "http://localhost:8000/api";

export default function App() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState(null);
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function authRequest(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(
        `${API}/auth/${mode === "register" ? "register" : "login"}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Authentication failed");
      }

      setToken(data.access_token);
      setUser(data.user);
      setPassword("");
      setMessages([]);
    } catch (err) {
      setError(err.message || "Could not connect to server");
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const text = input.trim();

    if (!text || loading || !token) return;

    const updated = [
      ...messages,
      { role: "user", content: text },
    ];

    setMessages(updated);
    setInput("");
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ messages: updated }),
      });

      const data = await response.json();

      if (response.status === 401) {
        setToken("");
        setUser(null);
        setMessages([]);
        throw new Error("Session expired. Please log in again.");
      }

      if (!response.ok) {
        throw new Error(data.detail || "Chat request failed");
      }

      setMessages([
        ...updated,
        { role: "assistant", content: data.reply },
      ]);
    } catch (err) {
      setError(err.message || "Unable to reach the AI");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setToken("");
    setUser(null);
    setMessages([]);
    setInput("");
    setError("");
    setMode("login");
  }

  function newChat() {
    setMessages([]);
    setInput("");
    setError("");
  }

  if (!token || !user) {
    return (
      <main className="auth-page">
        <form className="auth-card" onSubmit={authRequest}>
          <h1>ChatGpt Local</h1>
          <p>
            {mode === "login"
              ? "Sign in to your AI assistant"
              : "Create your account"}
          </p>

          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={
              mode === "login"
                ? "current-password"
                : "new-password"
            }
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          {mode === "register" && (
            <small>Password must contain at least 8 characters.</small>
          )}

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" disabled={loading}>
            {loading
              ? "Please wait..."
              : mode === "login"
              ? "Login"
              : "Create account"}
          </button>

          <p className="switch-mode">
            {mode === "login"
              ? "New here?"
              : "Already have an account?"}{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
            >
              {mode === "login" ? "Register" : "Login"}
            </button>
          </p>
        </form>
      </main>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>ChatGpt AI</h2>
        <button onClick={newChat}>+ New chat</button>        
      </aside>

      <main className="chat">
        <header className="topbar">
          <strong>ChatGPT Clone</strong>
          <div className="account">
            <p><b>{user.email}</b></p>
            <button onClick={logout}><b>Logout</b></button>
          </div>
        </header>

        <section className="messages">
          {messages.length === 0 && (
            <div className="welcome">
              <h1>What can I help with?</h1>
              <p>You're signed in. Ask your AI a question.</p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              className={`message ${message.role}`}
              key={index}
            >
              <div className="avatar">
                {message.role === "user" ? "You" : "AI"}
              </div>
              <div className="content">
                <strong>
                  {message.role === "user" ? "You" : "Assistant"}
                </strong>
                <p>{message.content}</p>
              </div>
            </div>
          ))}

          {loading && <p className="thinking">AI is thinking...</p>}
          {error && <p className="auth-error">{error}</p>}
          <div ref={bottomRef} />
        </section>

        <form className="composer" onSubmit={sendMessage}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
              }
            }}
            placeholder="Message your AI..."
            rows={2}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            ↑
          </button>
        </form>

        <p className="disclaimer">
          AI responses may not accurate.
        </p>
      </main>
    </div>
  );
}
