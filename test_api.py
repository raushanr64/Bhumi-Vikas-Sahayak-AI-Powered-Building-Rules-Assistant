import os
import traceback
from pathlib import Path

import anthropic
import httpx2 as httpx

def main():
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        print("ERROR: .env file not found")
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("ANTHROPIC_API_KEY="):
            os.environ["ANTHROPIC_API_KEY"] = (
                line.split("=", 1)[1].strip().strip("\"'")
            )
            break

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: API key not found")
        return

    http_client = httpx.Client(
        headers={"Accept-Encoding": "identity"},
        timeout=30.0,
    )

    try:
        client = anthropic.Anthropic(
            http_client=http_client,
            max_retries=0,
        )

        response = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=10,
            messages=[
                {"role": "user", "content": "Reply only OK"}
            ],
        )

        print("SDK SUCCESS!")
        print("Response:", response.content[0].text)

    except Exception:
        traceback.print_exc()

    finally:
        http_client.close()


if __name__ == "__main__":
    main()