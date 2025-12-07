"""
Bedrock Client - Wrapper for Amazon Bedrock InvokeModel
Supports multiple model formats (openai.gpt-oss-120b-1:0, Claude, etc.)
"""

import json
import logging
import time
from typing import Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Pricing per 1K tokens
MODEL_PRICING = {
    "openai.gpt-oss-120b-1:0": {"input": 0.00015, "output": 0.0003},
    "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.00025, "output": 0.00125},
    "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 0.003, "output": 0.015},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 0.001, "output": 0.002}


class BedrockClient:
    """
    Wrapper for Bedrock InvokeModel with retry logic and cost tracking.
    Supports configurable models per pass.
    """

    def __init__(
        self,
        model_ids: Optional[Dict[str, str]] = None,
        region: str = "us-east-1",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Initialize Bedrock client.

        Args:
            model_ids: Dict mapping pass names to model IDs
                       e.g., {"pass1": "openai.gpt-oss-120b-1:0", "pass2": "openai.gpt-oss-120b-1:0"}
            region: AWS region
            max_retries: Max retry attempts for throttling
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.model_ids = model_ids or {
            "pass1": "openai.gpt-oss-120b-1:0",
            "pass2": "openai.gpt-oss-120b-1:0",
            "pass3": "openai.gpt-oss-120b-1:0",
        }
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def get_model_id(self, pass_name: str) -> str:
        """Get model ID for a specific pass."""
        return self.model_ids.get(pass_name, "openai.gpt-oss-120b-1:0")

    def invoke(
        self,
        prompt: str,
        system: Optional[str] = None,
        pass_name: str = "pass1",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> Tuple[str, int, int, float]:
        """
        Invoke Bedrock model with retry logic.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            pass_name: Which pass (for model selection)
            max_tokens: Max output tokens
            temperature: Model temperature (low for structured output)

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost_usd)
        """
        model_id = self.get_model_id(pass_name)
        body = self._build_request_body(model_id, prompt, system, max_tokens, temperature)

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json",
                )

                response_body = json.loads(response["body"].read())
                text, input_tokens, output_tokens = self._parse_response(model_id, response_body)
                cost = self._calculate_cost(model_id, input_tokens, output_tokens)

                return text, input_tokens, output_tokens, cost

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                error_message = str(e)

                # Retry on throttling, service unavailable, or transient validation errors
                is_throttling = error_code in ["ThrottlingException", "ServiceUnavailableException"]
                is_transient_error = (
                    error_code == "ValidationException" and
                    "EngineCore encountered an issue" in error_message
                )

                if is_throttling or is_transient_error:
                    last_error = e
                    delay = self.retry_delay * (2 ** attempt)
                    reason = "throttled" if is_throttling else "transient error"
                    logger.warning(f"Bedrock {reason}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                else:
                    raise

        # All retries exhausted
        raise last_error or Exception("Bedrock invocation failed after retries")

    def _is_openai_compatible(self, model_id: str) -> bool:
        """Check if model uses OpenAI-compatible API format."""
        # Models that use OpenAI-compatible format in Bedrock
        openai_prefixes = (
            "openai.",      # OpenAI models (gpt-oss-120b-1, etc.)
            "moonshot.",    # Kimi K2
            "deepseek.",    # DeepSeek R1
            "minimax.",     # MiniMax M2
            "qwen.",        # Qwen models
            "mistral.",     # Mistral models
            "google.",      # Gemma models
            "meta.llama4",  # Llama 4 models
        )
        return any(model_id.startswith(prefix) for prefix in openai_prefixes)

    def _is_thinking_model(self, model_id: str) -> bool:
        """Check if model is a 'thinking' model that outputs reasoning by default."""
        # Models that output <reasoning> or similar before the actual response
        thinking_patterns = (
            "kimi-k2-thinking",  # Kimi K2 Thinking
            "deepseek.r1",       # DeepSeek R1
        )
        return any(pattern in model_id for pattern in thinking_patterns)

    def _build_request_body(
        self,
        model_id: str,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> Dict:
        """Build request body based on model type."""

        if self._is_openai_compatible(model_id):
            # OpenAI-compatible format (works for most third-party models in Bedrock)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            body = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

            # Disable reasoning for "thinking" models to get direct JSON output
            if self._is_thinking_model(model_id):
                body["include_reasoning"] = False

            return body

        elif model_id.startswith("anthropic.claude"):
            # Claude format
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                body["system"] = system
            return body

        else:
            # Generic format (fallback)
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            return {
                "prompt": full_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

    def _parse_response(self, model_id: str, response_body: Dict) -> Tuple[str, int, int]:
        """Parse response based on model type. Returns (text, input_tokens, output_tokens)."""

        if self._is_openai_compatible(model_id):
            # OpenAI-compatible format (works for most third-party models in Bedrock)
            text = response_body.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = response_body.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

        elif model_id.startswith("anthropic.claude"):
            # Claude format
            content = response_body.get("content", [])
            text = content[0].get("text", "") if content else ""
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

        else:
            # Generic format
            text = response_body.get("completion", str(response_body))
            # Estimate tokens if not provided
            input_tokens = response_body.get("input_tokens", len(text.split()) * 2)
            output_tokens = response_body.get("output_tokens", len(text.split()))

        return text, input_tokens, output_tokens

    def _calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model pricing."""
        pricing = MODEL_PRICING.get(model_id, DEFAULT_PRICING)
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost
