import json
from pydantic import ValidationError
from app.llm.ollama_client import LLMTranslator
from app.llm.schemas import ParsedIntent, IntentType
from app.k8s.executor import KubernetesExecutor


class SystemOrchestrator:
    def __init__(self):
        # Tüm işçilerimizi tek bir çatı altında topluyoruz
        self.translator = LLMTranslator()
        self.executor = KubernetesExecutor()

    def process_user_request(self, user_text: str) -> dict:
        print(f"\n[Orchestrator] Raw user input received: '{user_text}'")

        # 1. ADIM: Doğal dili LLM ile JSON string'e çevir
        print("[Orchestrator] Step 1: Sending text to local LLM translator...")
        raw_llm_output = self.translator.translate_request(user_text)

        # 2. ADIM: Gümrük Kapısı (Pydantic) ile doğrula
        print("[Orchestrator] Step 2: Passing LLM output through Pydantic validation gateway...")
        try:
            validated_intent = ParsedIntent.model_validate_json(raw_llm_output)
            print(
                f"✓ [Orchestrator] Security Check Passed! Intent: {validated_intent.intent}, Namespace: {validated_intent.namespace}")
        except ValidationError as e:
            print("X [Orchestrator] Security Alert: LLM output failed validation!")
            return {
                "status": "error",
                "message": "Security validation failed. Potential hallucination or unsafe input.",
                "details": e.errors()
            }

        # 3. ADIM: Güven dürüstlükten gelir ama kontrol siber güvenlikten!
        # Confidence (eminlik) kontrolü yapıyoruz (Doküman Madde 4.2)
        if validated_intent.confidence < 0.6:
            print("X [Orchestrator] Confidence too low! Asking for clarification...")
            return {
                "status": "error",
                "message": "I am not sure what you mean. Could you please be more specific?"
            }

        # 4. ADIM: Karar ve Çalıştırma (Deterministik Çekirdek)
        print("[Orchestrator] Step 3: Executing verified command via Kubernetes Executor...")

        if validated_intent.intent == IntentType.LIST_PODS:
            # Yapay zekadan temizlenen güvenli parametreyi bizim fonksiyona geçiyoruz
            k8s_result = self.executor.list_pods(namespace=validated_intent.namespace)
            return {
                "status": "success",
                "parsed_data": validated_intent.model_dump(),
                "k8s_response": k8s_result
            }

        # İleride eklenecek diğer intent'ler için köprü hazır
        elif validated_intent.intent == IntentType.LIST_DEPLOYMENTS:
            return {
                "status": "success",
                "message": "List deployments feature is coming soon in Phase 2!"
            }

        else:
            return {
                "status": "error",
                "message": "Unsupported action requested."
            }