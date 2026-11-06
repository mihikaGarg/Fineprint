"""The only entry point for LLM calls.

Responsibilities (to implement): response cache keyed by prompt hash,
structured logging, retry caps, temperature 0 for extraction/classification.
Never import this from /enforce: the enforce path makes no LLM calls.
"""
