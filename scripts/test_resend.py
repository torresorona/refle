import asyncio

import httpx
from refle_core.config import get_settings


async def test_resend():
    settings = get_settings()
    api_key = settings.resend_api_key
    if not api_key:
        print("RESEND_API_KEY is not set in environment.")
        return

    print("Sending test email using key:", api_key[:8] + "...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": "notifications@updates.refle.ai",
                "to": "test@example.com",
                "subject": "Testing Resend",
                "html": "<p>This is a test.</p>",
            },
        )
        print("Status Code:", response.status_code)
        try:
            print("Response:", response.json())
        except Exception:
            print("Response Text:", response.text)


if __name__ == "__main__":
    asyncio.run(test_resend())
