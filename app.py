"""FieldAI Web Demo - Streamlit showcase of the sales-chat experience.

Text-only demo of the FieldAI WhatsApp sales flow:
  * AI response simulation (rules) with an OPTIONAL live LLM (set GROQ_API_KEY)
  * Resume-without-reset mindset, timestamps, follow-up plan reporting
  * Multi-chat view for up to 4 ticked contacts
  * Per-contact access control (green/red) and chat lock

No API keys are hardcoded - live mode reads os.getenv("GROQ_API_KEY").

Run:  streamlit run app.py
"""

import random
import time
from datetime import datetime

import streamlit as st

from demo_engine import (
    DEMO_CONTACTS,
    generate_reply,
    live_mode_available,
    plan_for_contact,
    seed_history,
    simulate_followup,
)

st.set_page_config(page_title="FieldAI Web Demo", page_icon="💬", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
.stApp { background: #060D17; }
h1, h2, h3 { color: #00F3FF !important; }
[data-testid="stSidebar"] { background: #081424; border-right: 1px solid #142842; }
.msg-ai { background: #0D2B1E; border-left: 3px solid #00FF66; padding: 8px 12px; border-radius: 6px; margin: 4px 0; }
.msg-lead { background: #10243B; border-left: 3px solid #00F3FF; padding: 8px 12px; border-radius: 6px; margin: 4px 0; }
.msg-meta { color: #6A8CAE; font-size: 0.72rem; }
.plan-card { background: #1A1406; border: 1px solid #7A5B00; border-radius: 6px; padding: 8px 12px; color: #FFB700; font-size: 0.85rem; }
.badge-green { color: #00FF66; font-weight: bold; }
.badge-red { color: #FF0055; font-weight: bold; }
.badge-amber { color: #FFB700; font-weight: bold; }
.chat-col { background: #081424; border: 1px solid #142842; border-radius: 8px; padding: 10px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def now_ts() -> str:
    return datetime.now().strftime("%H:%M, %d/%m/%Y")


def short_ts(ts: str) -> str:
    return ts.split(",")[0] if "," in ts else ts[-5:]


def init_state():
    if "threads" not in st.session_state:
        st.session_state.threads = {c["key"]: seed_history(c) for c in DEMO_CONTACTS}
    if "access" not in st.session_state:
        st.session_state.access = {c["key"]: c["access"] for c in DEMO_CONTACTS}
    if "chat_lock" not in st.session_state:
        st.session_state.chat_lock = {c["key"]: c["chat"] for c in DEMO_CONTACTS}
    if "ticks" not in st.session_state:
        st.session_state.ticks = {c["key"]: False for c in DEMO_CONTACTS}
    if "active" not in st.session_state:
        st.session_state.active = DEMO_CONTACTS[0]["key"]
    if "pending" not in st.session_state:
        st.session_state.pending = None
    if "last_mode" not in st.session_state:
        st.session_state.last_mode = ""


def contact_by_key(key: str) -> dict:
    for c in DEMO_CONTACTS:
        if c["key"] == key:
            return c
    return DEMO_CONTACTS[0]


def effective(contact: dict) -> dict:
    c = dict(contact)
    c["access"] = st.session_state.access[contact["key"]]
    c["chat"] = st.session_state.chat_lock[contact["key"]]
    return c


def resolve_pending():
    """Generates the queued AI reply (with a human-paced typing pause)."""
    key = st.session_state.pending
    if not key:
        return
    contact = effective(contact_by_key(key))
    with st.status(f"💬 Ntokozo is typing to {contact['name']}...", expanded=False) as s:
        time.sleep(random.uniform(1.0, 2.2))
        text, mode = generate_reply(contact, st.session_state.threads[key])
        s.update(label=f"✅ Replied to {contact['name']} ({mode} mode)", state="complete")
    st.session_state.threads[key].append(["ai", text, now_ts()])
    st.session_state.last_mode = mode
    st.session_state.pending = None
    st.rerun()


init_state()
resolve_pending()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 💬 FieldAI // WEB DEMO")
    if live_mode_available():
        st.markdown('<span class="badge-green">LIVE MODE</span> - GROQ_API_KEY detected', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-amber">SIMULATION MODE</span> - no API key needed', unsafe_allow_html=True)
        st.caption("Set GROQ_API_KEY in your environment to switch the sales brain to a live LLM.")
    st.divider()
    st.markdown("### Contact controls")
    st.caption("🟢 green = AI can see | 🔴 red = AI is blind. 🔓 chat on = AI may reply | 🔒 locked = see-only.")
    for c in DEMO_CONTACTS:
        k = c["key"]
        row = st.columns([3, 1, 1])
        row[0].markdown(f"**{c['name']}**  \n*{c['industry']}*")
        access_on = row[1].toggle("🟢", value=(st.session_state.access[k] == "green"), key=f"acc_{k}")
        st.session_state.access[k] = "green" if access_on else "red"
        if not access_on:
            st.session_state.chat_lock[k] = "locked"
        chat_on = row[2].toggle("🔓", value=(st.session_state.chat_lock[k] == "on"), key=f"cht_{k}",
                                disabled=not access_on)
        st.session_state.chat_lock[k] = "on" if (access_on and chat_on) else "locked"
    st.divider()
    if st.button("♻️ Reset demo", use_container_width=True):
        for k in ("threads", "access", "chat_lock", "ticks", "pending", "last_mode"):
            st.session_state.pop(k, None)
        st.rerun()

st.markdown("# FieldAI Web Demo")
st.caption("Text-only showcase • simulated WhatsApp sales chat • priority #1: the AI answers the moment a lead replies.")

tab_chat, tab_multi, tab_pipeline = st.tabs(["💬 Sales Chat", "📋 Multi-Chat (max 4)", "📊 Scraped Leads & Pipeline"])

# ---------------------------------------------------------------------------
# Tab 1 - single sales chat
# ---------------------------------------------------------------------------
with tab_chat:
    keys = [c["key"] for c in DEMO_CONTACTS]
    labels = {
        k: f"{contact_by_key(k)['name']} — {contact_by_key(k)['industry']} ({st.session_state.access[k]})"
        for k in keys
    }
    label_list = [labels[k] for k in keys]
    active_key = st.selectbox(
        "Active conversation",
        label_list,
        index=label_list.index(labels[st.session_state.active]),
        key="active_sel",
    )
    st.session_state.active = next(k for k, v in labels.items() if v == active_key)
    active_key = st.session_state.active
    contact = effective(contact_by_key(active_key))
    thread = st.session_state.threads[active_key]

    plan = plan_for_contact(contact, thread)
    st.markdown(
        f'<div class="plan-card">🎯 <b>Planned action:</b> {plan["plan"]} &nbsp;|&nbsp; 🕐 <b>When:</b> {plan["when"]}'
        f' &nbsp;|&nbsp; 💡 {plan["reason"]}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if contact["access"] == "red":
        st.error("⛔ NO ACCESS (red). The AI cannot see, read or message this contact at all.")
    else:
        box = st.container(height=380, border=False)
        with box:
            for who, text, ts in thread:
                cls = "msg-ai" if who == "ai" else "msg-lead"
                label = "Ntokozo (AI)" if who == "ai" else contact["name"]
                st.markdown(
                    f'<div class="{cls}"><span class="msg-meta">[{short_ts(ts)}]</span> '
                    f'<b>{label}:</b><br>{text}</div>',
                    unsafe_allow_html=True,
                )
            if not thread:
                st.caption("No messages yet.")

        locked = contact["chat"] == "locked"
        if locked:
            st.warning("🔒 CHAT LOCKED (see-only). The AI reads the conversation but will not send replies.")

        c1, c2 = st.columns([5, 1])
        lead_msg = c1.text_input("Type a message AS THE LEAD (simulate them replying)", key="lead_input",
                                 disabled=locked, placeholder="e.g. How much does it cost?")
        if c2.button("Send ↩️", use_container_width=True, disabled=locked) and lead_msg.strip():
            thread.append(["lead", lead_msg.strip(), now_ts()])
            st.session_state.pending = active_key
            st.rerun()

        b1, b2 = st.columns(2)
        if b1.button("🕐 Simulate silence → AI follow-up", use_container_width=True, disabled=locked):
            contact_now = effective(contact_by_key(active_key))
            prior_ai = sum(1 for m in thread if m[0] == "ai")
            if prior_ai >= 3:
                st.info("Max 2 follow-ups already used - the AI stops here.")
            else:
                thread.append(["ai", simulate_followup(contact, thread), now_ts()])
                st.rerun()
        if b2.button("🧠 Regenerate last reply", use_container_width=True, disabled=locked):
            for i in range(len(thread) - 1, -1, -1):
                if thread[i][0] == "ai":
                    text, _ = generate_reply(contact, thread[:i])
                    thread[i] = ["ai", text, thread[i][2]]
                    break
            st.rerun()

# ---------------------------------------------------------------------------
# Tab 2 - multi-chat view (up to 4 ticked contacts)
# ---------------------------------------------------------------------------
with tab_multi:
    st.markdown("Tick up to **4** contacts, then review their threads side by side with their planned actions.")
    tick_cols = st.columns(len(DEMO_CONTACTS))
    for col, c in zip(tick_cols, DEMO_CONTACTS):
        k = c["key"]
        checked = col.checkbox(c["name"], value=st.session_state.ticks[k], key=f"tick_{k}")
        st.session_state.ticks[k] = checked
    ticked = [k for k, v in st.session_state.ticks.items() if v]
    if len(ticked) > 4:
        for k in ticked[4:]:
            st.session_state.ticks[k] = False
        ticked = ticked[:4]
        st.warning("Maximum of 4 chats - extra ticks were removed.")

    if not ticked:
        st.info("No chats ticked yet. Tick a contact above (max 4) to open the multi-chat table.")
    else:
        cols = st.columns(len(ticked))
        for col, k in zip(cols, ticked):
            contact = effective(contact_by_key(k))
            thread = st.session_state.threads[k]
            plan = plan_for_contact(contact, thread)
            with col:
                st.markdown(f'<div class="chat-col">', unsafe_allow_html=True)
                st.markdown(f"**💬 {contact['name']}**  \n<span class='msg-meta'>{contact['phone']}</span>",
                            unsafe_allow_html=True)
                st.markdown(
                    f'<div class="plan-card">🎯 {plan["plan"]}<br>🕐 {plan["when"]}<br>💡 {plan["reason"]}</div>',
                    unsafe_allow_html=True,
                )
                if contact["access"] == "red":
                    st.error("⛔ No access - AI is blind to this chat.")
                else:
                    thread_box = st.container(height=320)
                    with thread_box:
                        if not thread:
                            st.caption("(no synced messages yet)")
                        for who, text, ts in thread:
                            cls = "msg-ai" if who == "ai" else "msg-lead"
                            who_label = "AI" if who == "ai" else "THEM"
                            st.markdown(
                                f'<div class="{cls}"><span class="msg-meta">[{short_ts(ts)}]</span> '
                                f'<b>{who_label}:</b> {text}</div>',
                                unsafe_allow_html=True,
                            )
                st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tab 3 - pipeline
# ---------------------------------------------------------------------------
with tab_pipeline:
    st.markdown("### Scraped leads & outreach pipeline (sample data)")
    rows = []
    for c in DEMO_CONTACTS:
        contact = effective(c)
        thread = st.session_state.threads[c["key"]]
        plan = plan_for_contact(contact, thread)
        if thread and thread[-1][0] == "lead":
            status = "Replied"
        elif len(thread) >= 2:
            status = "Contacted"
        elif thread:
            status = "Awaiting first reply"
        else:
            status = "New (scraped, never contacted)"
        rows.append(
            {
                "Business": c["name"],
                "Phone": c["phone"],
                "Industry": c["industry"],
                "Website": c["website"],
                "Access": "🟢" if contact["access"] == "green" else "🔴",
                "Chat": "🔓 on" if contact["chat"] == "on" else "🔒 locked",
                "Status": status,
                "Planned action": f'{plan["plan"]} ({plan["when"]})',
                "Messages": sum(1 for m in thread),
            }
        )
    header = "| Business | Phone | Industry | Website | Access | Chat | Status | Planned action | Messages |\n"
    sep = "|" + "|".join([" ---" for _ in range(9)]) + "|\n"
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"| {r['Business']} | {r['Phone']} | {r['Industry']} | {r['Website']} | {r['Access']} | {r['Chat']} | "
            f"{r['Status']} | {r['Planned action']} | {r['Messages']} |"
        )
    st.markdown("\n".join(lines), unsafe_allow_html=True)
    st.caption(
        "This mirrors the real app: questions about contacted chats are answered from conversation data; "
        "uncontacted scraped leads are answered from the leads table."
    )
