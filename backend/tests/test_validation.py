import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.llm.schemas import ParsedIntent
from pydantic import ValidationError

if __name__ == "__main__":
    print("--- Starting Pydantic Validation Layer Test ---")


    valid_llm_output = '{"intent": "list_pods", "namespace": "production", "confidence": 0.85}'
    print(f"\n[Case 1] Simulating Valid LLM Output JSON: {valid_llm_output}")

    try:

        validated_object = ParsedIntent.model_validate_json(valid_llm_output)
        print("Success: Data successfully passed the custom validation gateway")
        print(f"Validated Object Data -> Intent: {validated_object.intent}, Namespace: {validated_object.namespace}")
    except ValidationError as e:
        print(f"X Failed: Valid data was rejected unexpectedly: {e}")

    print("\n" + "=" * 50)


    malicious_llm_output = '{"intent": "delete_all_cluster", "namespace": "default", "confidence": 99.9}'
    print(f"\n[Case 2] Simulating Malicious/Invalid LLM Output JSON: {malicious_llm_output}")

    try:
        ParsedIntent.model_validate_json(malicious_llm_output)
        print("X Vulnerability: Dangerous data leaked through the gateway without validation")
    except ValidationError as e:

        print("Security Protection: Dangerous data was successfully blocked by the gateway")
        print(f"[Blocked Error Details]:\n{e}")

    print("\n--- Validation Test Execution Completed ---")