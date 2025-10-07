"""
LLM Client for Cephiq Lite

Handles communication with Anthropic API and envelope parsing
"""
import os
from typing import List, Dict, Any
from .envelope import parse_llm_response, validate_envelope, normalize_envelope, create_error_envelope


class LLMClient:
    """Client for Anthropic Claude API"""

    def __init__(self, model: str = "claude-sonnet-4-20250514", temperature: float = 0.3):
        self.model = model
        self.temperature = temperature
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        # Import here to make it optional
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

    def decide(self, messages: List[Dict[str, str]], max_tokens: int = 8000) -> Dict[str, Any]:
        """
        Get decision from LLM

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            max_tokens: Max tokens in response

        Returns:
            Validated envelope dict
        """
        try:
            # Separate system message from conversation
            system_msg = None
            conversation = []

            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    conversation.append(msg)

            # Call Anthropic API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                system=system_msg,
                messages=conversation
            )

            # Extract text from response
            response_text = response.content[0].text

            # Parse into envelope
            success, result = parse_llm_response(response_text)

            if not success:
                # Failed to parse JSON
                return create_error_envelope(f"LLM response parse failed: {result}")

            # Normalize envelope
            envelope = normalize_envelope(result)

            # Validate envelope
            valid, errors = validate_envelope(envelope)

            if not valid:
                error_msg = "Envelope validation failed: " + "; ".join(errors)
                return create_error_envelope(error_msg, error_type="validation_error")

            return envelope

        except Exception as e:
            return create_error_envelope(f"LLM API error: {str(e)}", error_type="api_error")

    def decide_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 8000,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Get decision with retry on validation errors

        Feeds validation errors back to LLM for self-correction
        """
        last_errors = None

        for attempt in range(max_retries):
            # Add validation errors to context if retrying
            if last_errors and attempt > 0:
                error_msg = f"\nPrevious envelope had validation errors:\n" + "\n".join(last_errors)
                error_msg += "\n\nPlease emit a valid envelope that fixes these issues."

                # Append to last user message
                if messages and messages[-1]["role"] == "user":
                    messages[-1]["content"] += error_msg

            # Try to get decision
            envelope = self.decide(messages, max_tokens)

            # Check if it's an error envelope from validation
            if envelope.get("state") == "error":
                error_data = envelope.get("error", {})

                if error_data.get("error_type") == "validation_error":
                    # Extract validation errors for retry
                    last_errors = [error_data.get("error_message", "Unknown error")]

                    if attempt < max_retries - 1:
                        continue  # Retry

                # Non-validation error or final retry - return error
                return envelope
            else:
                # Valid envelope - return it
                return envelope

        # Max retries exhausted
        return create_error_envelope(
            f"Failed to get valid envelope after {max_retries} attempts",
            error_type="max_retries_exceeded"
        )


if __name__ == "__main__":
    # Self-test
    import sys

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("Set ANTHROPIC_API_KEY environment variable to test")
        sys.exit(1)

    client = LLMClient()

    messages = [
        {
            "role": "system",
            "content": "You are a helpful agent. Emit JSON envelopes only."
        },
        {
            "role": "user",
            "content": """Emit a simple reply envelope saying hello.

Format:
{
  "state": "reply",
  "brief_rationale": "Greeting user",
  "conversation": {"utterance": "Hello!"},
  "meta": {"continue": false, "stop_reason": "user_reply"}
}"""
        }
    ]

    envelope = client.decide(messages)

    print("Envelope received:")
    import json
    print(json.dumps(envelope, indent=2))

    valid, errors = validate_envelope(envelope)
    print(f"\nValidation: {'PASS' if valid else 'FAIL'}")
    if errors:
        for err in errors:
            print(f"  - {err}")
