"""In-Region generation (CTL-022, CTL-023). Converse with no tools, no history and no fallback model.

The model identifier must be an In-Region foundation-model ID such as amazon.nova-micro-v1:0. Cross-region inference
profile IDs (us., eu., apac., global., …) and ARNs are refused before any call; IAM also denies them.
"""
from shared.reason_codes import MODEL_INVOCATION_FAILED, Denied

_PROFILE_PREFIXES = ("us.", "eu.", "apac.", "global.", "jp.", "au.", "ca.", "us-gov.")


def check_in_region_model_id(model_id):
    if not model_id or model_id.startswith("arn:") or model_id.startswith(_PROFILE_PREFIXES):
        raise Denied(MODEL_INVOCATION_FAILED, "generation model must be an In-Region foundation-model ID")


def generate(bedrock_runtime, model_id, system, messages):
    """Return (text, usage). Any failure is MODEL_INVOCATION_FAILED; there is no fallback."""
    check_in_region_model_id(model_id)
    try:
        response = bedrock_runtime.converse(modelId=model_id, system=system, messages=messages,
                                            inferenceConfig={"maxTokens": 400, "temperature": 0})
        text = "".join(part.get("text", "") for part in response["output"]["message"]["content"])
    except Exception as error:  # noqa: BLE001
        raise Denied(MODEL_INVOCATION_FAILED, type(error).__name__) from error
    return text, response.get("usage", {})
