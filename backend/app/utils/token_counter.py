# [FILE: backend/app/utils/token_counter.py - FULLCODE ONLY]
import tiktoken
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Token encoders cache
_encoders = {}

def get_encoder(model_name: str = "gpt-3.5-turbo"):
    """
    Get or create tiktoken encoder for specific model
    
    Args:
        model_name: Model name to get encoder for
    
    Returns:
        tiktoken.Encoding object
    """
    if model_name not in _encoders:
        try:
            # Try to get model-specific encoder
            _encoders[model_name] = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base (used by most modern models)
            logger.warning(f"Model {model_name} not found, using cl100k_base encoding")
            _encoders[model_name] = tiktoken.get_encoding("cl100k_base")
    
    return _encoders[model_name]

def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens in text using tiktoken
    
    Args:
        text: Text to count tokens for
        model_name: Model name for encoding
    
    Returns:
        Number of tokens
    """
    if not text:
        return 0
    
    try:
        encoder = get_encoder(model_name)
        return len(encoder.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        # Fallback: rough estimation
        return len(text.split())

def count_message_tokens(messages: list, model_name: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens in message format (for chat models)
    Based on OpenAI's token counting guide
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: Model name for encoding
    
    Returns:
        Total number of tokens
    """
    try:
        encoder = get_encoder(model_name)
        
        # Token overhead per message varies by model
        tokens_per_message = 3  # Default
        tokens_per_name = 1
        
        if model_name.startswith("gpt-3.5-turbo"):
            tokens_per_message = 4
            tokens_per_name = -1  # No name field in most cases
        elif model_name.startswith("gpt-4"):
            tokens_per_message = 3
            tokens_per_name = 1
        
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(encoder.encode(value))
                    if key == "name":
                        num_tokens += tokens_per_name
        
        num_tokens += 3  # Every reply is primed with assistant
        return num_tokens
        
    except Exception as e:
        logger.error(f"Error counting message tokens: {e}")
        # Fallback estimation
        total_text = " ".join([
            msg.get("content", "") 
            for msg in messages 
            if isinstance(msg.get("content"), str)
        ])
        return len(total_text.split())

def estimate_gemini_tokens(text: str) -> int:
    """
    Estimate Gemini tokens (Gemini uses SentencePiece similar to Claude)
    Approximation: ~0.75 tokens per word for English, ~1.5 for Thai
    
    Args:
        text: Text to estimate tokens for
    
    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    
    # Detect Thai characters
    thai_ratio = sum(1 for c in text if '\u0e00' <= c <= '\u0e7f') / max(len(text), 1)
    
    words = len(text.split())
    
    if thai_ratio > 0.3:  # Mostly Thai
        return int(words * 1.5)
    else:  # Mostly English
        return int(words * 0.75)

def get_token_usage(response: Any, provider: str, model_name: str = None) -> Dict[str, int]:
    """
    Extract token usage from LLM response
    
    Args:
        response: LLM response object
        provider: LLM provider (gemini/openai/local)
        model_name: Model name for fallback estimation
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens
    """
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }
    
    try:
        if provider == "gemini":
            # Gemini usage metadata
            if hasattr(response, "usage_metadata"):
                meta = response.usage_metadata
                usage["prompt_tokens"] = getattr(meta, "prompt_token_count", 0)
                usage["completion_tokens"] = getattr(meta, "candidates_token_count", 0)
                usage["total_tokens"] = getattr(meta, "total_token_count", 0)
            elif hasattr(response, "text"):
                # Fallback: estimate from response text
                usage["completion_tokens"] = estimate_gemini_tokens(response.text)
                usage["total_tokens"] = usage["completion_tokens"]
        
        elif provider in ["openai", "local"]:
            # OpenAI-compatible usage
            if hasattr(response, "usage"):
                u = response.usage
                usage["prompt_tokens"] = getattr(u, "prompt_tokens", 0)
                usage["completion_tokens"] = getattr(u, "completion_tokens", 0)
                usage["total_tokens"] = getattr(u, "total_tokens", 0)
            elif hasattr(response, "choices") and response.choices:
                # Fallback: estimate from response
                content = response.choices[0].message.content
                if model_name:
                    usage["completion_tokens"] = count_tokens(content, model_name)
                else:
                    usage["completion_tokens"] = count_tokens(content)
                usage["total_tokens"] = usage["completion_tokens"]
    
    except Exception as e:
        logger.error(f"Error extracting token usage: {e}")
    
    return usage

def format_token_usage(usage: Dict[str, int]) -> str:
    """
    Format token usage for logging
    
    Args:
        usage: Token usage dict
    
    Returns:
        Formatted string
    """
    return (
        f"Tokens - Prompt: {usage['prompt_tokens']:,} | "
        f"Completion: {usage['completion_tokens']:,} | "
        f"Total: {usage['total_tokens']:,}"
    )

# Cost calculation (approximate, update with latest pricing)
TOKEN_COSTS = {
    "gpt-3.5-turbo": {"prompt": 0.0005 / 1000, "completion": 0.0015 / 1000},
    "gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
    "gpt-4-turbo": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
    "gemini-2.0-flash": {"prompt": 0, "completion": 0},  # Free tier
    "gemini-2.5-flash": {"prompt": 0, "completion": 0},  # Free tier
    "local": {"prompt": 0, "completion": 0},  # Local model
}

def calculate_cost(usage: Dict[str, int], model_name: str) -> float:
    """
    Calculate approximate cost based on token usage
    
    Args:
        usage: Token usage dict
        model_name: Model name
    
    Returns:
        Cost in USD
    """
    # Find matching cost entry
    cost_entry = None
    for key in TOKEN_COSTS:
        if key in model_name.lower():
            cost_entry = TOKEN_COSTS[key]
            break
    
    if not cost_entry:
        return 0.0
    
    prompt_cost = usage["prompt_tokens"] * cost_entry["prompt"]
    completion_cost = usage["completion_tokens"] * cost_entry["completion"]
    
    return prompt_cost + completion_cost
