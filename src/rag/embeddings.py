"""Amazon Titan text embeddings via Bedrock."""

import json
import os

import boto3
from dotenv import load_dotenv

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
MAX_INPUT_CHARS = 6000


def get_embedding_client():
    """Create a Bedrock runtime client using .env credentials."""
    load_dotenv()
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def embed_text(client, text: str) -> list:
    """Embed one text with Titan v2. Returns a list of floats."""
    body = json.dumps({"inputText": text[:MAX_INPUT_CHARS]})
    resp = client.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=body,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]
