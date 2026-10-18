"""
FieldAI — fully operational web demo.
Real WhatsApp Web integration via Selenium + Chrome (no mock data).

Sidebar: product branding, API key input, anti-ban warning, ➕ Link WhatsApp.
Clicking Link launches a real Chrome instance, opens web.whatsapp.com, extracts
the live QR code for scanning. Once scanned, unlocks two tabs:
  💬 WhatsApp — live synced chat stream from the connected account.
  🧠 AI Overview — live contacts table, AI activity log, human-like typing replies.

Run:  streamlit run app.py
"""

import base64
import os
import random
import time
from datetime import datetime

import streamlit as st

from wa_engine import WhatsAppEngine, QR_IMAGE_PATH, STATE_DIR
from ai_brain import generate_reply

st.set_page_config(page_title="FieldAI — Live Demo", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

CSS = r"""
<style>
:root { --ink:#060E17; --card:#0F1724; --line:#1F2A3A; --cyan:#22D3EE;
  --green:#00FF88; --amber:#FBBF24; --red:#EF4444; --muted:#94A3B8; }
.stApp { background: var(--ink); color: #E2E8F0; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;}
header[data-testid="stHeader"] {background: var(--ink); border-bottom: 1px solid var(--line);}
.brand { display:flex; align-items:center; gap:10px; margin-bottom:6px; }
.logo-sym { width:34px; height:34px; border-radius:10px;
  background: linear-gradient(135deg, #00F3FF 0%, #00FF88 100%);
  display:grid; place-items:center; font-weight:900; font-size:18px; color:#020617;
  box-shadow: 0 0 24px rgba(0,243,238,0.35); }
.brand-title { font-size:20px; font-weight:800; letter-spacing:-0.5px;
  background: linear-gradient(90deg, #22D3EE, #00FF88);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.brand-sub { font-size:11px; color: var(--muted); margin-top:2px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius:14px;
  padding:16px; margin:10px 0; box-shadow: 0 8px 30px rgba(0,0,0,0.35); }
.card-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.badge { display:inline-flex; align-items:center; gap:6px; padding:2px 10px; border-radius:999px;
  font-size:11px; font-weight:700; border:1px solid var(--line); background:#0B1220; }
.badge-live { color: var(--green); border-color: rgba(0,255,136,0.25); background: rgba(0,255,136,0.08); }
.badge-sim { color: var(--amber); border-color: rgba(251,191,36,0.25); background: rgba(251,191,36,0.08); }
.badge-red { color: var(--red); border-color: rgba(239,68,68,0.25); background: rgba(239,68,68,0.08); }
.warn { background: rgba(124,58,237,0.10); border: 1px solid rgba(168,85,247,0.35);
  color: #E9D5FF; border-radius:12px; padding:14px 18px; margin:12px 0;
  display:flex; align-items:flex-start; gap:12px; font-size:13.5px; line-height:1.5; }
.warn b { color: #F5F3FF; }
.chat-wrap { height: 60vh; overflow-y: auto; border: 1px solid var(--line); border-radius:14px;
  background: #0A101C; padding:16px; display:flex; flex-direction:column; gap:10px; margin-bottom:12px; }
.msg { display:flex; gap:10px; margin: 4px 0; }
.msg.ai { justify-content: flex-start; }
.msg.lead { justify-content: flex-end; }
.bubble { max-width: 72%; padding: 10px 14px; border-radius: 16px; font-size: 14px;
  line-height: 1.45; white-space: pre-wrap; }
.bubble.ai { background: #142032; border: 1px solid var(--line); color: #E2E8F0; border-bottom-left-radius: 4px; }
.bubble.lead { background: #0B6BFF; color: #fff; border-bottom-right-radius: 4px; }
.msg-meta { font-size: 10.5px; color: var(--muted); margin-top: 4px; display:block; }
.typing { color: var(--cyan); font-size: 13px; font-style: italic; margin-top: 6px; }
.qr-card { text-align:center; margin: 12px 0; }
.qr-img { border: 1px solid var(--line); border-radius: 12px; background: #fff; padding: 6px; }
.metric { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.metric-val { font-size: 20px; font-weight: 800; color: #E2E8F0; }
.plan-item { background: #0B1220; border: 1px solid var(--line); border-radius: 12px; padding: 12px; margin-bottom: 10px; }
.profile-pin { margin-top: 26px; padding-top: 16px; border-top: 1px solid var(--line);
  display:flex; align-items:center; gap:12px; font-size: 13px; }
.profile-avatar { width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, #22D3EE, #00FF88); display:grid; place-items:center;
  font-weight:800; color: #020617; font-size: 16px; }
.profile-name { font-weight: 700; color: #E2E8F0; }
.profile-sub { color: var(--muted); font-size: 11px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- state
def _new_engine():
    return WhatsAppEngine()

DEFAULTS = {
    "engine": _new_engine(),
    "api_key": "",
    "mode": "simulation",
    "linked": False,
    "qr_step": 0,      # 0 none, 1 show qr
    "active": None,
    "replied": {},     # contact name -> last lead ts we answered
    "activity": [],
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def now_ts() -> str:
    return datetime.now().strftime("%H:%M, %d/%m/%Y")


def log_activity(kind: str, text: str):
    st.session_state.activity.insert(0, (kind, text, now_ts()))
    st.session_state.activity = st.session_state.activity[:12]


# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="logo-sym">FA</div><div>'
        '<div class="brand-title">FieldAI</div>'
        '<div class="brand-sub">Live WhatsApp sales brain</div></div></div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # API key input at top
    st.markdown("### 🔑 Live AI key")
    key_in = st.text_input(
        "GROQ API key (optional)",
        value=st.session_state.api_key,
        type="password",
        placeholder="gsk_…",
        help="Leave empty — demo runs in simulation mode.",
    )
    if key_in != st.session_state.api_key:
        st.session_state.api_key = key_in.strip()
        os.environ["GROQ_API_KEY"] = st.session_state.api_key
        st.rerun()
    st.markdown(
        f'<span class="badge {"badge-live" if st.session_state.api_key else "badge-sim"}>'
        f'● {"LIVE — Groq" if st.session_state.api_key else "SIMULATION"}</span>',
        unsafe_allow_html=True,
    )
    st.caption("Key lives only in this session; nothing is stored.")
    st.divider()

    # Anti-ban warning
    st.markdown(
        '<div class="warn">'
        '<b>⚠️ Anti-ban safety.</b> Always connect a <b>backup WhatsApp account</b> '
        'for testing — never your main account. FieldAI paces every reply like a '
        'human (reading + typing delays) to reduce ban risk, but any automation '
        'carries risk. Use a spare line.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Link WhatsApp
    st.markdown("### 📱 WhatsApp")
    if not st.session_state.linked:
        st.markdown('<span class="badge badge-red">● Not linked</span>', unsafe_allow_html=True)
        st.caption("Click below to open a real Chrome browser to WhatsApp Web.")
        if st.button("➕ Link WhatsApp", use_container_width=True, type="primary"):
            eng = st.session_state.engine
            eng.start()
            st.session_state.qr_step = 1
            st.rerun()
    else:
        st.markdown('<span class="badge badge-green">● WhatsApp linked</span>', unsafe_allow_html=True)
        st.caption("Real session — all messages route through the connected account.")
        if st.button("🔌 Disconnect", use_container_width=True):
            st.session_state.engine.stop()
            st.session_state.linked = False
            st.session_state.qr_step = 0
            st.session_state.active = None
            st.session_state.replied = {}
            st.rerun()

    # QR modal
    if st.session_state.qr_step == 1 and not st.session_state.linked:
        st.divider()
        st.markdown("### 📷 Scan to link")
        img_bytes = st.session_state.engine.qr_image()
        if img_bytes:
            st.image(img_bytes, caption="WhatsApp Web QR code — scan with your backup account", width=260)
        else:
            st.info("Waiting for QR code from Chrome…")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ I scanned the code", use_container_width=True, type="primary"):
                # poll a moment for auth
                time.sleep(3)
                eng = st.session_state.engine
                eng.sync()
                if eng.linked():
                    st.session_state.linked = True
                    st.session_state.qr_step = 0
                    st.session_state.active = None
                    log_activity("system", "WhatsApp account linked")
                    st.rerun()
                else:
                    st.error("Not detected yet — scan the QR code and try again.")
        with col2:
            if st.button("↻ Refresh QR", use_container_width=True):
                eng = st.session_state.engine
                eng.sync()
                st.rerun()

    st.divider()
    st.markdown(
        '<div class="profile-pin">'
        '<div class="profile-avatar">NT</div>'
        '<div><div class="profile-name">Demo User</div>'
        '<div class="profile-sub">FieldAI • demo workspace</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- helpers
def engine_sync():
    eng = st.session_state.engine
    eng.sync()
    with eng.lock:
        st.session_state.contacts = dict(eng.contacts)


def needs_reply(name: str, chats: list) -> bool:
    if not chats:
        return False
    last = chats[-1]
    if last["who"] != "lead":
        return False
    last_ts = last.get("ts", "")
    return st.session_state.replied.get(name) != last_ts


def do_ai_reply(name: str, chats: list) -> str:
    eng = st.session_state.engine
    hist = [[m["who"], m["text"], m.get("ts", "")] for m in chats[-14:]]
    placeholder = st.empty()
    placeholder.markdown(
        '<div class="msg ai"><div class="bubble ai"><span class="typing">Ntokozo is typing…</span></div></div>',
        unsafe_allow_html=True,
    )
    reply = generate_reply(eng, name, hist)
    # type out char by char
    shown = ""
    reveal = st.empty()
    for ch in reply:
        shown += ch
        reveal.markdown(
            f'<div class="msg ai"><div class="bubble ai">{shown}<span class="typing">▋</span></div></div>',
            unsafe_allow_html=True,
        )
        time.sleep(random.uniform(0.03, 0.07))
    reveal.empty()
    ok = eng.send(name, reply)
    ts = now_ts()
    chats.append({"who": "ai", "text": reply, "ts": ts})
    st.session_state.replied[name] = ts
    log_activity("ai", f"Replied to {name}: “{reply[:40]}…”" if len(reply) > 40 else f"Replied to {name}: “{reply}”")
    return reply


# --------------------------------------------------------------------------- main
if not st.session_state.linked:
    st.markdown("## 👋 Welcome to FieldAI")
    st.write(
        "Connect your WhatsApp account to see live chats and let the AI sell for you. "
        "Everything is real — no mock data. Use a **backup** WhatsApp account."
    )
else:
    # keep the engine alive & sync live data on every render
    eng = st.session_state.engine
    if eng.status in ("linked", "qr"):
        engine_sync()
        if eng.status == "linked":
            st.session_state.linked = True

    tabs = st.tabs(["💬 WhatsApp", "🧠 AI Overview"])

    # ================= TAB 1: WhatsApp live view =================
    with tabs[0]:
        contacts = st.session_state.get("contacts", {})
        names = list(contacts.keys())
        if not names:
            st.info("Waiting for chats to load from WhatsApp…")
        else:
            if st.session_state.active not in names:
                st.session_state.active = names[0]
            active_name = st.selectbox("Conversation", names, index=names.index(st.session_state.active))
            st.session_state.active = active_name
            chats = contacts.get(active_name, [])

            st.markdown(
                f'<div class="card-header"><div><div style="font-size:16px;font-weight:800">{active_name}</div>'
                f'<div style="font-size:12px;color:#94A3B8">Live chat from connected WhatsApp</div></div>'
                f'<span class="badge badge-green">● Synced live</span></div>',
                unsafe_allow_html=True,
            )

            box = st.container(height=520)
            with box:
                for m in chats:
                    cls = "msg ai" if m["who"] == "ai" else "msg lead"
                    bubble = "bubble ai" if m["who"] == "ai" else "bubble lead"
                    label = "Ntokozo (AI)" if m["who"] == "ai" else active_name
                    st.markdown(
                        f'<div class="msg {cls}"><div class="{bubble}">{m["text"]}'
                        f'<span class="msg-meta">{label} • {m.get("ts","")}</span></div></div>',
                        unsafe_allow_html=True,
                    )
                if not chats:
                    st.caption("No messages yet.")

            # auto-reply: instant when lead messages
            if needs_reply(active_name, chats):
                do_ai_reply(active_name, chats)
                st.rerun()

            txt = st.text_input("Send as AI", placeholder="Type your reply…", key="ai_out")
            if st.button("Send ↩️", use_container_width=True, type="primary", disabled=not txt.strip()):
                eng.send(active_name, txt.strip())
                chats.append({"who": "ai", "text": txt.strip(), "ts": now_ts()})
                st.session_state.replied[active_name] = now_ts()
                log_activity("ai", f"Sent to {active_name}: “{txt.strip()[:40]}…”")
                st.rerun()

    # ================= TAB 2: AI Overview =================
    with tabs[1]:
        st.markdown("### 🧠 AI Overview & Control Center")
        st.markdown(
            f'<div style="font-size:12px;color:#94A3B8;margin-bottom:14px">'
            f'Mode: {"LIVE — Groq" if st.session_state.api_key else "SIMULATION"}</div>',
            unsafe_allow_html=True,
        )

        # metrics
        total = len(contacts)
        unread = sum(1 for c in contacts.values() for m in c.get("chats", []) if m["who"] == "lead")
        m1, m2, m3 = st.columns(3)
        m1.markdown(f'<div class="card"><div class="metric">Contacts</div><div class="metric-val">{total}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="card"><div class="metric">Unread lead msgs</div><div class="metric-val">{unread}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="card"><div class="metric">Auto-replies</div><div class="metric-val">{len(st.session_state.replied)}</div></div>', unsafe_allow_html=True)

        st.markdown('<div style="font-size:12px;font-weight:700;color:#22D3EE;margin:18px 0 8px 0">📇 Live contacts (from WhatsApp)</div>', unsafe_allow_html=True)
        if not contacts:
            st.info("No contacts yet — sync in progress…")
        else:
            for name, info in contacts.items():
                chats = info.get("chats", [])
                n_lead = sum(1 for m in chats if m["who"] == "lead")
                n_ai = sum(1 for m in chats if m["who"] == "ai")
                last = chats[-1] if chats else None
                status = "Awaiting reply" if (last and last["who"] == "lead") else ("Active" if chats else "New")
                st.markdown(
                    f'<div class="plan-item">'
                    f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                    f'<div><b style="color:#22D3EE">{name}</b>'
                    f'<div style="font-size:12px;color:#94A3B8">{n_lead} in / {n_ai} out • {status}</div></div>'
                    f'<span class="badge badge-{"red" if status=="Awaiting reply" else "green"}">'
                    f'● {status}</span></div>'
                    f'<div style="margin-top:6px;font-size:13px">{("Last: “"+last["text"][:50]+"…" if last and last["text"] else "—")}</div>'
                    f'</div>', unsafe_allow_html=True,
                )

        st.markdown('<div style="font-size:12px;font-weight:700;color:#22D3EE;margin:18px 0 8px 0">🪞 AI activity log</div>', unsafe_allow_html=True)
        for kind, text, ts in st.session_state.activity:
            icon = "🤖" if kind == "ai" else "⚙️"
            st.markdown(f'<div style="font-size:13px; margin:6px 0">{icon} {text} <span style="color:#64748B">[{ts}]</span></div>', unsafe_allow_html=True)
