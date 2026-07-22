import logging
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


MODEL = "claude-haiku-4-5"


async def generate_review_response(
    review_text: str,
    rating: int,
    reviewer_name: str,
    voice_sample: str
) -> str:
    """Generate a voice-matched review reply using Claude Haiku 4.5."""
    system_prompt = f"""You are writing a review reply for an Australian local business.

VOICE: Match the owner's voice. {voice_sample if voice_sample else "Be warm and genuine."}
No corporate language. No marketing speak.

FORBIDDEN PHRASES:
- "We apologize for any inconvenience"
- "Thank you for your feedback"
- "We strive to"
- "Our team"

RATING RULES:
- 1-2 star: Acknowledge specifically, offer resolution path, max 80 words
- 3 star: Thank, address gap, mention ONE improvement, max 60 words
- 4-5 star: Warm, specific, invite return, max 50 words

ALWAYS:
- Use the reviewer's first name
- Never make up facts about the business
- Output ONLY the response text, no preamble

Your business operates in Australia. Use Australian English spelling and tone."""

    try:
        client = _get_client()
        message = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Reviewer: {reviewer_name}\nRating: {rating} stars\nReview: {review_text}\n\nWrite the reply:"
            }]
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"generate_review_response failed: {e}")
        raise


async def generate_seo_report(
    business_name: str,
    this_week: list[dict],
    last_week: list[dict]
) -> str:
    """Generate plain-English SEO ranking delta report. Called by Phase 4."""
    deltas_json = []
    for tw in this_week:
        lw = next((l for l in last_week if l["keyword"] == tw["keyword"]), None)
        prev_pos = lw["position"] if lw else None
        curr_pos = tw["position"]
        delta = None
        if prev_pos is not None and curr_pos is not None:
            delta = prev_pos - curr_pos  # positive = improved
        deltas_json.append({
            "keyword": tw["keyword"],
            "last_week": prev_pos,
            "this_week": curr_pos,
            "delta": delta
        })

    system_prompt = """You are writing a weekly SEO report for an Australian local business owner.
Rules:
- Open with the most significant movement
- Plain language — no jargon
- Suggest ONE action this week
- End with a trajectory verdict (improving/stable/declining)
- Forbidden words: SERP, organic, algorithm, domain authority
- Max 150 words"""

    try:
        client = _get_client()
        message = client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Business: {business_name}\nDeltas: {deltas_json}\n\nWrite the weekly report:"
            }]
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"generate_seo_report failed: {e}")
        raise


async def generate_competitor_brief(
    business_name: str,
    changes_summary: str
) -> str:
    """Generate competitive intelligence brief. Called by Phase 5."""
    system_prompt = """You are a competitive intelligence analyst for an Australian local business.
Write a brief based on competitor website changes detected.

Cover:
1. What changed (specific)
2. Likely signal (what the competitor is doing)
3. ONE 7-day response action for the business
4. Threat level: LOW | MEDIUM | HIGH with reasoning

Be direct. No hedging. Max 200 words."""

    try:
        client = _get_client()
        message = client.messages.create(
            model=MODEL,
            max_tokens=350,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"Business: {business_name}\nChanges detected:\n{changes_summary}\n\nWrite the brief:"
            }]
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"generate_competitor_brief failed: {e}")
        raise


async def generate_followup_message(
    patient_name: str,
    last_treatment: str,
    business_name: str,
    channel: str,
    practitioner_name: str | None = None,
    claim_type: str | None = None,
) -> str:
    """Generate re-booking follow-up message.

    ``practitioner_name`` lets the copy reference the patient's usual clinician
    (e.g. "…with Dr Chen") when known. ``claim_type`` (best-effort, PMS-sourced)
    tunes the tone without asserting specifics — per D3-A detailed claim/health-fund
    info is kept OUT of the SMS body.
    """
    system_prompt = """You are writing a re-booking message for an Australian healthcare/clinic patient.

SMS rules:
- Max 160 characters
- Start with business name
- No links unless absolutely necessary

Email rules:
- Max 100 words
- Warm, personal

PRACTITIONER:
- When a practitioner name is provided, you may reference them naturally
  (e.g. "book your next visit with Dr Chen"). Do not invent a name when none is given.

CLAIM / BILLING GUARDRAILS:
- Never quote exact dollar amounts, gaps, out-of-pocket costs or rebates unless
  they are explicitly provided AND verified.
- Never make medical or financial claims (e.g. "fully covered", "no out-of-pocket",
  "bulk-billed at no cost"). Keep any claim/billing context generic at most.
- Do not mention a health fund or Medicare by name unless explicitly provided.

FORBIDDEN PHRASES:
- "friendly reminder"
- "reach out"
- "don't hesitate"

Never make up medical claims"""

    try:
        client = _get_client()
        parts = [
            f"Patient: {patient_name}",
            f"Last treatment: {last_treatment}",
            f"Business: {business_name}",
            f"Channel: {channel}",
        ]
        if practitioner_name:
            parts.append(f"Practitioner: {practitioner_name}")
        if claim_type:
            parts.append(f"Claim type: {claim_type}")
        parts.append("\nWrite the message:")
        user_content = "\n".join(parts)
        message = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": user_content,
            }]
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"generate_followup_message failed: {e}")
        raise
