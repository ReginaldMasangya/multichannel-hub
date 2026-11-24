"""Gemini: rewrite one master listing to fit each channel's style.
All LLM calls go through adapt_listing(), so switching to Groq later means editing only this file."""
import os

from pydantic import BaseModel

CHANNEL_STYLE = {
    "woocommerce": "Brand webstore. Warm, descriptive copy. Title up to 70 characters.",
    "marketplace": "Busy marketplace. Keyword-first title up to 60 characters, short bullet-style description.",
}


class Listing(BaseModel):
    title: str
    description: str


def adapt_listing(name: str, description: str, channel: str) -> Listing:
    key = os.getenv("GEMINI_API_KEY")
    if not key:  # No key yet: fall back so the demo never breaks
        return Listing(title=name, description=description)

    from google import genai
    client = genai.Client(api_key=key)
    prompt = (f"Rewrite this product listing for the channel described.\n"
              f"Channel: {CHANNEL_STYLE[channel]}\n"
              f"Product name: {name}\nDescription: {description}")
    resp = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": Listing},
    )
    return resp.parsed
