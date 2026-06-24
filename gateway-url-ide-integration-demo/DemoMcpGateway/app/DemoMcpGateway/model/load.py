import os
from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials.

    Model ID can be overridden via BEDROCK_MODEL_ID environment variable.
    Defaults to Claude Sonnet 4 (cross-region inference).
    """
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "us.anthropic.claude-sonnet-4-20250514-v1:0"
    )
    return BedrockModel(model_id=model_id)
