"""
FieldAI Web Demo — premium SaaS showcase (dark mode).

Text-only live demonstration of the FieldAI WhatsApp sales brain:
  * Logo splash animation on load
  * Sidebar: API key input (top), ➕ Link WhatsApp with QR modal, profile (bottom)
  * Anti-ban warning banner (use a BACKUP WhatsApp account)
  * Split view: live WhatsApp chat (left) + AI Overview & Control Center (right)
  * Human-like typing speed, anti-ban pacing
  * Simulation mode out of the box; live Groq LLM when GROQ_API_KEY is provided

No API keys are hardcoded - live mode reads os.getenv("GROQ_API_KEY") from the
sidebar input at runtime.

Run:  streamlit run app.py
"""

import base64
import io
import os
import random
import time
from datetime import datetime

import streamlit as st

from demo_engine import (
    DEMO_CONTACTS,
    live_reply,
    plan_for_contact,
    seed_history,
    simulate_followup,
    simulate_reply,
)

st.set_page_config(page_title="FieldAI — Live Demo", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

CSS = r"""
<style>
:root {
  --ink: #060E17;
  --card: #0F1724;
  --line: #1F2A3A;
  --cyan: #22D3EE;
  --green: #00FF88;
  --amber: #FBBF24;
  --red: #EF4444;
  --muted: #94A3B8;
}

/* Page */
.stApp { background: var(--ink); color: #E2E8F0; }
[data-testid="stSidebar"] { background: #0B1220; border-right: 1px solid var(--line); }

/* Hide streamlit chrome we don't need */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {background: var(--ink); border-bottom: 1px solid var(--line);}

/* --- Logo / brand --- */
.brand { display:flex; align-items:center; gap:10px; margin-bottom: 6px; }
.logo-sym {
  width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, #00F3FF 0%, #00FF88 100%);
  display: grid; place-items: center; font-weight: 900; font-size: 18px; color: #020617;
  box-shadow: 0 0 24px rgba(0,243,238,0.35);
}
.brand-title { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; background: linear-gradient(90deg, #22D3EE, #00FF88); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.brand-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* --- Cards --- */
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 16px; margin: 10px 0; box-shadow: 0 8px 30px rgba(0,0,0,0.35);
}
.card-header { display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px; }
.badge {
  display:inline-flex; align-items:center; gap:6px; padding: 2px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700; border: 1px solid var(--line); background: #0B1220;
}
.badge-live { color: var(--green); border-color: rgba(0,255,136,0.25); background: rgba(0,255,136,0.08); }
.badge-sim { color: var(--amber); border-color: rgba(251,191,36,0.25); background: rgba(251,191,36,0.08); }
.badge-red { color: var(--red); border-color: rgba(239,68,68,0.25); background: rgba(239,68,68,0.08); }

/* --- Warning banner --- */
.warn {
  background: rgba(124, 58, 237, 0.10); border: 1px solid rgba(168, 85, 247, 0.35);
  color: #E9D5FF; border-radius: 12px; padding: 14px 18px; margin: 12px 0;
  display:flex; align-items:flex-start; gap:12px; font-size: 13.5px; line-height: 1.5;
}
.warn b { color: #F5F3FF; }

/* --- Contact pills --- */
.pill {
  display:flex; align-items:center; gap:10px; padding: 10px 14px; border-radius: 12px;
  border: 1px solid var(--line); background: #0B1220; cursor: pointer; margin-bottom: 8px;
  transition: border 0.15s, background 0.15s;
}
.pill:hover { border-color: var(--cyan); background: #111827; }
.pill.active { border-color: var(--cyan); background: linear-gradient(180deg, rgba(34,211,238,0.12), #0B1220); }
.pill-dot { width: 9px; height: 9px; border-radius: 50%; }
.pill-dot.green { background: var(--green); box-shadow: 0 0 10px var(--green); }
.pill-dot.red { background: var(--red); box-shadow: 0 0 10px var(--red); }
.pill-name { flex:1; font-size: 14px; font-weight: 600; }
.pill-ts { font-size: 11px; color: var(--muted); }

/* --- Chat pane --- */
.chat-wrap { height: 560px; overflow-y: auto; border: 1px solid var(--line); border-radius: 14px;
  background: #0A101C; padding: 16px; display:flex; flex-direction:column; gap:10px;
  margin-bottom: 12px; }
.msg { display:flex; gap:10px; margin: 4px 0; }
.msg.ai { justify-content: flex-start; }
.msg.lead { justify-content: flex-end; }
.bubble {
  max-width: 72%; padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.45;
  white-space: pre-wrap;
}
.bubble.ai { background: #142032; border: 1px solid var(--line); color: #E2E8F0; border-bottom-left-radius: 4px; }
.bubble.lead { background: #0B6BFF; color: #fff; border-bottom-right-radius: 4px; }
.msg-meta { font-size: 10.5px; color: var(--muted); margin-top: 4px; display:block; }
.typing-dots { font-size: 14px; color: var(--muted); animation: blink 1.2s infinite; display:inline-block; }
@keyframes blink { 0%,80%,100% { opacity: 0.3; } 40% { opacity: 1; } }

/* Input row */
.stTextInput > div > div > input {
  background: #0B1220; border: 1px solid var(--line); color: #E2E8F0; border-radius: 10px;
}
.stButton > button {
  background: var(--card); border: 1px solid var(--line); color: #E2E8F0; border-radius: 10px;
}
.stButton > button:hover { border-color: var(--cyan); }
.stButton[kind="primary"] > button {
  background: linear-gradient(135deg, #00F3FF, #00FF88); color: #020617; border: none; font-weight: 700;
}
.stButton[kind="primary"] > button:hover { filter: brightness(1.15); }

/* --- Overview pane --- */
.metric { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.metric-val { font-size: 20px; font-weight: 800; color: #E2E8F0; }
.plan-item { background: #0B1220; border: 1px solid var(--line); border-radius: 12px; padding: 12px; margin-bottom: 10px; }
.plan-item b.title { color: var(--cyan); font-size: 14px; }
.plan-item .when { color: var(--green); font-size: 12px; }
.reflection { background: #0B1220; border-left: 3px solid var(--amber); border-radius: 0 12px 12px 0; padding: 10px 14px; margin-bottom: 10px; font-size: 13px; line-height: 1.5; color: #E2E8F0; }

/* --- QR modal --- */
.qr-backdrop {
  position: fixed; inset: 0; z-index: 9999; background: rgba(2,6,12,0.75);
  display: flex; align-items: center; justify-content: center;
}
.qr-card {
  background: var(--card); border: 1px solid var(--line); border-radius: 20px;
  width: 420px; padding: 32px; text-align: center; box-shadow: 0 25px 60px rgba(0,0,0,0.6);
}
.qr-img { border: 1px solid var(--line); border-radius: 12px; background: #fff; padding: 6px; margin: 0 auto 16px auto; }
.qr-mock {
  width: 200px; height: 200px; background: #fff; border: 3px solid #000; border-radius: 6px;
  margin: 0 auto 16px auto; position: relative;
}
.qr-finder { position: absolute; background: #000; border: 6px solid #fff; }
.qr-finder.tl { top: 6px; left: 6px; width: 58px; height: 58px; }
.qr-finder.tr { top: 6px; right: 6px; width: 58px; height: 58px; }
.qr-finder.bl { bottom: 6px; left: 6px; width: 58px; height: 58px; }
.qr-mod { position: absolute; background: #000; }

.profile-pin {
  margin-top: 26px; padding-top: 16px; border-top: 1px solid var(--line);
  display:flex; align-items:center; gap:12px; font-size: 13px;
}
.profile-avatar { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg, #22D3EE, #00FF88); display:grid; place-items:center; font-weight: 800; color: #020617; font-size: 16px; }
.profile-name { font-weight: 700; color: #E2E8F0; }
.profile-sub { color: var(--muted); font-size: 11px; }

.stTabs [data-baseweb="tab-list"] { gap: 8px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def _seed():
    out = {}
    for c in DEMO_CONTACTS:
        out[c["key"]] = [
            {"who": w, "text": t, "ts": ts} for w, t, ts in seed_history(c)
        ]
    return out

DEFAULTS = {
    "splash": True,
    "linked": False,
    "api_key": "",
    "mode": "simulation",
    "qr_step": 0,        # 0 = none, 1 = scanning, 2 = linked
    "chats": _seed(),
    "active": DEMO_CONTACTS[0]["key"],
    "access": {c["key"]: c["access"] for c in DEMO_CONTACTS},
    "chat_lock": {c["key"]: c["chat"] for c in DEMO_CONTACTS},
    "pending": None,     # contact key waiting for AI reply
    "live_activity": [
        ("system", "Demo environment initialized", "—"),
        ("ai", "Ntokozo is online and monitoring your chats", "—"),
    ],
    "reflections": [
        "Pivot: first opener was too formal — switched to casual, outcome-first intros",
        "Lesson: asking about revenue early caused silence — now curiosity-led only",
        "Note: max 2 follow-ups enforced; silent leads get a graceful close",
    ],
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def now_ts() -> str:
    return datetime.now().strftime("%H:%M, %d/%m/%Y")


def contact_by_key(key: str) -> dict:
    for c in DEMO_CONTACTS:
        if c["key"] == key:
            return c
    return DEMO_CONTACTS[0]


def engine_history(key: str):
    """Convert app message rows to engine format [[who, text, ts], ...]."""
    return [[m["who"], m["text"], m["ts"]] for m in st.session_state.chats[key]]


# ---------------------------------------------------------------------------
# Splash / loading animation
# ---------------------------------------------------------------------------
def render_splash() -> None:
    frames = [
        """<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;'>
        <div class='logo-sym'>FA</div>
        <div class='brand-title'>FieldAI</div>
        <div style='margin-top:8px;color:#64748B;font-size:13px'>Initializing mission control…</div>
        <div style='margin-top:26px;display:flex;gap:6px;'>
          <div style='width:9px;height:9px;background:#22D3EE;border-radius:50%;animation:b 1.4s infinite'></div>
          <div style='width:9px;height:9px;background:#00FF88;border-radius:50%;animation:b 1.4s infinite 0.2s'></div>
          <div style='width:9px;height:9px;background:#FBBF24;border-radius:50%;animation:b 1.4s infinite 0.4s'></div>
        </div>
        <style>@keyframes b{0%,100%{opacity:.35;transform:scale(1)}50%{opacity:1;transform:scale(1.25)}}</style>
        </div>""",
        """<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;'>
        <div class='logo-sym'>FA</div>
        <div class='brand-title'>FieldAI</div>
        <div style='margin-top:8px;color:#94A3B8;font-size:13px'>Loading sales brain…</div>
        <div style='margin-top:26px;width:180px;height:4px;background:#1F2A3A;border-radius:2px;overflow:hidden;'>
          <div style='width:0%;height:100%;background:linear-gradient(90deg,#22D3EE,#00FF88);
            animation:load 1.6s infinite'></div>
        </div>
        <style>@keyframes load{0%{width:0%}40%{width:60%}100%{width:0%}}</style>
        </div>""",
        """<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;'>
        <div class='logo-sym'>FA</div>
        <div class='brand-title'>FieldAI</div>
        <div style='margin-top:8px;color:#22D3EE;font-size:13px'>Systems live. Demo ready.</div>
        </div>""",
    ]
    box = st.empty()
    for html in frames:
        box.markdown(html, unsafe_allow_html=True)
        time.sleep(0.9)
    box.empty()
    st.session_state.splash = False


if st.session_state.splash:
    render_splash()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="brand"><div class="logo-sym">FA</div><div>'
                '<div class="brand-title">FieldAI</div><div class="brand-sub">Live sales brain • demo</div></div></div>',
                unsafe_allow_html=True)
    st.divider()

    # --- API key input (top of sidebar) ---
    st.markdown("### 🔑 Connect live AI")
    key_in = st.text_input(
        "GROQ API Key (optional)",
        value=st.session_state.api_key,
        type="password",
        placeholder="gsk_…",
        help="Leave empty to run the fully offline simulation.",
    )
    if key_in != st.session_state.api_key:
        st.session_state.api_key = key_in.strip()
        st.session_state.mode = "live" if st.session_state.api_key else "simulation"
        st.rerun()
    badge_cls = "badge-live" if st.session_state.mode == "live" else "badge-sim"
    mode_txt = "LIVE — Groq LLM connected" if st.session_state.mode == "live" else "SIMULATION — offline demo"
    st.markdown(f'<span class="badge {badge_cls}">● {mode_txt}</span>', unsafe_allow_html=True)
    st.caption("No key is stored — it lives only in this session.")
    st.divider()

    # --- Link WhatsApp ---
    st.markdown("### 📱 WhatsApp")
    if st.button("➕ Link WhatsApp", use_container_width=True, type="primary"):
        st.session_state.qr_step = 1
        st.rerun()
    if st.session_state.linked:
        st.markdown('<span class="badge badge-green">● WhatsApp linked (backup account)</span>', unsafe_allow_html=True)
        st.caption("All messages route through the connected session.")
    else:
        st.markdown('<span class="badge badge-sim">● Not linked — demo mode</span>', unsafe_allow_html=True)
        st.caption("Tap ➕ Link WhatsApp to scan the QR code with your backup account.")
    st.divider()

    # --- Contact list ---
    st.markdown("### 💬 Chats")
    for c in DEMO_CONTACTS:
        k = c["key"]
        active = st.session_state.active == k
        dot_cls = "green" if st.session_state.access.get(k, c["access"]) == "green" else "red"
        unread = sum(1 for m in st.session_state.chats[k] if m["who"] == "lead" and not m.get("read"))
        pill_html = (
            f'<div class="pill {"active" if active else ""}" onclick="void(0)">'
            f'<div class="pill-dot {dot_cls}"></div>'
            f'<div><div class="pill-name">{c["name"]}</div>'
            f'<div class="pill-ts">{c["industry"]} • {c["phone"]}</div></div>'
        )
        if unread:
            pill_html += '<div style="background:var(--green);color:#020617;border-radius:50%;width:18px;height:18px;'
            pill_html += 'display:grid;place-items:center;font-size:10px;font-weight:800">' + str(unread) + '</div>'
        pill_html += "</div>"
        st.markdown(pill_html, unsafe_allow_html=True)
        if st.button(c["name"], key=f"pick_{k}", use_container_width=True):
            st.session_state.active = k
            st.rerun()
    st.divider()

    # --- Profile pinned at bottom ---
    st.markdown(
        '<div class="profile-pin">'
        '<div class="profile-avatar">NT</div>'
        '<div><div class="profile-name">Demo User</div>'
        '<div class="profile-sub">FieldAI • Demo workspace</div></div>'
        '</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def mode_badge() -> str:
    if st.session_state.mode == "live":
        return '<span class="badge badge-live">● LIVE — Groq</span>'
    return '<span class="badge badge-sim">● SIMULATION</span>'


def qr_image_src() -> str:
    """Real QR PNG if qrcode is installed, else a CSS mock pattern."""
    try:
        import qrcode  # type: ignore
        img = qrcode.make("fieldai://link?session=demo")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Anti-ban banner
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="warn">'
    '<b>⚠️ Anti-ban safety.</b> Always connect a <b>backup WhatsApp account</b> for testing — '
    'never your main account. FieldAI paces every message like a human (reading + typing delays) '
    'to reduce ban risk, but any automation carries risk. Use this demo only on a spare line.'
    '</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# QR linking modal
# ---------------------------------------------------------------------------
if st.session_state.qr_step == 1:
    qr_src = qr_image_src()
    qr_html = (
        f'<img src="{qr_src}" class="qr-img" alt="QR code" width="200"/>'
        if qr_src else
        """<div class="qr-mock">
           <div class="qr-finder tl"></div><div class="qr-finder tr"></div><div class="qr-finder bl"></div>
           <div class="qr-mod" style="top:30px;left:78px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:46px;left:94px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:62px;left:70px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:78px;left:86px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:94px;left:78px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:110px;left:94px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:126px;left:66px;width:10px;height:10px;"></div>
           <div class="qr-mod" style="top:142px;left:82px;width:10px;height:10px;"></div>
           </div>"""
    )
    st.markdown(
        f'<div class="qr-backdrop"><div class="qr-card">'
        f'<div style="font-size:11px;color:#94A3B8;margin-bottom:6px">SCAN TO LINK</div>'
        f'<div style="font-size:20px;font-weight:800;margin-bottom:10px">📱 Link WhatsApp</div>'
        f'{qr_html}'
        f'<div style="font-size:12px;color:#94A3B8;margin-bottom:6px">Scan with your <b>backup</b> WhatsApp account</div>'
        f'<div style="font-size:13px;color:#E2E8F0;margin-bottom:22px">Linking session expires in <b id="cd">30</b>s</div>'
        f'<div style="margin-top:14px;font-size:11px;color:#64748B">Expires soon? Click ➕ Link WhatsApp again.</div>'
        f'<script>var s=30,el=document.getElementById("cd");var iv=setInterval(function(){{s--;el.textContent=s;if(s<=0){{clearInterval(iv)}}}},1000);</script>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("✅ I have scanned the code", key="scanned_qr", use_container_width=True, type="primary"):
        st.session_state.qr_step = 2
        st.session_state.linked = True
        st.session_state.active = "linked-wa"
        st.session_state.chats["linked-wa"] = [
            {"who": w, "text": t, "ts": ts} for w, t, ts in seed_history(DEMO_CONTACTS[0])
        ]
        st.session_state.chats["linked-wa"].insert(0, {"who": "system", "text": "WhatsApp linked — backup account connected", "ts": now_ts()})
        st.rerun()

# ---------------------------------------------------------------------------
# Split view
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2], gap="medium")

# ================= LEFT PANE: WhatsApp chat =================
with left:
    c = contact_by_key(st.session_state.active)
    access = st.session_state.access.get(c["key"], c["access"])
    chat_locked = st.session_state.chat_lock.get(c["key"], c["chat"]) == "locked" if "chat_lock" in st.session_state else c["chat"] == "locked"

    st.markdown(
        f'<div class="card-header"><div><div style="font-size:16px;font-weight:800">{c["name"]}</div>'
        f'<div style="font-size:12px;color:#94A3B8">{c["industry"]} • {c["phone"]}</div></div>'
        f'<span class="badge {"badge-green" if access=="green" else "badge-red"}">'
        f'● {"ACCESS" if access=="green" else "NO ACCESS"}</span></div>', unsafe_allow_html=True)

    if access == "red":
        st.error("⛔ NO ACCESS — the AI cannot see, read or message this contact. Turn the contact green in the sidebar first.")
    else:
        chat = st.session_state.chats[st.session_state.active]
        box = st.container(height=520)
        with box:
            for m in chat:
                who = m["who"]
                align = "ai" if who == "ai" else "lead"
                label = "Ntokozo" if who == "ai" else c["name"]
                who_cls = "msg ai" if who == "ai" else "msg lead"
                bubble_cls = "bubble ai" if who == "ai" else "bubble lead"
                meta = m.get("ts", "")
                st.markdown(
                    f'<div class="msg {who_cls}"><div class="bubble {bubble_cls}">{m["text"]}'
                    f'<span class="msg-meta">{label} • {meta}</span></div></div>', unsafe_allow_html=True)
            if not chat:
                st.caption("No messages yet.")

        # Incoming simulation buttons when idle
        cols = st.columns(2)
        if cols[0].button("📥 Simulate lead message", use_container_width=True, disabled=st.session_state.pending is not None):
            demo_texts = [
                "Hi, how much does it cost?",
                "Who is this exactly?",
                "Not interested, thanks.",
                "Yes I'm interested — tell me more.",
                "I'm busy right now, can you call later?",
            ]
            text = random.choice(demo_texts)
            chat.append({"who": "lead", "text": text, "ts": now_ts(), "read": False})
            st.session_state.pending = st.session_state.active
            st.rerun()
        if cols[1].button("🕐 Follow-up nudge", use_container_width=True, disabled=st.session_state.pending is not None or sum(1 for m in chat if m["who"] == "ai") >= 3):
            fb = simulate_followup(c, engine_history(st.session_state.active))
            chat.append({"who": "ai", "text": fb, "ts": now_ts()})
            st.rerun()

        if st.session_state.chat_lock.get(st.session_state.active, c["chat"]) == "locked":
            st.warning("🔒 CHAT LOCKED — the AI reads but will not send replies.")

        txt = st.text_input("Type a message AS THE LEAD", placeholder="e.g. How much does it cost?", key="lead_in")
        if st.button("Send ↩️", use_container_width=True, type="primary", disabled=not txt.strip() or st.session_state.pending is not None):
            chat.append({"who": "lead", "text": txt.strip(), "ts": now_ts(), "read": True})
            st.session_state.pending = st.session_state.active
            st.rerun()

        # Human-paced AI reply (typing simulation)
        if st.session_state.pending == st.session_state.active:
            contact = contact_by_key(st.session_state.active)
            hist = engine_history(st.session_state.active)
            typing_ph = st.empty()
            typing_ph.markdown('<div class="msg ai"><div class="bubble ai"><span class="typing-dots">Ntokozo is typing…</span></div></div>', unsafe_allow_html=True)
            time.sleep(random.uniform(1.0, 2.2))
            typing_ph.empty()
            if st.session_state.mode == "live" and st.session_state.api_key:
                reply = live_reply(contact, hist)
                mode_tag = "live"
            else:
                reply = simulate_reply(contact, hist)
                mode_tag = "simulation"
            if not reply:
                reply = "Got it 👋 I'll keep that in mind."
            # Type out character stream
            reveal = st.empty()
            shown = ""
            cps = random.uniform(0.035, 0.075)
            for ch in reply:
                shown += ch
                reveal.markdown(
                    f'<div class="msg ai"><div class="bubble ai">{shown}<span class="typing-dots">▋</span></div></div>',
                    unsafe_allow_html=True,
                )
                time.sleep(cps)
            chat.append({"who": "ai", "text": reply, "ts": now_ts()})
            st.session_state.last_mode = mode_tag
            st.session_state.pending = None
            st.session_state.live_activity.insert(0, ("ai", f"Replied to {contact['name']} ({mode_tag})", now_ts()))
            st.session_state.live_activity = st.session_state.live_activity[:6]
            st.rerun()

# ================= RIGHT PANE: AI Overview =================
with right:
    st.markdown("### 🧠 AI Overview & Control Center")
    st.markdown(f'Status: {mode_badge()}', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#94A3B8;margin-bottom:14px">'
        'Live activity, planned actions and reflection logs update in real time.</div>', unsafe_allow_html=True)

    # Live activity
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;font-weight:700;color:#22D3EE;margin-bottom:8px">⚡ Live activity</div>', unsafe_allow_html=True)
    for who, text, ts in st.session_state.live_activity:
        icon = "🤖" if who == "ai" else "⚙️"
        st.markdown(f'<div class="msg-meta" style="margin:6px 0">{icon} {text} <span style="color:#64748B">{ts}</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Planned actions
    st.markdown('<div style="font-size:12px;font-weight:700;color:#22D3EE;margin:16px 0 8px 0">🎯 Planned actions</div>', unsafe_allow_html=True)
    for c in DEMO_CONTACTS:
        contact = contact_by_key(c["key"])
        plan = plan_for_contact(contact, engine_history(c["key"]))
        st.markdown(
            f'<div class="plan-item">'
            f'<b class="title">{c["name"]}</b> <span class="badge badge-{"green" if st.session_state.access.get(c["key"], c["access"])=="green" else "red"}">'
            f'{"ON" if st.session_state.access.get(c["key"], c["access"])=="green" else "OFF"}</span>'
            f'<div style="margin-top:6px;font-size:13px">{plan["plan"]}</div>'
            f'<div class="when">⏰ {plan["when"]} &nbsp;•&nbsp; {plan["reason"]}</div>'
            f'</div>', unsafe_allow_html=True)

    # Reflection log
    st.markdown('<div style="font-size:12px;font-weight:700;color:#22D3EE;margin:16px 0 8px 0">🪞 Reflection log (brain stem)</div>', unsafe_allow_html=True)
    for r in st.session_state.reflections:
        st.markdown(f'<div class="reflection">• {r}</div>', unsafe_allow_html=True)
