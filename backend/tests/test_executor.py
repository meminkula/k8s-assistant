import sys
import os

# Python'a test_executor.py dosyasının iki üst klasörünü (yani backend klasörünü)
# doğrudan ana arama yolu (root dizini) olarak elinle dikte et.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Şimdi gönül rahatlığıyla import edebiliriz, Python artık kör değilse bulacak :)
from app.k8s.executor import KubernetesExecutor

if __name__ == "__main__":
    print("--- Test Başlatılıyor ---")

    # Sınıfımızdan bir işçi (nesne) üretiyoruz
    isci = KubernetesExecutor()

    # Pod listeleme fonksiyonumuzu çağırıyoruz
    sonuc = isci.list_pods(namespace="default")

    print("\nKubernetes'ten Gelen Sonuç:")
    print(sonuc)