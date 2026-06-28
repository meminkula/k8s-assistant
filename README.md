# Doğal Dil Tabanlı Kubernetes Yönetim Asistanı — Mimari Dokümanı

## 0. Önsöz: Teknoloji Seçimleri ve Gerekçeleri


| Bileşen | Seçim | Neden |
|---|---|---|
| Backend dili | **Python 3.11+ / FastAPI** | Resmi `kubernetes` Python istemcisi çok olgun; Pydantic ile şema doğrulama doğal geliyor (LLM çıktısını doğrulamak için tam ihtiyacımız olan şey); async/WebSocket desteği canlı durum güncellemeleri için uygun; Ollama ile HTTP entegrasyonu trivial. |
| LLM çalışma zamanı | **Ollama + Llama 3.1 8B Instruct** (alternatif: Mistral 7B Instruct) | Yerel çalışır, veri dışarı çıkmaz (cluster bilgisi hassas olabilir — bu gizlilik avantajı projenin satış noktalarından biri), JSON-mode/structured output desteği yeterli düzeyde, 8B model tüketici donanımında (16GB+ RAM, ideal olarak GPU) makul hızda çalışır. |
| Test/geliştirme cluster'ı | **kind (Kubernetes IN Docker)** | minikube'den daha hafif, multi-node cluster simülasyonu yapılabilir, CI/CD pipeline'larına kolay entegre olur, Docker zaten gerekli bir bağımlılık. |
| Kubernetes istemcisi | **Resmi `kubernetes` Python client (client-python)** | API sunucusuyla doğrudan, tip-güvenli iletişim; `kubectl` subprocess çağırmaktan (shell injection riski, parse zorluğu) çok daha güvenli ve test edilebilir. |
| Session/state deposu | **Redis** (geliştirme aşamasında SQLite de yeterli) | State machine'in oturum durumunu (hangi cluster, hangi namespace, bekleyen onaylar) hızlı okuma/yazma ile tutmak için. |
| Frontend | **React + WebSocket** (MVP'de düz HTML/JS de kabul edilebilir) | Canlı state güncellemeleri, onay diyalogları için reaktif arayüz. |


---

## 1. Temel Felsefe: Güç Ayrımı (Separation of Authority)

Bu projenin tüm mimarisi tek bir ilkeden türüyor:

> **LLM hiçbir zaman bir eylemi doğrudan tetikleyemez. LLM sadece serbest metni yapılandırılmış veriye çevirir. Yapılandırılmış veriyi doğrulayan, oturum durumuyla birleştiren, gerçek dünyada bir şey değiştiren her adım, deterministik ve test edilebilir kod tarafından yönetilir.**

Bunun pratik anlamı şu: LLM'in çıktısı asla şu şekillerde kullanılmaz:
- Doğrudan bir `kubectl` komutu string'i olarak
- Doğrudan bir Kubernetes API çağrısı parametresi olarak (ara doğrulama katmanı olmadan)
- Bir shell komutuna enjekte edilen serbest metin olarak

Bunun yerine LLM'in çıktısı **her zaman** önceden tanımlı bir JSON şemasına uyan, sınırlı bir alana (whitelist) ait, ayrı bir doğrulama katmanından geçen bir yapıdır. Bu ayrım üç somut riski ortadan kaldırır:

1. **Halüsinasyon riski**: LLM "var olmayan bir namespace" veya "yanlış bir kaynak adı" üretebilir. Doğrulama katmanı bunu cluster'ın gerçek durumuyla karşılaştırır, eşleşmezse LLM'in önerisini reddeder.
2. **Prompt injection riski**: Kullanıcı (veya kötü niyetli bir üçüncü taraf, örneğin bir pod log'una gömülmüş zararlı metin) LLM'i manipüle edip "tüm namespace'i sil" gibi bir niyet ürettirmeye çalışabilir. Whitelist + onay katmanı, LLM'in ürettiği niyet ne olursa olsun, yıkıcı bir eylemin kullanıcı onayı almadan gerçekleşmesini engeller.
3. **Belirlenemezlik riski**: Aynı girdi için LLM her zaman aynı çıktıyı üretmeyebilir (temperature, model güncellemeleri, vb.). Çekirdek algoritma deterministik olduğu için, aynı doğrulanmış JSON her zaman aynı sonucu üretir — bu, sistemi test edilebilir ve öngörülebilir kılar.

---

## 2. Üst Düzey Sistem Mimarisi

Sistem altı ana katmandan oluşur. Her katman, bir öncekinin çıktısını girdiği olarak alır ve kendi sorumluluk alanı dışına çıkmaz.

```
┌─────────────────────────────────────────────────────────────────┐
│  1. FRONTEND (React + WebSocket)                                 │
│     - Doğal dil giriş kutusu                                     │
│     - Canlı durum/rapor görüntüleme                               │
│     - Onay diyalogları (yıkıcı eylemler için)                    │
└───────────────────────────┬───────────────────────────────────────┘
                            │ HTTP/WebSocket
┌───────────────────────────▼───────────────────────────────────────┐
│  2. API GATEWAY (FastAPI)                                         │
│     - İstek doğrulama, kimlik doğrulama, rate limiting           │
│     - Oturum yönetimi (session_id üretimi/takibi)                │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────────┐
│  3. LLM TERCÜMAN KATMANI (Ollama + Llama 3.1)                     │
│     - Serbest metni alır                                         │
│     - Önceden tanımlı JSON şemasına uyan intent+parametre üretir  │
│     - HİÇBİR durumda K8s API'sine veya shell'e erişimi yoktur     │
└───────────────────────────┬───────────────────────────────────────┘
                            │ Ham JSON (henüz güvenilmez)
┌───────────────────────────▼───────────────────────────────────────┐
│  4. DOĞRULAMA & ŞEMA KATMANI (Pydantic)                          │
│     - JSON şema uyumluluğu kontrolü                               │
│     - Intent whitelist kontrolü                                  │
│     - Parametre tipi/aralık kontrolü                              │
│     - Cluster'daki gerçek kaynaklarla çapraz doğrulama            │
└───────────────────────────┬───────────────────────────────────────┘
                            │ Doğrulanmış komut nesnesi
┌───────────────────────────▼───────────────────────────────────────┐
│  5. ÇEKİRDEK STATE MACHINE (deterministik Python kodu)            │
│     - Oturum durumunu yükler (Redis)                              │
│     - Doğrulanmış komutu mevcut durumla birleştirir               │
│     - Yıkıcı eylemler için onay durumuna geçer                    │
│     - Onaylanan eylemi Kubernetes Executor'a iletir               │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────────┐
│  6. KUBERNETES EXECUTOR (client-python)                          │
│     - Sadece önceden tanımlı, parametreli API çağrılarını yapar  │
│     - Ham API yanıtını (genellikle JSON/objects) döndürür         │
└───────────────────────────┬───────────────────────────────────────┘
                            │ Ham sonuç
┌───────────────────────────▼───────────────────────────────────────┐
│  7. ÇIKTI İŞLEMCİ / RAPORLAYICI                                  │
│     - Ham K8s nesnesini temizler, ilgisiz alanları süzer          │
│     - (Opsiyonel) İkinci bir LLM çağrısı ile insan-okunur özet    │
│     - Frontend'e WebSocket ile gönderir                           │
└─────────────────────────────────────────────────────────────────┘
```

Şimdi her katmanı tek tek, somut detaylarla ele alalım.

---

## 3. Katman Detayı: LLM Tercüman Katmanı

### 3.1. Sorumluluğu

Bu katmanın **tek** görevi şudur: kullanıcının serbest metnini alıp, önceden tanımlı bir JSON şemasına uyan bir yapıya çevirmek. Başka hiçbir şey yapmaz — karar vermez, doğrulamaz, çalıştırmaz.

### 3.2. İzin Verilen Intent Kümesi (Whitelist)

LLM'in üretebileceği `intent` alanı, sabit ve önceden tanımlı bir listeden gelir. Bu liste backend kodunda bir enum olarak tanımlanır, LLM'e prompt içinde bu liste açıkça verilir, ve LLM listenin dışında bir değer üretirse doğrulama katmanı bunu otomatik olarak reddeder.

MVP için önerilen başlangıç kümesi (risk seviyesine göre gruplanmış):

**Salt-okunur (otomatik onaylı, risksiz):**
- `list_pods` — namespace'teki pod'ları listele
- `list_deployments` — deployment'ları listele
- `describe_resource` — bir kaynağın detayını göster
- `get_logs` — pod loglarını getir
- `get_events` — namespace olaylarını getir
- `get_resource_usage` — CPU/bellek kullanımını göster

**Yarı-yıkıcı (kullanıcı onayı zorunlu):**
- `restart_deployment` — deployment'ı yeniden başlat (rollout restart)
- `scale_deployment` — replica sayısını değiştir
- `rollback_deployment` — önceki revizyona dön

**Yıkıcı (kullanıcı onayı + ikinci doğrulama adımı zorunlu):**
- `delete_pod` — belirli bir pod'u sil
- `delete_deployment` — bir deployment'ı tamamen sil
- `scale_to_zero` — bir deployment'ı 0 replica'ya indir (etkin biçimde durdurma)

Bu üç kategori, state machine'in onay mantığını doğrudan belirler (Bölüm 5'te detaylandırılıyor).

### 3.3. JSON Şeması (Pydantic Modeli)

LLM'in üretmesi gereken çıktı, Pydantic ile şu şekilde tanımlanır:

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class IntentType(str, Enum):
    LIST_PODS = "list_pods"
    LIST_DEPLOYMENTS = "list_deployments"
    DESCRIBE_RESOURCE = "describe_resource"
    GET_LOGS = "get_logs"
    GET_EVENTS = "get_events"
    GET_RESOURCE_USAGE = "get_resource_usage"
    RESTART_DEPLOYMENT = "restart_deployment"
    SCALE_DEPLOYMENT = "scale_deployment"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    DELETE_POD = "delete_pod"
    DELETE_DEPLOYMENT = "delete_deployment"
    SCALE_TO_ZERO = "scale_to_zero"

class ParsedIntent(BaseModel):
    intent: IntentType
    namespace: str = Field(default="default")
    resource_name: Optional[str] = None
    replica_count: Optional[int] = Field(default=None, ge=0, le=100)
    revision: Optional[int] = None
    confidence: float = Field(ge=0.0, le=1.0)
    raw_user_text: str  # denetim/loglama için orijinal metin saklanır
```

Burada `confidence` alanı önemli bir tasarım kararı: LLM'den kendi eminlik derecesini de istiyoruz. Eğer LLM düşük bir confidence (örn. 0.5'in altı) bildirirse, state machine kullanıcıya doğrudan netleştirici bir soru sorar, eylemi hiç denemez.

### 3.4. Prompt Tasarımı Yaklaşımı

LLM'e gönderilen sistem promptu şu prensiplere uyar:

1. **İzin verilen intent listesi açıkça verilir**, liste dışı bir değer üretmemesi istenir.
2. **Few-shot örnekler** verilir — kullanıcı cümlesi → beklenen JSON çıktısı eşleşmesi, özellikle Türkçe ve İngilizce karışık kullanım ihtimaline karşı çeşitli örnekler.
3. **JSON-only çıktı zorunluluğu** — Ollama'nın `format: json` parametresi kullanılır, bu modelin sadece geçerli JSON üretmesini zorunlu kılan bir mekanizma.
4. **Belirsizlik durumunda düşük confidence üretmesi** açıkça istenir — "eğer kullanıcı hangi kaynaktan bahsettiği belirsizse, confidence değerini düşür" talimatı.

Örnek prompt iskeleti (kısaltılmış):

```
Sen bir Kubernetes komut tercümanısın. Kullanıcının doğal dil isteğini
aşağıdaki JSON şemasına uyan bir yapıya çevir. SADECE JSON döndür,
başka hiçbir metin ekleme.

İzin verilen intent değerleri: [list_pods, list_deployments, ...]

Örnekler:
Kullanıcı: "production namespace'indeki podları göster"
Çıktı: {"intent": "list_pods", "namespace": "production", "confidence": 0.95, ...}

Kullanıcı: "şu deployment'ı yeniden başlat"
Çıktı: {"intent": "restart_deployment", "namespace": "default",
        "resource_name": null, "confidence": 0.4, ...}
        # confidence düşük çünkü "şu" hangi deployment belirsiz

Şimdi şu kullanıcı isteğini çevir:
{user_input}
```

### 3.5. Neden LLM'e Doğrudan K8s Erişimi Verilmiyor

Bu noktayı tekrar netleştirmek önemli: LLM çalışma zamanı (Ollama süreci), Kubernetes API sunucusuna, kubeconfig dosyasına, veya herhangi bir kimlik bilgisine **hiçbir ağ veya dosya sistemi erişimine sahip değildir**. Bu, container/process seviyesinde izolasyonla (örneğin LLM'i ayrı bir Docker container'ında, K8s servis hesabı kimlik bilgileri olmadan çalıştırarak) güvence altına alınır — sadece mimari bir niyet değil, işletimsel bir gerçektir.

---

## 4. Katman Detayı: Doğrulama ve Şema Katmanı

LLM'den gelen ham JSON, çekirdek state machine'e ulaşmadan önce şu sıralı kontrollerden geçer. Herhangi bir kontrol başarısız olursa, işlem orada durur ve kullanıcıya anlaşılır bir hata/netleştirme mesajı döner.

### 4.1. Şema Uyumluluğu Kontrolü
Pydantic, LLM'in çıktısını `ParsedIntent` modeline parse etmeye çalışır. Eksik zorunlu alan, yanlış tip (örn. `replica_count` için string gelmesi), veya enum dışı bir `intent` değeri varsa, bu adımda otomatik olarak hata fırlatılır.

### 4.2. Confidence Eşik Kontrolü
`confidence < 0.6` ise (eşik değer ayarlanabilir), sistem eylemi denemeden kullanıcıya netleştirici bir soru döner: *"Hangi deployment'tan bahsediyorsunuz? Mevcut deployment'lar: api-gateway, auth-service, worker-queue"*

### 4.3. Cluster Gerçekliği ile Çapraz Doğrulama
Bu kritik bir adım: LLM'in ürettiği `namespace` ve `resource_name` değerleri, gerçekten cluster'da var mı kontrol edilir (bu kontrol de Kubernetes Executor üzerinden read-only bir API çağrısıyla yapılır, LLM'e değil). Eğer LLM "auth-servic" (yazım hatalı) gibi var olmayan bir kaynak adı üretmişse, sistem en yakın eşleşen gerçek kaynak adını önerir ("auth-service mi demek istediniz?") — bunu yine LLM'e sormadan, basit bir string-benzerlik algoritmasıyla (örn. Levenshtein distance) çekirdek kod yapar.

### 4.4. Yetki/RBAC Kontrolü
Sistemin kullandığı Kubernetes servis hesabının, talep edilen işlemi yapmaya yetkisi olup olmadığı kontrol edilir. Örneğin sistem salt-okunur bir RBAC rolüyle çalışıyorsa, `delete_deployment` gibi bir intent, API'ye gitmeden önce burada reddedilir.

---

## 5. Katman Detayı: Çekirdek State Machine

Bu, sistemin "beyni" — yani bahsettiğin orijinal tasarımdaki "esas kontrolü elinde tutan algoritma." Tamamen deterministiktir: aynı girdi (doğrulanmış komut + mevcut oturum durumu) her zaman aynı durum geçişini üretir.

### 5.1. Durumlar (States)

```
IDLE
  │  (kullanıcı mesajı gelir)
  ▼
PARSING               (LLM çağrısı yapılıyor)
  │
  ▼
VALIDATING            (Bölüm 4'teki kontroller)
  │
  ├──[hata/belirsizlik]──► AWAITING_CLARIFICATION ──► (kullanıcı yanıtı) ──► PARSING
  │
  ▼ [doğrulama başarılı]
RISK_ASSESSMENT        (intent risk kategorisine bakılır)
  │
  ├──[salt-okunur]────────────────────────────────► EXECUTING
  │
  └──[yarı-yıkıcı veya yıkıcı]──► AWAITING_CONFIRMATION
                                        │
                                        ├──[kullanıcı onaylamadı]──► IDLE
                                        │
                                        └──[kullanıcı onayladı]──► EXECUTING
  ▼
EXECUTING              (Kubernetes Executor çağrılıyor)
  │
  ├──[API hatası]──► ERROR_HANDLING ──► IDLE (hata raporu ile)
  │
  ▼ [başarılı]
PROCESSING_OUTPUT      (ham sonuç temizleniyor/özetleniyor)
  │
  ▼
REPORTING              (frontend'e WebSocket ile gönderiliyor)
  │
  ▼
IDLE                   (oturum durumu güncellenmiş halde bekliyor)
```

### 5.2. Oturum Durumu (Session State) Yapısı

Her kullanıcı oturumu Redis'te şu yapıda saklanır:

```python
class SessionState(BaseModel):
    session_id: str
    current_state: StateEnum
    active_namespace: str = "default"
    last_intent: Optional[ParsedIntent] = None
    pending_confirmation: Optional[ParsedIntent] = None
    conversation_history: list[dict] = []  # son N etkileşim, LLM bağlamı için
    cluster_context: str  # hangi kubeconfig context'i kullanılıyor
    created_at: datetime
    last_activity_at: datetime
```

`active_namespace` alanı özellikle kullanıcı deneyimi için önemli: kullanıcı bir kere "production namespace'inde çalış" dediğinde, sonraki komutlarda namespace'i tekrar söylemesi gerekmez — state machine bunu oturum bağlamından otomatik doldurur. Bu, LLM'in her seferinde namespace'i doğru tahmin etmesi gerekliliğini de azaltır.

### 5.3. Onay Mekanizmasının Detayı (Kritik Güvenlik Noktası)

`AWAITING_CONFIRMATION` durumu, projenin en önemli güvenlik garantisini temsil eder. Bu durumda:

1. Sistem, yapılacak işlemin **tam olarak ne olduğunu** açık, teknik bir dille kullanıcıya gösterir (LLM'in ürettiği özet değil, doğrulanmış komut nesnesinden türetilen deterministik bir metin): *"production namespace'indeki 'api-gateway' deployment'ı SİLİNECEK. Bu işlem geri alınamaz. Onaylıyor musunuz?"*
2. Yıkıcı kategori (`delete_*`, `scale_to_zero`) için, tek bir onay yetmez — kullanıcının kaynak adını **yeniden yazarak** doğrulaması istenir (örneğin "SİL api-gateway" yazması gerekir). Bu, yanlışlıkla tıklanan bir "evet" butonunun felakete yol açmasını engeller.
3. Onay süresi sınırlıdır (örn. 60 saniye) — süre dolarsa işlem otomatik olarak iptal edilir, eski bir onay başka bir bağlamda geçerli kabul edilmez.
4. Her onay/red, audit log'a zaman damgası, kullanıcı kimliği ve tam komut içeriğiyle kaydedilir.

---

## 6. Katman Detayı: Kubernetes Executor

### 6.1. Sorumluluğu
Bu katman, doğrulanmış ve (gerekirse) onaylanmış komut nesnesini alır ve **önceden tanımlı, parametreli** bir Kubernetes API fonksiyonuna çevirir. Burada da bir whitelist mantığı var: her `IntentType` değeri, koddaki sabit bir fonksiyona eşlenir, hiçbir zaman dinamik/serbest bir API çağrısı oluşturulmaz.

```python
INTENT_TO_EXECUTOR_MAP = {
    IntentType.LIST_PODS: executor.list_pods,
    IntentType.RESTART_DEPLOYMENT: executor.restart_deployment,
    IntentType.DELETE_DEPLOYMENT: executor.delete_deployment,
    # ... her intent için sabit, test edilmiş bir fonksiyon
}
```

### 6.2. Örnek Executor Fonksiyonu

```python
from kubernetes import client

def restart_deployment(namespace: str, name: str) -> dict:
    apps_v1 = client.AppsV1Api()
    # Kubernetes'in "rollout restart" davranışını taklit eden
    # standart yöntem: pod template'e bir annotation eklemek
    now = datetime.utcnow().isoformat()
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": now
                    }
                }
            }
        }
    }
    result = apps_v1.patch_namespaced_deployment(
        name=name, namespace=namespace, body=patch
    )
    return {"status": "success", "deployment": name, "restarted_at": now}
```

Dikkat edilmesi gereken nokta: bu fonksiyon hiçbir serbest metin/string interpolasyonu kabul etmiyor; `name` ve `namespace` parametreleri zaten Bölüm 4'te cluster gerçekliğine karşı doğrulanmış durumda.

### 6.3. Servis Hesabı ve RBAC Yapılandırması

Sistemin kullandığı Kubernetes servis hesabı, mümkün olan en az yetkiyle (least privilege) yapılandırılır. Önerilen RBAC rolü örneği:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: llm-assistant-role
rules:
  - apiGroups: [""]
    resources: ["pods", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch", "patch"]
    # NOT: "delete" verb'i bilinçli olarak çıkarılabilir,
    # eğer "yıkıcı" kategori MVP'de devre dışı bırakılacaksa
```

Bu, mimarideki uygulama-seviyesi onay mekanizmasının üzerine **bir savunma katmanı daha** ekler: uygulama kodunda bir hata olsa bile, Kubernetes'in kendi RBAC sistemi son bir engel olarak durur.

---

## 7. Katman Detayı: Çıktı İşleme ve Raporlama

### 7.1. Neden Bu Katman Ayrı

Kubernetes API'sinden dönen ham yanıtlar (özellikle `describe` benzeri işlemler) çok büyük, gürültülü JSON nesneleridir — yüzlerce alan, çoğu kullanıcı için anlamsız. Bu katmanın görevi:

1. **Süzme**: İlgisiz/teknik alanları (örn. `managedFields`, uzun `resourceVersion` zincirleri) kaldırmak.
2. **Yapılandırma**: Kalan veriyi kullanıcı arayüzünde gösterilecek bir yapıya (tablo, zaman çizelgesi, durum rozetleri) dönüştürmek.
3. **(Opsiyonel) İnsan-okunur özet**: İkinci bir LLM çağrısı burada devreye girebilir — ama dikkat: bu çağrı **sadece sunum amaçlıdır**, hiçbir karar üretmez, hiçbir eylemi tetiklemez. Örneğin ham pod listesini alıp "3 pod çalışıyor, 1 pod CrashLoopBackOff durumunda, son 10 dakikada 2 yeniden başlama oldu" gibi bir özet üretebilir. Bu LLM çağrısının çıktısı asla başka bir işlemi tetiklemez, sadece ekrana yazılır.

### 7.2. Sayısal Doğruluk İlkesi

Önemli bir tasarım kararı: **sayısal hesaplamalar (pod sayısı, restart sayısı, kaynak kullanım yüzdesi) asla LLM'e bırakılmaz.** Bu hesaplamalar deterministik Python kodu tarafından yapılır, LLM'e sadece zaten hesaplanmış sayılar verilir ve LLM bunları doğal dile çevirir. Bu, LLM'in sayısal halüsinasyon yapma riskini (örneğin "5 pod var" derken gerçekte 7 pod olması) tamamen ortadan kaldırır.

---

## 8. Uçtan Uca Örnek Akış

Somutlaştırmak için, gerçek bir kullanıcı etkileşimini baştan sona takip edelim:

**Kullanıcı yazıyor:** *"production'daki api-gateway'i yeniden başlat"*

1. **Frontend** → API Gateway'e WebSocket üzerinden mesaj + `session_id` gönderir.
2. **API Gateway**, oturumu Redis'ten yükler (`active_namespace` zaten yoksa, mesajdaki "production" kelimesi LLM tarafından çıkarılacak).
3. **LLM Tercüman Katmanı**, şu JSON'u üretir:
   ```json
   {"intent": "restart_deployment", "namespace": "production",
    "resource_name": "api-gateway", "confidence": 0.92,
    "raw_user_text": "production'daki api-gateway'i yeniden başlat"}
   ```
4. **Doğrulama Katmanı**: Şema geçerli ✓, confidence eşiği geçti ✓, `production` namespace'i cluster'da var mı kontrol edilir (read-only API çağrısı) ✓, `api-gateway` deployment'ı o namespace'te var mı kontrol edilir ✓, RBAC izni var mı kontrol edilir ✓.
5. **State Machine**: `restart_deployment` "yarı-yıkıcı" kategoride olduğu için `AWAITING_CONFIRMATION` durumuna geçer. Frontend'e onay isteği gönderilir: *"production namespace'indeki 'api-gateway' deployment'ı yeniden başlatılacak (tüm pod'lar sırayla yeniden oluşturulacak, kısa kesintiler olabilir). Onaylıyor musunuz?"*
6. **Kullanıcı onaylar** → State Machine `EXECUTING` durumuna geçer.
7. **Kubernetes Executor**, `restart_deployment(namespace="production", name="api-gateway")` fonksiyonunu çağırır, gerçek API isteği gönderilir.
8. **Çıktı İşlemci**, dönen sonucu alır, "İşlem başarılı, yeniden başlatma 14:32:07'de tetiklendi" gibi bir rapora çevirir.
9. **Frontend**, bu raporu gösterir, ayrıca isteğe bağlı olarak rollout durumunu canlı takip etmek için bir `watch` bağlantısı açabilir (pod'ların tek tek yeniden oluşturulduğunu canlı gösterir).
10. **Oturum durumu güncellenir**: `active_namespace = "production"` olarak kaydedilir, böylece kullanıcı sonraki mesajında namespace'i tekrar söylemek zorunda kalmaz.

---

## 9. Proje Klasör Yapısı (Önerilen)

```
k8s-llm-asistan/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI giriş noktası
│   │   ├── llm/
│   │   │   ├── prompt_templates.py  # Sistem promptları, few-shot örnekler
│   │   │   ├── ollama_client.py     # Ollama API ile iletişim
│   │   │   └── schemas.py           # Pydantic: ParsedIntent, IntentType
│   │   ├── validation/
│   │   │   ├── validators.py        # Bölüm 4'teki kontroller
│   │   │   └── fuzzy_match.py       # Kaynak adı benzerlik kontrolü
│   │   ├── state_machine/
│   │   │   ├── states.py            # StateEnum, geçiş tablosu
│   │   │   ├── session.py           # SessionState modeli, Redis I/O
│   │   │   └── engine.py            # Ana state machine mantığı
│   │   ├── k8s/
│   │   │   ├── executor.py          # Her intent için executor fonksiyonu
│   │   │   └── client_factory.py    # kubeconfig/servis hesabı yönetimi
│   │   ├── reporting/
│   │   │   ├── formatters.py        # Ham K8s objesi → temiz yapı
│   │   │   └── summarizer.py        # Opsiyonel ikinci LLM çağrısı
│   │   └── websocket/
│   │       └── connection_manager.py
│   ├── tests/
│   │   ├── test_validation.py
│   │   ├── test_state_machine.py    # Her durum geçişi için test
│   │   └── test_executor.py         # kind cluster'a karşı entegrasyon testleri
│   └── requirements.txt
├── frontend/
│   └── (React uygulaması)
├── infra/
│   ├── rbac.yaml                    # Bölüm 6.3'teki RBAC tanımı
│   └── kind-config.yaml             # Test cluster yapılandırması
└── docs/
    └── architecture.md              # Bu doküman
```

---

## 10. Geliştirme Yol Haritası 


**Faz 1 — Sadece Okuma (1-2 hafta)**
Sadece salt-okunur intent'leri (`list_pods`, `describe_resource`, `get_logs`) destekle. Onay mekanizması yok, çünkü risk yok. Bu faz, LLM tercüman katmanını ve doğrulama katmanını sağlamlaştırmaya odaklanır — en kırılgan kısım burası.

**Faz 2 — Yarı-Yıkıcı Eylemler + Onay Mekanizması (1-2 hafta)**
`restart_deployment`, `scale_deployment` eklenir. `AWAITING_CONFIRMATION` durumu ve onay UI'ı inşa edilir. Bu fazın çıktısı, projenin "öne çıkan" mühendislik kararını (LLM'e yıkıcı yetki vermeme) gösterebileceğin ilk versiyon.

**Faz 3 — Raporlama ve Özet Katmanı (3-5 gün)**
İkinci LLM çağrısı ile insan-okunur özetler. Canlı `watch` bağlantılarıyla rollout takibi.

**Faz 4 — Yıkıcı Eylemler + Çift Onay (3-5 gün)**
`delete_*`, `scale_to_zero` eklenir, çift-doğrulama (kaynak adını yeniden yazma) mekanizması inşa edilir. Audit log sistemi eklenir.

**Faz 5 — Sertleştirme (devam eden)**
RBAC sıkılaştırma, rate limiting, çok-kullanıcılı oturum yönetimi, prompt injection testleri (örneğin pod loglarına gömülü zararlı metnin LLM'i manipüle edip edemediğini test etme).

---

## 11. Bu Mimarinin Test Edilebilirliği

Son bir not: bu mimarinin LLM-tabanlı rakiplerinden en somut farkı, **çoğu katmanın LLM'siz test edilebilir olmasıdır.** State machine, doğrulama katmanı, Kubernetes Executor — bunların hepsi sabit, deterministik girdilerle (LLM'i hiç çağırmadan) unit test edilebilir. Sadece LLM Tercüman Katmanı, doğası gereği olasılıksal test gerektirir (örnek cümle setleri üzerinde "ne kadar doğru intent üretiyor" ölçümü). Bu ayrım, projenin mühendislik kalitesini göstermek için mülakatta veya README'de kullanabileceğin çok güçlü bir argümandır: *"Sistemimin %90'ı geleneksel, deterministik unit testlerle kapsanıyor; LLM'in belirsizliği sadece tek, izole bir katmanda yaşıyor."*
