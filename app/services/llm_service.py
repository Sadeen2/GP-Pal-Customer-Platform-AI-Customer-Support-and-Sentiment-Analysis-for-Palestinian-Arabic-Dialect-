import os
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

client = None

if OpenAI is not None and OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)


def generate_faq_reply(
    user_message: str,
    faq_question: str,
    faq_answer: str,
    sentiment: str = "neutral"
) -> str:
    """
    Rewrite the matched FAQ answer using ChatGPT.
    If OpenAI is not configured, return the original FAQ answer.
    """

    if not faq_answer:
        return "مش واضح عندي جواب مناسب، ممكن توضحلي أكثر؟ 😊"

    if client is None:
        print("OpenAI client is None, returning FAQ answer only")
        return faq_answer

    system_prompt = """
You are a customer-support assistant for DAB STORE BZU.

The customers speak Palestinian Arabic.

Important rules:
- Answer ONLY using the FAQ answer provided.
- Do NOT invent prices, offers, dates, services, phone numbers, links, locations, or policies.
- If the FAQ answer asks for more information, ask the customer naturally.
- Keep the reply short, friendly, and natural.
- Use simple Palestinian Arabic.
- Do not mention FAQ, database, JSON, model, OpenAI, or internal system details.
- Do not add unnecessary explanations.
"""

    user_prompt = f"""
Customer message:
{user_message}

Detected sentiment:
{sentiment}

Matched FAQ question:
{faq_question}

FAQ answer:
{faq_answer}

Rewrite the final reply to the customer in natural Palestinian Arabic.
"""

    try:
        print("Calling OpenAI FAQ reply...")

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=160,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("OpenAI FAQ error:", e)
        return faq_answer


def generate_general_reply(user_message: str, sentiment: str = "neutral") -> str:
    """
    General reply for greetings or unclear messages.
    It must not invent business-specific information.
    """

    fallback_reply = "ممكن توضحلي أكثر؟ 😊 إذا قصدك السعر، التوصيل، أو تثبيت الطلب احكيلي وبساعدك."
    if client is None:
        print("OpenAI client is None, returning general fallback")
        return fallback_reply

    system_prompt = """
You are a friendly customer-support assistant for DAB STORE BZU.

The customers speak Palestinian Arabic.

Rules:
- Reply in simple Palestinian Arabic.
- Keep the reply short and friendly.
- Do NOT invent prices, working hours, services, phone numbers, links, locations, or policies.
- If the customer asks about business-specific information and you do not have enough context, ask them to send the product picture/name or clarify what they need.
- Do not mention OpenAI, FAQ, database, JSON, model, or internal system details.
"""

    user_prompt = f"""
Customer message:
{user_message}

Detected sentiment:
{sentiment}

Write a short helpful reply.
"""

    try:
        print("Calling OpenAI general reply...")

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=120,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("OpenAI general error:", e)
        return fallback_reply