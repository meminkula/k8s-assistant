import ollama
from app.k8s.executor import KubernetesExecutor

class LLMTranslator:
    def __init__(self):
        self.model_name= "qwen2.5:3b"

    def _get_system_prompt(self) -> str:

        return"""
        You are a strict Kubernetes command translator. Your only job is to convert the user's natural language request into a single, valid JSON object.
        
        CRITICAL RULES:
        1. DO NOT chat. DO NOT say "Here is your JSON". DO NOT write any explanations.
        2. Output ONLY the raw JSON object.
        3. If you don't understand or if the request is ambiguous, set "confidence" to a low value (e.g., 0.4).
        
        Allowed "intent" values: ["list_pods", "list_deployments", "get_logs"]
        
        Expected JSON Format:
        {
            "intent": "string (the allowed intent)",
            "namespace": "string (default is 'default')",
            "confidence": float (between 0.0 and 1.0)
        }
        
        Examples:
        User: "show me the pods in production namespace"
        Output: {"intent": "list_pods", "namespace": "production", "confidence": 0.95}
        
        User: "default odasındaki podları getir"
        Output: {"intent": "list_pods", "namespace": "default", "confidence": 0.90}
        """
    def translate_request(self, user_text: str) -> str:
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role":"system", "content": self._get_system_prompt()},
                    {"role":"user", "content": user_text},
                ],
                options={"temrature":0.0}
            )
            return response.message.content
        except Exception as e:
            return f"Error: {str(e)}"