import sys
import os

# Add the backend directory to Python path for seamless imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.llm.ollama_client import LLMTranslator

if __name__ == "__main__":
    print("--- Starting LLM Translator Integration Test ---")

    # Initialize the local Qwen translator instance
    translator = LLMTranslator()

    # Test case: A realistic, informal Turkish prompt from a DevOps engineer
    user_prompt = "kral bana production odasındaki podları bi listelesene sana zahmet"
    print(f"\n[Input] User Prompt: '{user_prompt}'")

    print("\n[Processing] Translating natural language via local Qwen model...")
    raw_json_output = translator.translate_request(user_prompt)

    print("\n[Output] Structured JSON Result from LLM:")
    print(raw_json_output)
    print("\n--- Test Execution Completed Successfully ---")