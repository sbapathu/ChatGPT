import React, { useEffect, useRef, useState } from 'react';
import { api, streamChat, getToken, setToken, clearToken } from './services/api';
import { MessageSquarePlus, Send, LogOut, Menu, X, Bot, UserRound, LogIn, LoaderCircle, Square } from 'lucide-react';
import "./App.css";

function getReply(data) {
  for (const key of ['reply', 'response', 'answer', 'assistant_message', 'content']) {
    if (typeof data?.[key] === 'string') return data[key];
    if (typeof data?.[key]?.content === 'string') return data[key].content;
  }
  if (typeof data?.message === 'string') return data.message;
  return JSON.stringify(data);
}

function normalizeMessages(data) {
  const items = Array.isArray(data) ? data : data?.messages || [];
  return items.map((item, index) => ({ id: item.id ?? index, role: item.role === 'assistant' ? 'assistant' : 'user', content: item.content ?? item.message ?? '' }));
}

function AuthForm({ onClose, onSuccess }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('');
    try {
      if (mode === 'register') {
        await api.register({ email, password, full_name: name });
      }
      const result = await api.login({ email, password });
      const token = result.access_token || result.token;
      if (!token) throw new Error('Login succeeded but no access token was returned.');
      setToken(token); await onSuccess(); onClose();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={e => e.stopPropagation()}>
    <button className="close" onClick={onClose} aria-label="Close"><X size={20}/></button>
    <div className="logo"><Bot size={24}/></div><h2>{mode === 'login' ? 'Welcome back' : 'Create an account'}</h2>
    <p>Sign in to save and revisit your conversations.</p>
    <form onSubmit={submit}>
      {mode === 'register' && <label>Full name<input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" required /></label>}
      <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required /></label>
      <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength={8} required /></label>
      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={busy}>{busy ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
    </form>
    <button className="switch" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>{mode === 'login' ? 'New here? Create an account' : 'Already registered? Sign in'}</button>
  </div></div>;
}

export default function App() {
  const [token, setTokenState] = useState(getToken());
  const [user, setUser] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [authOpen, setAuthOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottom = useRef(null);
  const textRef = useRef(null);
  const abortRef = useRef(null);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);
  useEffect(() => {
    if (!token) { setUser(null); setConversations([]); return; }
    let active = true;
    Promise.all([api.me(), api.conversations()]).then(([me, list]) => {
      if (active) { setUser(me); setConversations(Array.isArray(list) ? list : list?.conversations || []); }
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [token]);
  async function loggedIn() { setTokenState(getToken()); setConversationId(null); setMessages([]); }
  function logout() { abortRef.current?.abort(); clearToken(); setTokenState(null); setUser(null); setConversationId(null); setMessages([]); setConversations([]); setError(''); }
  function newChat() { setConversationId(null); setMessages([]); setError(''); setSidebarOpen(false); textRef.current?.focus(); }
  async function openConversation(id) {
    if (loading) return;
    setError(''); setSidebarOpen(false);
    try { const data = await api.conversation(id); setConversationId(id); setMessages(normalizeMessages(data)); }
    catch (err) { setError(err.message); }
  }
  async function send(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || loading) return;
    if (!token) { setAuthOpen(true); setError('Please sign in to stream and save chats.'); return; }
    const assistantId = `a-${crypto.randomUUID()}`;
    const controller = new AbortController();
    abortRef.current = controller;
    setInput(''); setError(''); setLoading(true);
    setMessages(prev => [...prev,
      { id: `u-${crypto.randomUUID()}`, role: 'user', content: message },
      { id: assistantId, role: 'assistant', content: '', status: 'streaming' }
    ]);
    try {
      await streamChat(message, conversationId, {
        signal: controller.signal,
        onMeta: data => setConversationId(data.conversation_id),
        onToken: chunk => setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + chunk } : m)),
        onDone: data => setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, status: 'completed', serverId: data.assistant_message_id } : m))
      });
      const list = await api.conversations();
      setConversations(Array.isArray(list) ? list : list?.conversations || []);
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message);
      setMessages(prev => prev.map(m => m.id === assistantId
        ? { ...m, status: controller.signal.aborted ? 'cancelled' : 'failed' } : m));
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setLoading(false);
    }
  }
  function stopGenerating() { abortRef.current?.abort(); }
  return <div className="app">
    {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
      <div className="sidebar-head"><span className="brand"><Bot size={23}/> Modern Chat</span><button className="icon-btn mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X size={20}/></button></div>
      <button className="new-chat" onClick={newChat}><MessageSquarePlus size={18}/> New chat</button>
      <div className="history-title">Your conversations</div>
      <div className="history">{token ? (conversations.length ? conversations.map(c => <button key={c.id} className={`history-item ${conversationId === c.id ? 'selected' : ''}`} onClick={() => openConversation(c.id)} title={c.title || `Chat ${c.id}`}><span>{c.title || `Conversation ${c.id}`}</span></button>) : <p className="empty-history">No saved conversations yet.</p>) : <p className="empty-history">Sign in to save your chat history.</p>}</div>
      <div className="sidebar-foot">{token ? <><span className="account-name">{user?.full_name || user?.email || 'Signed in'}</span><button onClick={logout}><LogOut size={17}/> Log out</button></> : <button onClick={() => setAuthOpen(true)}><LogIn size={17}/> Sign in / Register</button>}</div>
    </aside>
    <main className="main"><header className="topbar"><button className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu size={22}/></button><span>Modern Chat <span className="model-tag">Ollama</span></span>{!token && <button className="header-login" onClick={() => setAuthOpen(true)}>Sign in</button>}</header>
      <div className="messages-scroll"><div className={`messages ${messages.length === 0 ? 'welcome-container' : ''}`}>
        {messages.length === 0 ? <div className="welcome"><div className="welcome-icon"><Bot size={34}/></div><h1>How can I help you today?</h1><p>Ask anything. Powered by your local Ollama model.</p></div> : messages.map(m => <div className={`message ${m.role}`} key={m.id}><div className="avatar">{m.role === 'assistant' ? <Bot size={18}/> : <UserRound size={18}/>}</div><div className="message-body">{m.content}</div></div>)}
        
        <div ref={bottom}/></div></div>
      <div className="composer-area">{error && <div className="chat-error">{error}</div>}<form className="composer" onSubmit={send}><textarea ref={textRef} rows={1} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form.requestSubmit(); } }} placeholder="Message Modern Chat..." aria-label="Message"/>{loading ? <button type="button" onClick={stopGenerating} aria-label="Stop generating"><Square size={19}/></button> : <button type="submit" disabled={!input.trim()} aria-label="Send message"><Send size={19}/></button>}</form><div className="disclaimer">{token ? 'Your conversations are saved to your backend.' : 'Sign in to enable streaming and saved chat history.'}</div></div>
    </main>{authOpen && <AuthForm onClose={() => setAuthOpen(false)} onSuccess={loggedIn}/>}</div>;
}
