"""
Bedrock Client - Wrapper for Amazon Bedrock InvokeModel
Supports multiple model formats (openai.gpt-oss-120b-1:0, Claude, etc.)
Includes Circuit Breaker pattern for throttling protection.
"""

import json
import logging
import os
import time
from enum import Enum
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


# ═══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker Pattern
# Protects against cascading failures from Bedrock throttling
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation, requests flow through
    OPEN = "open"          # Circuit tripped, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker for Bedrock API calls.

    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Service is failing, reject requests immediately
    - HALF_OPEN: Allow one request to test if service recovered

    Configuration via environment variables:
    - CIRCUIT_BREAKER_FAILURE_THRESHOLD: Failures before opening (default: 5)
    - CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Seconds before half-open (default: 60)
    """

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
    ):
        self.failure_threshold = failure_threshold or int(
            os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
        )
        self.recovery_timeout = recovery_timeout or int(
            os.environ.get("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")
        )

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.success_count = 0

    def can_execute(self) -> bool:
        """Check if request should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               (time.time() - self.last_failure_time) >= self.recovery_timeout:
                logger.info("Circuit breaker: transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN: allow one request to test
        return True

    def record_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker: test request succeeded, closing circuit")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0

        self.success_count += 1

    def record_failure(self, is_throttling: bool = False) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker: test request failed, reopening circuit")
            self.state = CircuitState.OPEN
            return

        # Only open circuit for throttling errors (transient)
        if is_throttling and self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker: opening after {self.failure_count} failures "
                f"(threshold: {self.failure_threshold})"
            )
            self.state = CircuitState.OPEN

    def get_status(self) -> Dict:
        """Get circuit breaker status for monitoring."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    pass


# Per-model circuit breakers (shared across Lambda invocations in warm container)
# This allows different models to fail independently - if mistral is throttled,
# gemma requests can still proceed
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(model_id: str = "default") -> CircuitBreaker:
    """
    Get or create circuit breaker for a specific model.

    Each model has its own circuit breaker, allowing independent failure handling.
    This prevents a single throttled model from blocking all requests.

    Args:
        model_id: Bedrock model ID (e.g., "mistral.mistral-large-3-675b-instruct")

    Returns:
        CircuitBreaker instance for the specified model
    """
    if model_id not in _circuit_breakers:
        _circuit_breakers[model_id] = CircuitBreaker()
        logger.info(f"Created circuit breaker for model: {model_id}")
    return _circuit_breakers[model_id]


def get_all_circuit_breakers_status() -> Dict[str, Dict]:
    """Get status of all circuit breakers for monitoring."""
    return {model_id: cb.get_status() for model_id, cb in _circuit_breakers.items()}


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

    # Default max_tokens per pass (Pass 3 needs more due to large JSON schema)
    DEFAULT_MAX_TOKENS = {
        "pass1": 4096,
        "pass2": 4096,
        "pass3": 32768,  # Pass 3 has ~500 lines of structured JSON output
    }

    def invoke(
        self,
        prompt: str,
        system: Optional[str] = None,
        pass_name: str = "pass1",
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
    ) -> Tuple[str, int, int, float]:
        """
        Invoke Bedrock model with retry logic and circuit breaker protection.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            pass_name: Which pass (for model selection)
            max_tokens: Max output tokens (uses pass-specific default if None)
            temperature: Model temperature (low for structured output)

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost_usd)

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open (service unavailable)
        """
        model_id = self.get_model_id(pass_name)

        # Check per-model circuit breaker
        circuit_breaker = get_circuit_breaker(model_id)
        if not circuit_breaker.can_execute():
            status = circuit_breaker.get_status()
            logger.error(f"Circuit breaker OPEN for model {model_id}, rejecting request. Status: {status}")
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open for {model_id}. Service will retry after recovery timeout. "
                f"Failures: {status['failure_count']}"
            )
        # Use pass-specific default if max_tokens not provided
        if max_tokens is None:
            max_tokens = self.DEFAULT_MAX_TOKENS.get(pass_name, 4096)
        body = self._build_request_body(model_id, prompt, system, max_tokens, temperature)

        # Retry loop with exponential backoff
        last_error = None
        is_throttling_error = False

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

                # Success - record with circuit breaker
                circuit_breaker.record_success()
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
                    is_throttling_error = is_throttling
                    delay = self.retry_delay * (2 ** attempt)
                    reason = "throttled" if is_throttling else "transient error"
                    logger.warning(f"Bedrock {reason}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                else:
                    # Non-retryable error - don't affect circuit breaker
                    raise

        # All retries exhausted - record failure with circuit breaker
        circuit_breaker.record_failure(is_throttling=is_throttling_error)
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
            "openai.gpt-oss",    # GPT-OSS models output <reasoning> tags
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
