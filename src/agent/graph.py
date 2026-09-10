"""LangGraph agent for card terms Q&A."""

import os

from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import build_tools

MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


def build_agent(collection=None, embed_client=None, model_id: str = MODEL_ID,
                bank: str | None = None):
    """Compile the LangGraph terms agent.

    collection and embed_client may be None; the search tool then reports
    that the index is unavailable instead of failing.
    """
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    model = ChatBedrockConverse(model=model_id, region_name=region)
    tools = build_tools(collection, embed_client, bank_scope=bank)
    prompt = SYSTEM_PROMPT
    if bank:
        prompt += f"\nThis session is restricted to bank '{bank}'."
    return create_agent(model, tools, system_prompt=prompt)
