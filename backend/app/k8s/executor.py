from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesExecutor:
    def __init__(self):
        try:
            config.load_kube_config()
            self.core_v1 = client.CoreV1Api()
            print("Connected to kubernetes cluster.")
        except Exception as e:
            print(f"Failed to connect kubernetes: {e}")
            raise e

    def list_pods(self, namespace: str = "default") -> dict:
        try:
            main_pod_list = self.core_v1.list_namespaced_pod(namespace=namespace)
            clean_pods = []

            for pod in main_pod_list.items:
                pod_info = {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "ip": pod.status.pod_ip
                }
                clean_pods.append(pod_info)

            return {
                "status": "success",
                "namespace": namespace,
                "data": clean_pods
            }

        except ApiException as e:
            return {
                "status": "error",
                "message": f"Kubernetes API Error: {e.reason}",
                "code": e.status
            }
