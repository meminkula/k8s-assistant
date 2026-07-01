import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.k8s.executor import KubernetesExecutor

if __name__ == "__main__":
    print("Testing...")

    worker = KubernetesExecutor()

    
    result = worker.list_pods(namespace="default")

    print(result)
