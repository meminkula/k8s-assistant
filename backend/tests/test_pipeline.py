import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from app.state_machine.engine import StateMachineEngine

if __name__ == "__main__":
    print("==================================================")
    print("--- STARTING FULL PIPELINE INTEGRATION TEST ---")
    print("==================================================")


    engine = StateMachineEngine()

    user_command = "kral bana default odasındaki podları bi listelesene"
    final_response = engine.process_user_request(user_command)

    print("\n==================================================")
    print("[FINAL RESULT] System Response to Frontend:")
    print("==================================================")
    import pprint

    pprint.pprint(final_response)
    print("\n--- Pipeline Test Finished Successfully ---")