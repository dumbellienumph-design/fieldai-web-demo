"""
Sales AI brain - generates human-like WhatsApp replies.

Uses the live Groq LLM when GROQ_API_KEY is provided (via os.getenv at
runtime - nothing hardcoded), otherwise falls back to a rule-based
simulation that follows the same sales philosophy.
"""

import os
import random
from datetime import datetime

from wa_engine import WhatsAppEngine


SYSTEM_PROMPT = (
    "You are 'Ntokozo', a freelance AI-receptionist developer texting a local "
    "business owner on WhatsApp. Rules:\n"
    "(1) Text like a real human: very short (usually one sentence), natural "
    "words, no essays, no 'Dear', no signatures, no AI-speak, no lists.\n"
    "(2) NEVER repeat or rephrase a message already sent - every message moves "
    "the conversation FORWARD.\n"
    "(3) Judge time from message timestamps; continue naturally from where the "
    "conversation stopped - never open with a fresh hello after you already spoke.\n"
    "(4) FORBIDDEN: asking about business operations as an outsider - no "
    "'how's business?', revenue, staff probing. Create interest with outcomes "
    "instead, softly and low-commitment.\n"
    "(5) One question maximum per message. Never make the lead commit early.\n"
    "(6) If they decline: one gracious goodbye, then stop forever.\n"
    "(7) Max 2 follow-ups; never send two messages in a row without a reply.\n"
    "(8) Never lie or invent prices, clients or results."
)

_SIM_FLOWS = {
    "decline": [
        "No problem at all - thanks for your time, all the best! 👋",
        "That's completely fair. Appreciate your time - take care! 👋",
    ],
    "ask_price": [
        "Good question - around R3000 once-off. Want me to show how it'd work for {biz}?",
        "Around R3000 once-off, nothing monthly. Should I show you how it fits {biz}?",
    ],
    "interest": [
        "Nice! It answers your customers and captures enquiries 24/7, nothing to install. Want a quick look?",
        "Great - so it never lets a customer message slip while you're busy. Want to see how it looks?",
    ],
    "busy": [
        "That's exactly where it helps - while you're hands-on, it keeps enquiries coming in. Curious?",
    ],
    "who": [
        "I'm Ntokozo 👋 I build little AI assistants that answer customer messages for local businesses. Mind if I show you?",
    ],
    "default": [
        "Got it 👋 Do you ever wish you could never miss a customer message, even when you're fully booked?",
        "Fair enough! Places like yours often lose enquiries after hours. Want to see a simple way to catch them?",
        "Understood. {biz} could reply to customers 24/7 without you lifting a finger. Curious?",
    ],
}


def _classify(text: str) -> str:
    t = str(text or "").lower()
    if any(k in t for k in ["not interested", "no thanks", "stop", "don't contact"]):
        return "decline"
    if any(k in t for k in ["price", "cost", "how much", "rand", "r3000", "fee"]):
        return "ask_price"
    if any(k in t for k in ["who is this", "who are you", "what is this"]):
        return "who"
    if any(k in t for k in ["yes", "sure", "ok", "okay", "tell me", "go ahead", "why"]):
        return "interest"
    if any(k in t for k in ["busy", "later", "no time"]):
        return "busy"
    return "default"


def simulate_reply(contact_name: str, history: list) -> str:
    prior_ai = [m[1].lower().strip() for m in history if m[0] == "ai"]
    last_lead = next((m[1] for m in reversed(history) if m[0] == "lead"), "")
    kind = _classify(last_lead)
    pool = list(_SIM_FLOWS.get(kind, _SIM_FLOWS["default"]))
    random.shuffle(pool)
    for candidate in pool:
        text = candidate.format(biz=contact_name)
        if not any(text.lower()[:20] == p[:20] for p in prior_ai):
            return text
    return pool[0].format(biz=contact_name)


def generate_reply(engine: WhatsAppEngine, contact_name: str, history: list) -> str:
    """Returns a reply string - live LLM if API key present, else simulation."""
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
            sent = [m[1] for m in history if m[0] == "ai"]
            system = SYSTEM_PROMPT + "\n\nMESSAGES YOU ALREADY SENT (never repeat these):\n" + "\n".join(
                f"- {m}" for m in sent[-8:]
            )
            now = datetime.now().strftime("%A %H:%M")
            msgs = [
                {"role": "system", "content": system},
                {"role": "system", "content": f"Right now it is {now}."},
            ]
            for m in history[-14:]:
                role = "assistant" if m[0] == "ai" else "user"
                msgs.append({"role": role, "content": m[1]})
            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b", messages=msgs, temperature=0.7, max_tokens=120
            )
            text = (resp.choices[0].message.content or "").strip().strip('"')
            if text:
                return text
        except Exception:
            pass
    return simulate_reply(contact_name, history)
