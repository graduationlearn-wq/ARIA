"""
Chat Route — serves the hosted lead chat page and handles real-time messaging.

Endpoints:
  GET  /chat/{token}          — the chat UI page (what leads open from email)
  POST /chat/{token}/message  — process a lead's message, return ARIA's response
  GET  /chat/{token}/history  — load conversation history (called on page load)
  GET  /chat/admin/{lead_id}  — team view of a lead's conversation (no token needed)

How it fits in the pipeline:
  Lead receives email → clicks "Chat with us" → lands here → ARIA qualifies them
  → CRM updates in real time → alert fires when lead is ready for human contact
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.lead import Lead
from models.interaction import Interaction
from models.escalation import Escalation
from models.demo import Demo
from services.chat_flow import (
    get_welcome_message,
    get_next_guided_step,
    parse_guided_answer,
    extract_software_name,
    should_alert_human,
    get_contextual_options,
    get_flow_complete_message,
    get_reengage_message,
)
from services.intent_classifier import classify_intent, should_escalate
from services.kb_lookup import get_answer_for_intent
from services.llm import generate_chat_response
from services.lead_scorer import apply_engagement_delta, score_to_quality, compute_initial_score
from services.alert_mailer import send_human_alert
from services.demo_mailer import send_demo_confirmation
from utils.whatsapp_sender import send_demo_whatsapp, send_alert_whatsapp

router = APIRouter(prefix="/chat", tags=["Chat"])


# ─────────────────────────────────────────────────────────────────────────────
# Chat page HTML
# ─────────────────────────────────────────────────────────────────────────────

CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#1e3a8a">
<title>BeyondSure — Chat with ARIA</title>
<style>
  /* ── Reset & base ── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { height: 100%; }
  body {
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    /* Layered background: mesh gradient + subtle dot grid */
    background-color: #0d1b3e;
    background-image:
      radial-gradient(ellipse 80% 60% at 20% 10%,  rgba(59,130,246,.22) 0%, transparent 60%),
      radial-gradient(ellipse 60% 50% at 80% 80%,  rgba(16,185,129,.14) 0%, transparent 55%),
      radial-gradient(ellipse 50% 40% at 60% 20%,  rgba(139,92,246,.10) 0%, transparent 50%),
      radial-gradient(ellipse 70% 60% at 10% 80%,  rgba(30,58,138,.30) 0%, transparent 60%),
      /* dot grid */
      radial-gradient(circle, rgba(255,255,255,.055) 1px, transparent 1px);
    background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%, 28px 28px;
    display: flex; align-items: center; justify-content: center;
    position: relative;
  }
  /* Soft vignette to frame the page */
  body::before {
    content: '';
    position: fixed; inset: 0; pointer-events: none;
    background: radial-gradient(ellipse 100% 100% at 50% 50%,
      transparent 40%, rgba(5,10,25,.55) 100%);
  }

  /* ══════════════════════════════════════════════
     DESKTOP LAYOUT  (≥ 769px)
     Two-panel: sidebar on left, chat on right
  ══════════════════════════════════════════════ */
  .page {
    display: flex;
    width: 96vw;
    max-width: 1040px;
    height: 88vh;
    max-height: 760px;
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 32px 80px rgba(10,20,60,.2), 0 8px 24px rgba(10,20,60,.1);
  }

  /* ── Left sidebar ── */
  .sidebar {
    width: 320px;
    flex-shrink: 0;
    background: #0f1e45;
    color: #fff;
    display: flex;
    flex-direction: column;
    padding: 36px 28px 28px;
    position: relative;
    overflow: hidden;
  }
  /* decorative background shapes */
  .sidebar::before {
    content: '';
    position: absolute;
    width: 360px; height: 360px; border-radius: 50%;
    background: radial-gradient(circle, rgba(59,130,246,.18) 0%, transparent 70%);
    bottom: -100px; right: -120px; pointer-events: none;
  }
  .sidebar::after {
    content: '';
    position: absolute;
    width: 200px; height: 200px; border-radius: 50%;
    background: radial-gradient(circle, rgba(16,185,129,.12) 0%, transparent 70%);
    top: -60px; left: -60px; pointer-events: none;
  }

  .sb-brand {
    display: flex; align-items: center; gap: 13px;
    margin-bottom: 36px; position: relative; z-index: 1;
  }
  .sb-brand-logo {
    width: 50px; height: 50px;
    background: #fff;
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 800;
    color: #1e3a8a;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(0,0,0,.25);
  }
  .sb-brand-name { font-size: 19px; font-weight: 700; letter-spacing: -.4px; }
  .sb-brand-tag  { font-size: 11px; opacity: .5; margin-top: 3px; letter-spacing: .2px; }

  .sb-tagline {
    font-size: 21px; font-weight: 700; line-height: 1.35;
    letter-spacing: -.4px;
    margin-bottom: 8px;
    position: relative; z-index: 1;
  }
  .sb-tagline em { font-style: normal; color: #60a5fa; }

  .sb-desc {
    font-size: 13px; line-height: 1.65; opacity: .55;
    margin-bottom: 32px;
    position: relative; z-index: 1;
  }

  .sb-features { display: flex; flex-direction: column; gap: 16px; position: relative; z-index: 1; }
  .sb-feat { display: flex; align-items: flex-start; gap: 12px; }
  .sb-feat-ico {
    width: 34px; height: 34px; flex-shrink: 0;
    background: rgba(255,255,255,.07);
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; margin-top: 1px;
  }
  .sb-feat-body strong { display: block; font-size: 13px; font-weight: 600; margin-bottom: 2px; }
  .sb-feat-body span   { font-size: 11.5px; opacity: .48; line-height: 1.4; }

  .sb-divider { height: 1px; background: rgba(255,255,255,.08); margin: 28px 0; position: relative; z-index: 1; }

  .sb-trust { position: relative; z-index: 1; margin-top: auto; }
  .sb-trust-label { font-size: 10.5px; opacity: .4; text-transform: uppercase; letter-spacing: .7px; font-weight: 600; margin-bottom: 10px; }
  .sb-pills { display: flex; flex-wrap: wrap; gap: 7px; }
  .sb-pill {
    font-size: 11.5px; background: rgba(255,255,255,.07);
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 20px; padding: 4px 11px; opacity: .75;
  }

  /* ── Right chat panel ── */
  .chat-panel {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column;
    background: #fff;
  }

  .chat-header {
    padding: 15px 22px;
    border-bottom: 1px solid #eaeff7;
    display: flex; align-items: center; gap: 12px;
    flex-shrink: 0; background: #fff;
  }
  .ch-ava {
    width: 42px; height: 42px; flex-shrink: 0;
    background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 17px; font-weight: 700;
    letter-spacing: -.5px;
  }
  .ch-info h3 { font-size: 15px; font-weight: 700; color: #0f172a; letter-spacing: -.2px; }
  .ch-info p  {
    font-size: 12px; color: #64748b;
    margin-top: 2px;
    display: flex; align-items: center; gap: 5px;
  }
  .online-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #10b981; flex-shrink: 0;
    animation: blink 2.4s ease-in-out infinite;
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.4} }

  .ch-badge {
    margin-left: auto;
    font-size: 11px; color: #94a3b8;
    background: #f8fafc; border: 1px solid #e8edf5;
    padding: 4px 11px; border-radius: 20px;
    white-space: nowrap;
  }

  /* Messages */
  .messages {
    flex: 1; overflow-y: auto;
    padding: 26px 22px 10px;
    display: flex; flex-direction: column; gap: 2px;
    background: #f9fbfe;
    scroll-behavior: smooth;
    -webkit-overflow-scrolling: touch;
  }
  .messages::-webkit-scrollbar { width: 4px; }
  .messages::-webkit-scrollbar-track { background: transparent; }
  .messages::-webkit-scrollbar-thumb { background: #d1d9e6; border-radius: 10px; }

  .msg-group { display: flex; flex-direction: column; margin-bottom: 4px; }
  .msg-group.aria { align-items: flex-start; }
  .msg-group.user { align-items: flex-end; }

  .bubble {
    max-width: 72%;
    padding: 11px 16px;
    font-size: 14.5px; line-height: 1.65;
    word-break: break-word; white-space: pre-wrap;
  }
  .aria .bubble {
    background: #fff; color: #0f172a;
    border-radius: 4px 18px 18px 18px;
    border: 1px solid #e4eaf4;
    box-shadow: 0 1px 5px rgba(15,23,42,.06);
  }
  .user .bubble {
    background: #1e3a8a; color: #fff;
    border-radius: 18px 4px 18px 18px;
  }
  .bubble a { color: inherit; text-decoration: underline; word-break: break-all; }
  .user .bubble a { color: rgba(255,255,255,.82); }

  .msg-ts { font-size: 10.5px; color: #94a3b8; margin-top: 4px; padding: 0 3px; }

  .date-div {
    display: flex; align-items: center; gap: 12px;
    margin: 8px 0 18px;
    font-size: 11px; color: #94a3b8; font-weight: 500; letter-spacing: .3px;
  }
  .date-div::before, .date-div::after { content:''; flex:1; height:1px; background:#e8edf5; }

  /* Quick-reply chips */
  .opts-wrap {
    display: flex; flex-wrap: wrap; gap: 8px;
    max-width: 76%;
    align-self: flex-start;
    margin: 8px 0 6px;
  }
  .opt-btn {
    background: #fff; color: #1e3a8a;
    border: 1.5px solid #c3d0ed;
    border-radius: 20px; padding: 8px 16px;
    font-size: 13.5px; font-weight: 500;
    font-family: inherit; cursor: pointer;
    transition: background .14s, border-color .14s, transform .1s, box-shadow .14s;
    -webkit-tap-highlight-color: transparent; user-select: none;
  }
  .opt-btn:hover:not(:disabled) {
    background: #eff4ff; border-color: #1e3a8a;
    transform: translateY(-1px);
    box-shadow: 0 3px 12px rgba(30,58,138,.12);
  }
  .opt-btn:active:not(:disabled) { transform: none; box-shadow: none; }
  .opt-btn:disabled { opacity: .35; cursor: default; transform: none; }

  /* Typing */
  .typing-wrap { display: flex; margin-bottom: 8px; }
  .typing-bubble {
    background: #fff; border: 1px solid #e4eaf4;
    border-radius: 4px 18px 18px 18px;
    padding: 12px 16px;
    display: flex; gap: 4px; align-items: center;
    box-shadow: 0 1px 5px rgba(15,23,42,.06);
  }
  .td { width: 6px; height: 6px; border-radius: 50%; background: #94a3b8; animation: tdot 1.3s ease-in-out infinite; }
  .td:nth-child(2) { animation-delay:.16s; }
  .td:nth-child(3) { animation-delay:.32s; }
  @keyframes tdot { 0%,60%,100%{transform:translateY(0);opacity:.4} 30%{transform:translateY(-5px);opacity:1} }

  /* Escalated */
  .escalated-banner {
    background: #fffbeb; border-top: 1px solid #fcd34d;
    padding: 11px 22px; font-size: 13px; font-weight: 500;
    color: #78350f; text-align: center;
    display: none; flex-shrink: 0;
  }

  /* Input */
  .input-area {
    padding: 14px 22px 18px;
    background: #fff; border-top: 1px solid #eaeff7;
    flex-shrink: 0;
  }
  .input-row {
    display: flex; gap: 10px; align-items: flex-end;
    background: #f4f7fc; border: 1.5px solid #dde5f4;
    border-radius: 28px;
    padding: 7px 7px 7px 18px;
    transition: border-color .15s, box-shadow .15s;
  }
  .input-row:focus-within {
    border-color: #1e3a8a; background: #fff;
    box-shadow: 0 0 0 3px rgba(30,58,138,.08);
  }
  .msg-input {
    flex: 1; border: none; background: transparent;
    padding: 5px 0; font-size: 14.5px; font-family: inherit;
    resize: none; outline: none; max-height: 100px;
    line-height: 1.5; color: #0f172a; overflow-y: auto;
  }
  .msg-input::placeholder { color: #a0aec0; }
  .send-btn {
    width: 40px; height: 40px;
    background: #1e3a8a; border: none; border-radius: 50%;
    color: #fff; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    transition: background .14s, transform .1s;
    -webkit-tap-highlight-color: transparent;
  }
  .send-btn:hover:not(:disabled) { background: #1e40af; transform: scale(1.06); }
  .send-btn:active:not(:disabled) { transform: scale(.93); }
  .send-btn:disabled { background: #c2cfe6; cursor: default; transform: none; }

  .input-footer {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 10px; font-size: 11.5px; color: #94a3b8;
  }
  .person-btn {
    background: none; border: none; padding: 0;
    color: #1e3a8a; font-size: 11.5px; font-weight: 500;
    font-family: inherit; cursor: pointer;
    transition: opacity .14s; -webkit-tap-highlight-color: transparent;
  }
  .person-btn:hover { opacity: .65; }

  /* ══════════════════════════════════════════════
     MOBILE  (≤ 768px)
     Full-screen chat, sidebar hidden, branded header
  ══════════════════════════════════════════════ */
  @media (max-width: 768px) {
    html, body { height: 100%; height: -webkit-fill-available; }
    body { background: #1e3a8a; align-items: flex-start; }
    body::before { display: none; }
    .page {
      width: 100%; max-width: 100%;
      height: 100vh; height: -webkit-fill-available;
      border-radius: 0; box-shadow: none;
      max-height: none;
    }
    .sidebar { display: none; }
    /* On mobile the right-side header doubles as the brand header */
    .chat-header {
      background: linear-gradient(140deg, #1e3a8a 0%, #1e40af 100%);
      border-bottom: none; padding: 14px 18px;
    }
    .ch-ava { background: rgba(255,255,255,.2); }
    .ch-info h3 { color: #fff; font-size: 16px; }
    .ch-info p  { color: rgba(255,255,255,.72); }
    .ch-badge   { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.2); color: rgba(255,255,255,.75); }
    .messages   { background: #f9fbfe; padding: 18px 14px 8px; }
    .bubble     { max-width: 86%; font-size: 14px; }
    .opts-wrap  { max-width: 94%; }
    .opt-btn    { font-size: 13px; padding: 9px 14px; }
    .input-area { padding: 12px 14px 16px; }
    .send-btn   { width: 38px; height: 38px; }
  }
</style>
</head>
<body>
<div class="page">

  <!-- ── Sidebar (desktop only) ── -->
  <aside class="sidebar">
    <div class="sb-brand">
      <div class="sb-brand-logo">B</div>
      <div>
        <div class="sb-brand-name">BeyondSure</div>
        <div class="sb-brand-tag">Insurance Business Platform</div>
      </div>
    </div>

    <div class="sb-tagline">Run your insurance<br>business <em>smarter.</em></div>
    <div class="sb-desc">All your leads, policies &amp; commissions managed in one place — so your team spends less time on admin and more time closing.</div>

    <div class="sb-features">
      <div class="sb-feat">
        <div class="sb-feat-ico">📋</div>
        <div class="sb-feat-body">
          <strong>Lead Management</strong>
          <span>Capture, score &amp; follow up — automatically</span>
        </div>
      </div>
      <div class="sb-feat">
        <div class="sb-feat-ico">📄</div>
        <div class="sb-feat-body">
          <strong>Policy Tracking</strong>
          <span>Never miss a renewal or lapse again</span>
        </div>
      </div>
      <div class="sb-feat">
        <div class="sb-feat-ico">💰</div>
        <div class="sb-feat-body">
          <strong>Commission Reports</strong>
          <span>Real-time earnings across all policies</span>
        </div>
      </div>
      <div class="sb-feat">
        <div class="sb-feat-ico">📊</div>
        <div class="sb-feat-body">
          <strong>Business Analytics</strong>
          <span>Know exactly where your pipeline stands</span>
        </div>
      </div>
    </div>

    <div class="sb-divider"></div>

    <div class="sb-trust">
      <div class="sb-trust-label">Built for</div>
      <div class="sb-pills">
        <span class="sb-pill">Agents &amp; IMFs</span>
        <span class="sb-pill">Brokers</span>
        <span class="sb-pill">POSPs</span>
        <span class="sb-pill">Advisors</span>
      </div>
    </div>
  </aside>

  <!-- ── Chat panel ── -->
  <main class="chat-panel">

    <div class="chat-header">
      <div class="ch-ava">AR</div>
      <div class="ch-info">
        <h3>ARIA — BeyondSure Assistant</h3>
        <p><span class="online-dot"></span> Online · Replies in seconds</p>
      </div>
      <div class="ch-badge">🔒 Secure</div>
    </div>

    <div class="messages" id="messages">
      <div class="date-div">Today</div>
    </div>

    <div class="escalated-banner" id="escalatedBanner">
      ✅ Our team has been notified and will reach out to you shortly.
    </div>

    <div class="input-area">
      <div class="input-row">
        <textarea
          class="msg-input"
          id="msgInput"
          placeholder="Type your message…"
          rows="1"
          onkeydown="onKey(event)"
          oninput="autoResize(this)"
        ></textarea>
        <button class="send-btn" id="sendBtn" onclick="send()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
      <div class="input-footer">
        <span>Powered by BeyondSure</span>
        <button class="person-btn" id="personBtn" onclick="askForPerson()">Talk to a person →</button>
      </div>
    </div>

  </main>

</div>

<script>
const TOKEN = "__TOKEN__";
const BASE  = window.location.origin;
let sending = false;

/* ── Utils ───────────────────────────────────────────────────────── */
function fmtTime(ts) {
  if (!ts) return '';
  return new Date(ts).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}
function scrollDown() {
  const m = document.getElementById('messages');
  requestAnimationFrame(() => { m.scrollTop = m.scrollHeight; });
}
function lockOpts() {
  document.querySelectorAll('.opt-btn').forEach(b => b.disabled = true);
}
function setSending(v) {
  sending = v;
  document.getElementById('sendBtn').disabled = v;
}
function linkify(raw) {
  const s = raw
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  return s.replace(/(https?:\\/\\/[^\\s<>"]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
}

/* ── Render ──────────────────────────────────────────────────────── */
function addBubble(role, text, ts, options) {
  const msgs = document.getElementById('messages');
  const grp  = document.createElement('div');
  grp.className = 'msg-group ' + role;

  const bub = document.createElement('div');
  bub.className = 'bubble';
  bub.innerHTML = linkify(text || '');
  grp.appendChild(bub);

  if (ts) {
    const t = document.createElement('div');
    t.className = 'msg-ts';
    t.textContent = fmtTime(ts);
    grp.appendChild(t);
  }
  msgs.appendChild(grp);

  if (options && options.length && role === 'aria') addOptions(options);
  scrollDown();
}

function addOptions(options) {
  const msgs = document.getElementById('messages');
  const wrap = document.createElement('div');
  wrap.className = 'opts-wrap';
  options.forEach(opt => {
    const btn = document.createElement('button');
    btn.className = 'opt-btn';
    btn.textContent = opt;
    btn.onclick = () => { lockOpts(); send(opt); };
    wrap.appendChild(btn);
  });
  msgs.appendChild(wrap);
  scrollDown();
}

function showTyping() {
  const msgs = document.getElementById('messages');
  const d = document.createElement('div');
  d.id = 'typing'; d.className = 'typing-wrap';
  d.innerHTML = '<div class="typing-bubble"><div class="td"></div><div class="td"></div><div class="td"></div></div>';
  msgs.appendChild(d);
  scrollDown();
}
function hideTyping() { const t = document.getElementById('typing'); if (t) t.remove(); }

/* ── Send ────────────────────────────────────────────────────────── */
async function send(text) {
  const inp = document.getElementById('msgInput');
  const msg = (text !== undefined ? text : inp.value).trim();
  if (!msg || sending) return;
  if (text === undefined) { inp.value = ''; inp.style.height = 'auto'; }

  lockOpts(); setSending(true);
  addBubble('user', msg, new Date().toISOString(), null);
  showTyping();

  try {
    const res  = await fetch(`${BASE}/chat/${TOKEN}/message`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg}),
    });
    const data = await res.json();
    await new Promise(r => setTimeout(r, 680));
    hideTyping();

    if (data.escalated) {
      addBubble('aria', data.message, new Date().toISOString(), null);
      document.getElementById('escalatedBanner').style.display = 'block';
      const pb = document.getElementById('personBtn');
      if (pb) pb.style.display = 'none';
    } else {
      addBubble('aria', data.message, new Date().toISOString(), data.options || null);
    }
  } catch(e) {
    hideTyping();
    addBubble('aria', "Sorry, I'm having a connection issue. Please try again in a moment.", new Date().toISOString(), null);
  }
  setSending(false);
}

function onKey(e) { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
function askForPerson() { send("I'd like to speak to a real person please."); }

/* ── Load history ────────────────────────────────────────────────── */
async function loadHistory() {
  try {
    const res  = await fetch(`${BASE}/chat/${TOKEN}/history`);
    const data = await res.json();
    if (data.error) {
      addBubble('aria', "This link appears to be invalid or expired. Please contact BeyondSure directly.", null, null);
      document.getElementById('msgInput').disabled = true;
      document.getElementById('sendBtn').disabled  = true;
      return;
    }
    if (data.messages && data.messages.length > 0) {
      data.messages.forEach(m => addBubble(m.role, m.text, m.timestamp, null));
      if (data.last_options && data.last_options.length) addOptions(data.last_options);
    } else if (data.welcome) {
      addBubble('aria', data.welcome.message, new Date().toISOString(), data.welcome.options);
    }
  } catch(e) {
    addBubble('aria', "Unable to load conversation. Please refresh the page.", null, null);
  }
}

loadHistory();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{token}", response_class=HTMLResponse, tags=["Chat"])
def chat_page(token: str, db: Session = Depends(get_db)):
    """Serve the chat UI. Lead opens this link from their email."""
    lead = db.query(Lead).filter(Lead.chat_token == token).first()
    if not lead:
        return HTMLResponse("<h2>Link not found. Please contact BeyondSure.</h2>", status_code=404)
    return HTMLResponse(CHAT_HTML.replace("__TOKEN__", token))


@router.get("/{token}/history")
def get_chat_history(token: str, db: Session = Depends(get_db)):
    """
    Called by the chat page on load. Returns either:
    - {"messages": [...], "last_options": [...]} if lead has chatted before
    - {"welcome": {message, options}} if first visit
    - {"error": "..."} if token is invalid
    """
    lead = db.query(Lead).filter(Lead.chat_token == token).first()
    if not lead:
        return {"error": "Invalid token"}

    # Mark chat as opened
    if not lead.chat_opened_at:
        lead.chat_opened_at = datetime.utcnow()
        lead.status = "engaged" if lead.status == "new" else lead.status
        db.commit()

    history = (
        db.query(Interaction)
        .filter(
            Interaction.lead_id == lead.id,
            Interaction.message_type.in_(["chat_in", "chat_out"]),
        )
        .order_by(Interaction.timestamp.asc())
        .all()
    )

    if not history:
        return {"messages": [], "welcome": get_welcome_message(lead)}

    messages = [
        {
            "role": "user" if i.direction == "inbound" else "aria",
            "text": i.message_text or "",
            "timestamp": i.timestamp.isoformat() if i.timestamp else None,
        }
        for i in history
    ]

    # Determine what options to show on the last ARIA message
    last_outbound = next(
        (i for i in reversed(history) if i.direction == "outbound"), None
    )
    last_options = []
    if last_outbound:
        next_step = get_next_guided_step(lead)
        if next_step:
            last_options = next_step["options"]
        elif last_outbound.intent_label:
            last_options = get_contextual_options(last_outbound.intent_label)

    return {"messages": messages, "last_options": last_options}


@router.post("/{token}/message")
def chat_message(token: str, body: ChatMessage, db: Session = Depends(get_db)):
    """
    Core message handler. Called every time the lead sends a message.

    Pipeline:
      1. Validate token → get lead
      2. Log inbound interaction
      3. Check if guided flow has a next step → apply CRM update + return next question
      4. If open chat: classify intent → update score → KB lookup → LLM response
      5. Check alert threshold → fire human alert if crossed
      6. Log outbound interaction
      7. Return {message, options, escalated}
    """
    lead = db.query(Lead).filter(Lead.chat_token == token).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Invalid chat token")

    if lead.opt_out:
        return {"message": "You have previously unsubscribed. We won't contact you further.", "options": [], "escalated": False}

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # 1. Log inbound
    inbound = Interaction(
        lead_id=lead.id,
        direction="inbound",
        channel="chat",
        message_text=message,
        message_type="chat_in",
        handled_by="lead",
        send_status=None,
    )
    db.add(inbound)
    lead.last_interaction_at = datetime.utcnow()

    # 2. Classify intent (even during guided flow — catch demo requests early)
    intent = classify_intent(message)
    inbound.intent_label = intent.label
    inbound.intent_confidence = intent.confidence

    # 3. Handle opt-out
    if intent.label == "not_interested":
        lead.opt_out = True
        lead.status = "lost"
        db.commit()
        outbound_text = "No problem at all — I'll make sure we don't contact you again. Best of luck with your business!"
        _log_outbound(lead, outbound_text, "not_interested", db)
        return {"message": outbound_text, "options": [], "escalated": False}

    # 4. Handle escalation (bot detection, wants a human)
    if should_escalate(intent):
        lead.status = "needs_human"
        lead.assigned_to = "human_queue"
        db.flush()  # ensure inbound.id is populated before we reference it
        # ── Write Escalation row (P0 fix) ────────────────────────────────────
        escalation = Escalation(
            lead_id=lead.id,
            interaction_id=inbound.id,
            reason=intent.label,
            assigned_to="human_queue",
        )
        db.add(escalation)
        send_human_alert(lead, intent.label, message, db)
        send_alert_whatsapp(lead, intent.label)
        db.commit()
        outbound_text = (
            "Of course! I've notified our team and someone will reach out to you shortly. "
            "You can also call us directly or reply to your welcome email."
        )
        _log_outbound(lead, outbound_text, intent.label, db)
        return {"message": outbound_text, "options": [], "escalated": True}

    # 5. Check if guided flow still has a step to complete
    current_step = get_next_guided_step(lead)
    if current_step:
        updates = parse_guided_answer(current_step["field"], message, lead)
        action = updates.pop("_action", None)  # extract routing action if present

        # ── Demo step special branches ────────────────────────────────────────
        if current_step["field"] == "willing_for_demo":

            if action == "escalate":
                # "Talk to an expert" — immediate human escalation
                lead.status = "needs_human"
                lead.assigned_to = "human_queue"
                db.flush()
                escalation = Escalation(
                    lead_id=lead.id,
                    interaction_id=inbound.id,
                    reason="escalation_request",
                    assigned_to="human_queue",
                )
                db.add(escalation)
                send_human_alert(lead, "escalation_request", message, db)
                send_alert_whatsapp(lead, "escalation_request")
                db.commit()
                out = (
                    "Of course! 🙌 I've notified our team and someone will reach out "
                    "to you shortly. Feel free to ask anything in the meantime!"
                )
                _log_outbound(lead, out, "escalation_request", db)
                return {"message": out, "options": [], "escalated": True}

            elif action == "reengage":
                # "Maybe later" / "Just exploring" — warm farewell + schedule re-ping
                lead.re_engage_after = datetime.utcnow() + timedelta(days=3)
                lead.willing_for_demo = None  # keep null so flow can ask again on return
                db.commit()
                result = get_reengage_message(lead)
                _log_outbound(lead, result["message"], "objection_timing", db)
                return {"message": result["message"], "options": [], "escalated": False}

            elif action == "demo_book":
                # "Yes, book a demo" — set flag, ask for preferred time next
                # Alert fires AFTER they give their preferred time (demo_confirmed action)
                lead.willing_for_demo = True
                new_score = apply_engagement_delta(lead.lead_score or 0, "demo_request")
                lead.lead_score = new_score
                lead.lead_quality = score_to_quality(new_score)
                db.commit()
                # Get the demo_preference step (next in flow)
                next_step = get_next_guided_step(lead)
                if next_step:
                    _log_outbound(lead, next_step["message"], "demo_request", db)
                    return {"message": next_step["message"], "options": next_step["options"], "escalated": False}
                # Shouldn't happen, but fallback
                out = "When works best for a quick call? Our team will call you directly."
                _log_outbound(lead, out, "demo_request", db)
                return {"message": out, "options": ["This week", "Next week", "Flexible"], "escalated": False}

        # ── Demo preference confirmed → send email + WhatsApp ────────────────
        if current_step["field"] == "demo_preference" and action == "demo_confirmed":
            pref = updates.get("demo_preference", message.strip()[:200])
            lead.demo_preference = pref

            # Score bump for confirmed demo
            new_score = apply_engagement_delta(lead.lead_score or 0, "demo_request")
            lead.lead_score = new_score
            lead.lead_quality = score_to_quality(new_score)
            lead.status = "needs_human"

            db.flush()

            # ── Write Demo row (P0 fix) ───────────────────────────────────────
            # Count existing demos to determine demo_number
            existing_demo_count = db.query(Demo).filter(Demo.lead_id == lead.id).count()
            demo_row = Demo(
                lead_id=lead.id,
                scheduled_preference=pref,
                status="scheduled",
                demo_number=existing_demo_count + 1,
                booked_via="aria_chat",
            )
            db.add(demo_row)

            # Send confirmation email to lead
            send_demo_confirmation(lead, pref)

            # Send WhatsApp confirmation to lead
            send_demo_whatsapp(lead, pref)

            # Fire human alert (email + WhatsApp to team)
            if not lead.alert_sent_at:
                send_human_alert(lead, "demo_request", message, db)
                send_alert_whatsapp(lead, "demo_request")

            db.commit()

            # Build in-chat confirmation message
            out = (
                f"✅ All set — your demo is confirmed!\n\n"
                f"📅  Time: {pref}\n"
                f"📞  Our team will call you directly — you don't need to do anything, "
                f"just be available at your number.\n\n"
                f"We've sent a confirmation to your email. Talk soon! 😊"
            )

            _log_outbound(lead, out, "demo_confirmed", db)
            return {
                "message": out,
                "options": ["What to expect in the demo?", "Any questions for me?"],
                "escalated": False,
            }

        # ── Normal guided step ────────────────────────────────────────────────
        # Profile fields — these affect the 40-pt profile score component
        PROFILE_FIELDS = {"lead_type", "team_size", "uses_software", "open_to_platform"}
        profile_updated = any(f in PROFILE_FIELDS for f in updates)

        for field, value in updates.items():
            setattr(lead, field, value)

        # Score update
        if profile_updated:
            # Recompute the full profile + form-intent score from scratch,
            # then add whatever engagement delta has already accrued.
            # This ensures lead_type=broker + team_size=20 is worth 15+15 pts,
            # not still zero from when the form had lead_type=unknown.
            engagement_portion = max(0, (lead.lead_score or 0) - compute_initial_score(lead))
            new_base = compute_initial_score(lead)  # profile + form intent
            new_score = min(100, new_base + engagement_portion)
        else:
            new_score = apply_engagement_delta(lead.lead_score or 0, intent.label)
        lead.lead_score = new_score
        lead.lead_quality = score_to_quality(new_score)

        db.flush()

        # Check alert threshold
        if should_alert_human(lead, intent.label):
            lead.status = "needs_human"
            send_human_alert(lead, intent.label, message, db)

        next_step = get_next_guided_step(lead)
        db.commit()

        if next_step:
            response_text = next_step["message"]
            options = next_step["options"]
        else:
            # Shouldn't reach here outside demo step, but handle gracefully
            response_text = f"Thanks for sharing all of that! What questions do you have about BeyondSure?"
            options = ["Tell me about pricing", "What features does it have?", "I'd like a demo 📅"]

        _log_outbound(lead, response_text, intent.label, db)
        return {"message": response_text, "options": options, "escalated": False}

    # 6. Open chat — full LLM pipeline

    # ── unclear retry → escalate (P2 fix) ────────────────────────────────────
    # Architecture: "ask clarifying Q once, then escalate — never guess intent."
    if intent.label == "unclear":
        # Count how many consecutive unclear messages at the tail of history
        recent_intents = (
            db.query(Interaction.intent_label)
            .filter(
                Interaction.lead_id == lead.id,
                Interaction.direction == "inbound",
                Interaction.message_type == "chat_in",
            )
            .order_by(Interaction.timestamp.desc())
            .limit(3)
            .all()
        )
        consecutive_unclear = sum(
            1 for (lbl,) in recent_intents if lbl == "unclear"
        )
        if consecutive_unclear >= 1:
            # Already asked once — escalate now
            lead.status = "needs_human"
            lead.assigned_to = "human_queue"
            db.flush()
            escalation = Escalation(
                lead_id=lead.id,
                interaction_id=inbound.id,
                reason="unclear_after_retry",
                assigned_to="human_queue",
            )
            db.add(escalation)
            send_human_alert(lead, "unclear", message, db)
            send_alert_whatsapp(lead, "unclear")
            db.commit()
            out = (
                "I want to make sure I give you the right answer — "
                "let me connect you with one of our team members who can help you directly. "
                "They'll reach out to you shortly! 😊"
            )
            _log_outbound(lead, out, "unclear_escalated", db)
            return {"message": out, "options": [], "escalated": True}
        else:
            # First unclear — ask clarifying question
            db.commit()
            out = "I want to make sure I understand — could you tell me a bit more about what you're looking for?"
            _log_outbound(lead, out, "unclear", db)
            return {
                "message": out,
                "options": ["Tell me about pricing", "I want a demo", "What does BeyondSure do?"],
                "escalated": False,
            }

    new_score = apply_engagement_delta(lead.lead_score or 0, intent.label)
    lead.lead_score = new_score
    lead.lead_quality = score_to_quality(new_score)
    lead.current_intent = intent.label

    # Update status based on intent
    _update_status_from_intent(lead, intent.label)

    # KB lookup
    kb_entry = get_answer_for_intent(intent.label, db)
    kb_context = f"Q: {kb_entry.question}\nA: {kb_entry.answer}" if kb_entry else ""

    # Conversation history (last 6 messages)
    recent = (
        db.query(Interaction)
        .filter(
            Interaction.lead_id == lead.id,
            Interaction.message_type.in_(["chat_in", "chat_out"]),
        )
        .order_by(Interaction.timestamp.desc())
        .limit(6)
        .all()
    )
    history = [
        {
            "role": "user" if i.direction == "inbound" else "assistant",
            "content": i.message_text or "",
        }
        for i in reversed(recent)
        if i.message_text
    ]

    # LLM response
    response_text = generate_chat_response(
        lead=lead,
        intent_label=intent.label,
        incoming_message=message,
        conversation_history=history,
        kb_context=kb_context,
    )

    # Contextual option buttons
    options = get_contextual_options(intent.label)

    # Check alert threshold
    if should_alert_human(lead, intent.label):
        lead.status = "needs_human"
        send_human_alert(lead, intent.label, message, db)

    db.commit()
    _log_outbound(lead, response_text, intent.label, db)

    return {
        "message": response_text,
        "options": options,
        "escalated": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Admin view — team can watch any conversation by lead ID
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/{lead_id}")
def admin_chat_view(lead_id: int, db: Session = Depends(get_db)):
    """
    Returns the full conversation for a lead. Used in the human alert link.
    No token required — internal use only.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    history = (
        db.query(Interaction)
        .filter(Interaction.lead_id == lead_id)
        .order_by(Interaction.timestamp.asc())
        .all()
    )

    return {
        "lead": {
            "id": lead.id,
            "name": lead.first_name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company_name,
            "type": lead.lead_type,
            "team_size": lead.team_size,
            "score": lead.lead_score,
            "quality": lead.lead_quality,
            "status": lead.status,
            "current_software": lead.current_software,
            "uses_software": lead.uses_software,
            "open_to_platform": lead.open_to_platform,
            "willing_for_demo": lead.willing_for_demo,
            "human_priority": lead.human_priority,
            "human_notes": lead.human_notes,
            "alert_sent_at": lead.alert_sent_at,
            "chat_opened_at": lead.chat_opened_at,
        },
        "conversation": [
            {
                "id": i.id,
                "direction": i.direction,
                "role": "lead" if i.direction == "inbound" else "aria",
                "text": i.message_text,
                "intent": i.intent_label,
                "type": i.message_type,
                "timestamp": i.timestamp.isoformat() if i.timestamp else None,
            }
            for i in history
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log_outbound(lead: Lead, text: str, intent: str, db: Session):
    """Persist ARIA's chat response as an outbound interaction."""
    interaction = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="chat",
        message_text=text,
        message_type="chat_out",
        intent_label=intent,
        handled_by="aria",
        send_status="sent",
    )
    db.add(interaction)
    db.commit()


def _update_status_from_intent(lead: Lead, intent: str):
    """Advance lead status based on what they're expressing."""
    if lead.status in ("lost", "needs_human", "contacted"):
        return  # don't downgrade
    status_map = {
        "demo_request":    "needs_human",
        "pricing_query":   "interested",
        "feature_query":   "interested",
        "positive_signal": "interested",
        "greeting":        "engaged",
    }
    new_status = status_map.get(intent)
    if new_status:
        # Only advance, never retreat
        order = ["new", "engaged", "interested", "needs_human"]
        current_idx = order.index(lead.status) if lead.status in order else 0
        new_idx = order.index(new_status) if new_status in order else 0
        if new_idx > current_idx:
            lead.status = new_status


