"""FieldAI Web Demo - engine layer.

Pure-stdlib simulation engine that mirrors the mindset of the real FieldAI
sales brain, plus an OPTIONAL live mode (Groq via the OpenAI SDK) that only
activates when the GROQ_API_KEY environment variable is set.

No API keys are ever hardcoded here - everything comes from os.getenv().
"""

import os
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Demo contacts (seeded so the UI always has something meaningful to show)
# ---------------------------------------------------------------------------
DEMO_CONTACTS = [
    {
        "key": "prestige-carwash",
        "name": "Prestige Carwash",
        "phone": "+27 82 555 0101",
        "industry": "car wash",
        "website": "none",
        "access": "green",   # AI may see this contact
        "chat": "on",        # AI may send messages
        "history": [
            ("lead", "Yes who is this?"),
            ("ai", "Hey 👋 Ntokozo here. Quick one - do you ever miss customer messages while the wash bay is busy?"),
            ("lead", "Ja sometimes, why?"),
        ],
    },
    {
        "key": "river-pharmacy",
        "name": "River Pharmacy",
        "phone": "+27 83 555 0147",
        "industry": "pharmacy",
        "website": "riverpharmacy.co.za",
        "access": "green",
        "chat": "on",
        "history": [
            ("ai", "Hello 👋 quick one - is this River Pharmacy?"),
        ],
    },
    {
        "key": "elite-plumbers",
        "name": "Elite Plumbers",
        "phone": "+27 71 555 0199",
        "industry": "plumbing",
        "website": "none",
        "access": "green",
        "chat": "locked",    # see-only: AI will NOT reply
        "history": [
            ("ai", "Hi there 👋 is this Elite Plumbers?"),
            ("lead", "Speaking, what do you need?"),
        ],
    },
    {
        "key": "red-cafe",
        "name": "Red Cafe",
        "phone": "+27 60 555 0132",
        "industry": "restaurant",
        "website": "redcafe.co.za",
        "access": "red",     # zero access: AI is blind to this contact
        "chat": "on",
        "history": [],
    },
    {
        "key": "maziya-salon",
        "name": "Maziya Hair Salon",
        "phone": "+27 84 555 0176",
        "industry": "salon",
        "website": "none",
        "access": "green",
        "chat": "on",
        "history": [
            ("ai", "Hey 👋 hope I've got the right contact - is this Maziya Hair Salon?"),
            ("lead", "Yes it is"),
            ("ai", "Nice, thanks for confirming! 👋"),
            ("lead", "No thank you, not interested."),
        ],
    },
    {
        "key": "kzn-restaurant-supplies",
        "name": "KZN Restaurant Supplies",
        "phone": "+27 79 555 0123",
        "industry": "wholesale",
        "website": "kznsupplies.co.za",
        "access": "green",
        "chat": "on",
        "history": [
            ("ai", "Hello 👋 quick question - is this KZN Restaurant Supplies?"),
            ("lead", "Hi yes, how can I help?"),
            ("ai", "Thanks! Out of curiosity - do you ever wish you had a way to never miss a customer message, even on your busiest days?"),
        ],
    },
]

SYSTEM_PROMPT = (
    "You are 'Ntokozo', a freelance AI-receptionist developer chatting on WhatsApp with a local business owner "
    "(the person you are talking to is THE LEAD, and you are texting them). Rules:\n"
    "(1) Text like a REAL HUMAN on WhatsApp: very short messages (usually one sentence), natural words, no essays, "
    "no 'Dear', no signatures, no AI-speak, no lists.\n"
    "(2) NEVER repeat or rephrase a message you already sent - every message moves the conversation FORWARD.\n"
    "(3) Judge time from message timestamps and continue naturally from exactly where the conversation stopped. "
    "If you already spoke, never open with a fresh hello.\n"
    "(4) FORBIDDEN: asking about their business operations as an outsider - no 'how's business?', revenue, staff probing. "
    "Create interest with OUTCOMES instead, softly and low-commitment.\n"
    "(5) One question maximum per message. Never make the lead commit to anything early.\n"
    "(6) If they decline: one gracious goodbye, then stop forever.\n"
    "(7) Max 2 follow-ups in total; never send two messages in a row without a reply.\n"
    "(8) Never lie, invent prices, clients or results."
)

_SIM_FLOWS = {
    "ask_price": [
        "Good question - it depends on the setup, but it works out around R3000 once-off. Want me to show you how it'd look for {biz}?",
        "Around R3000 and it's yours - no monthly nonsense. Should I show you how it fits {biz}?",
    ],
    "interest": [
        "Nice! Simplest way: it answers your customers and captures enquiries 24/7, nothing to install. Want a quick look?",
        "Great - so it basically never lets a customer message slip while you're busy. Should I show you how it looks?",
    ],
    "busy": [
        "That's exactly where it helps - while you're hands-on with customers, it keeps the enquiries coming in. Curious how it'd look for {biz}?",
    ],
    "decline": [
        "No problem at all - thanks for your time, and all the best with {biz}! 👋",
        "That's completely fair. Appreciate your time - take care! 👋",
    ],
    "who": [
        "I'm Ntokozo 👋 I build little AI assistants that answer customer messages for local businesses. Mind if I show you what it does?",
    ],
    "default": [
        "Got it 👋 Out of curiosity - do you ever wish you could never miss a customer message, even when you're fully booked?",
        "Fair enough! Quick thought: places like yours often lose enquiries after hours. Want to see a simple way to catch them?",
        "Understood. One thing though - {biz} could reply to customers 24/7 without you lifting a finger. Curious?",
    ],
}


def _classify(text: str) -> str:
    t = str(text or "").lower()
    if any(k in t for k in ["not interested", "no thanks", "no thank you", "don't contact", "stop"]):
        return "decline"
    if any(k in t for k in ["price", "cost", "how much", "rand", "r3000", "fee"]):
        return "ask_price"
    if any(k in t for k in ["who is this", "who are you", "what is this"]):
        return "who"
    if any(k in t for k in ["yes", "sure", "ok", "okay", "tell me", "go ahead", "why", "how does it"]):
        return "interest"
    if any(k in t for k in ["busy", "later", "no time"]):
        return "busy"
    return "default"


def simulate_reply(contact: dict, history: list) -> str:
    """Rule-based simulated salesperson reply (no API needed)."""
    prior_ai = [m[1].lower().strip() for m in history if m[0] == "ai"]
    last_lead = next((m[1] for m in reversed(history) if m[0] == "lead"), "")
    biz = str(contact.get("name") or "your business")
    kind = _classify(last_lead)
    pool = list(_SIM_FLOWS.get(kind, _SIM_FLOWS["default"]))
    random.shuffle(pool)
    for candidate in pool:
        text = candidate.format(biz=biz)
        if not any(text.lower()[:20] == p[:20] for p in prior_ai):
            return text
    return pool[0].format(biz=biz)


def simulate_followup(contact: dict, history: list) -> str:
    """A light, human follow-up after silence (max 2 in the full app)."""
    prior_ai = [m[1].lower().strip() for m in history if m[0] == "ai"]
    pool = [
        "Hello again 👋 just checking in - no rush at all.",
        "Hey 👋 hope the week's been good. Still happy to show you how it'd work for {biz} whenever you're ready.",
        "Hi again 👋 quick nudge - want me to show the 30-second demo?",
    ]
    random.shuffle(pool)
    for candidate in pool:
        text = candidate.format(biz=str(contact.get("name") or "your business"))
        if not any(text.lower()[:20] == p[:20] for p in prior_ai):
            return text
    return pool[0].format(biz=str(contact.get("name") or "your business"))


def live_reply(contact: dict, history: list, extra: str = "") -> str:
    """Optional LIVE mode: Groq via OpenAI SDK. Returns '' when unavailable."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return ""
    try:
        from openai import OpenAI
    except Exception:
        return ""
    try:
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
        system = SYSTEM_PROMPT
        profile = f"Business: {contact.get('name')} | industry: {contact.get('industry')} | website: {contact.get('website')}"
        system += "\n\nLEAD PROFILE:\n" + profile
        if extra:
            system += "\n\nSPECIAL INSTRUCTION FOR THIS TURN: " + extra
        sent = [m[1].lower().strip() for m in history if m[0] == "ai"]
        if sent:
            system += "\n\nMESSAGES YOU ALREADY SENT (never repeat these):\n" + "\n".join(f"- {m}" for m in sent[-8:])
        msgs = [{"role": "system", "content": system}]
        now = datetime.now().strftime("%A %H:%M")
        msgs.append({"role": "system", "content": f"Right now it is {now}. Message timestamps are shown in [HH:MM] prefixes."})
        for who, text, ts in history[-14:]:
            role = "assistant" if who == "ai" else "user"
            msgs.append({"role": role, "content": f"[{ts}] {text}"})
        resp = client.chat.completions.create(model="openai/gpt-oss-120b", messages=msgs, temperature=0.7, max_tokens=120)
        return (resp.choices[0].message.content or "").strip().strip('"')
    except Exception:
        return ""


def generate_reply(contact: dict, history: list) -> tuple:
    """Returns (text, mode) where mode is 'live' or 'simulation'."""
    text = live_reply(contact, history)
    if text:
        return text, "live"
    return simulate_reply(contact, history), "simulation"


def live_mode_available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


# ---------------------------------------------------------------------------
# Follow-up planning (mirrors the real app's visible plan reporting)
# ---------------------------------------------------------------------------
def plan_for_contact(contact: dict, history: list) -> dict:
    """('Reply now' | 'Soft check-in' | 'Awaiting reply') + when + reason."""
    if contact.get("access") == "red":
        return {"plan": "Hidden (red)", "when": "—", "reason": "No access - AI cannot see this contact"}
    if contact.get("chat") == "locked":
        return {"plan": "See-only (locked)", "when": "—", "reason": "AI sees the chat but will not reply"}
    if not history:
        return {"plan": "First hello", "when": "Queued now", "reason": "New lead - opening message pending"}
    last_who = history[-1][0]
    if last_who == "lead":
        return {"plan": "Reply now", "when": "Immediately", "reason": "They replied - priority #1, no timer waiting"}
    ai_count = sum(1 for m in history if m[0] == "ai")
    if ai_count >= 3:
        return {"plan": "Stop (max follow-ups)", "when": "—", "reason": "Max 2 follow-ups already used"}
    hours = 1 if ai_count == 1 else 10
    due = datetime.now() + timedelta(hours=hours)
    return {
        "plan": "Soft check-in",
        "when": due.strftime("today %H:%M" if due.date() == datetime.now().date() else "%a %H:%M"),
        "reason": f"Unread after double-tick - light nudge in ~{hours}h if they stay silent",
    }


def seed_history(contact: dict) -> list:
    """Converts the static seed conversation into timestamped messages."""
    base = datetime.now() - timedelta(hours=26)
    out = []
    for i, (who, text) in enumerate(contact.get("history", [])):
        ts = (base + timedelta(minutes=37 * i)).strftime("%H:%M, %d/%m/%Y")
        out.append([who, text, ts])
    return out
