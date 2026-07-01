from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesExecutor:
    def __init__(self):
        try:
            config.load_kube_config()
            self.core_v1 = client.CoreV1Api()
            print("Kubernetes kümesine başarıyla bağlanıldı!")
        except Exception as e:
            print(f"Kubernetes bağlantısı başarısız oldu: {e}")
            raise e

    def list_pods(self, namespace: str = "default") -> dict:
        try:
            ham_pod_listesi = self.core_v1.list_namespaced_pod(namespace=namespace)
            temiz_podlar = []

            for pod in ham_pod_listesi.items:
                pod_bilgisi = {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "ip": pod.status.pod_ip
                }
                temiz_podlar.append(pod_bilgisi)

            return {
                "status": "success",
                "namespace": namespace,
                "data": temiz_podlar
            }

        except ApiException as e:
            return {
                "status": "error",
                "message": f"Kubernetes API Hatası: {e.reason}",
                "code": e.status
            }