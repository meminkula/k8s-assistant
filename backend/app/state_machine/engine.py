from pydantic import ValidationError
from app.llm.ollama_client import LLMTranslator
from app.llm.schemas import ParsedIntent, IntentType
from app.k8s.executor import KubernetesExecutor


class StateMachineEngine:
    def __init__(self):
        self.translator = LLMTranslator()
        self.executor = KubernetesExecutor()

    def process_user_request(self, user_text: str) -> dict:
        print(f"\n[StateMachine] Raw user input received: '{user_text}'")

        #LLM Translation
        print("[StateMachine] : Sending text to local LLM translator...")
        raw_llm_output = self.translator.translate_request(user_text)

        #Pydantic Validation
        print("[StateMachine] : Passing LLM output through Pydantic validation gateway...")
        try:
            validated_intent = ParsedIntent.model_validate_json(raw_llm_output)
            print(
                f" [StateMachine] Security Check Passed Intent: {validated_intent.intent}, Namespace: {validated_intent.namespace}")
        except ValidationError as e:
            print("X [StateMachine] Security Alert: LLM output failed validation")
            return {
                "status": "error",
                "message": "Security validation failed.",
                "details": e.errors()
            }

        #Confidence Check
        if validated_intent.confidence < 0.6:
            print("X [StateMachine] Confidence too low!")
            return {
                "status": "error",
                "message": "I am not sure what you mean. Could you please be more specific?"
            }

        # Execution
        print("[StateMachine] Step 3: Executing verified command via Kubernetes Executor...")
        if validated_intent.intent == IntentType.LIST_PODS:
            k8s_result = self.executor.list_pods(namespace=validated_intent.namespace)
            return {
                "status": "success",
                "parsed_data": validated_intent.model_dump(),
                "k8s_response": k8s_result
            }

        return {"status": "error", "message": "Unsupported action requested."}