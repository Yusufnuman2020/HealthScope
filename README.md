# HealthScope

Kan tahlili sonuçlarını Türkçe bir dil modeliyle yorumlayıp gıda mühendisliği
perspektifinden beslenme protokolü öneren **klinik karar destek sistemi**.

> ⚠️ **HealthScope teşhis koymaz.** Üretilen çıktılar istatistiksel bir
> değerlendirmedir ve hekim muayenesinin yerine geçmez. Tedavi veya beslenme
> değişikliği yapmadan önce doktorunuza danışın.

---

## Mimari

| Katman | Teknoloji |
| --- | --- |
| Arayüz | Next.js 16 (App Router, statik export) + React 19 + Tailwind v4 + Recharts |
| Sunucu | Python 3.12+ / FastAPI |
| Örüntü çıkarımı | BERTurk fill-mask — bu proje için tıbbi metinlerle fine-tune edildi ([model](https://huggingface.co/Ruhadam2020/checkpoint-85239)) |
| Gerekçelendirme | Qwen2.5-3B-Instruct, yerel (fp16) — opsiyonel |
| OCR | EasyOCR (TR + EN), PDF için pdf2image + Poppler |
| Veri | `database.json` — tek dosya, tek doğruluk kaynağı |

### Tek doğruluk kaynağı (single source of truth)

Laboratuvar parametreleriyle ilgili **her şey** `database.json` içindeki
`PARAMETER_CATALOG` bölümünde tanımlıdır:

```jsonc
"insulin": {
  "label": "İnsülin (Açlık)",
  "short": "İNSÜLİN",
  "unit": "uIU/mL",
  "domain": "Endokrinoloji",
  "group": "diyabet",
  "ref": { "min": 2.6, "max": 24.9 },
  "ocr": ["\\b[Iİ]NS[UÜ]L[Iİ]N\\b"],   // OCR desenleri
  "nutrition": { "high": "insulin_resistance" }  // beslenme protokolü
}
```

Backend `catalog.py` üzerinden, frontend `src/lib/catalog.ts` üzerinden **aynı
dosyayı** okur. Form alanları, referans aralıkları, OCR haritası ve besin
eşleştirmesi elle senkronize edilmez — bu yüzden "formda alan var ama backend
tanımıyor" ya da "protokol var ama anahtar tutmuyor" sınıfı hatalar oluşamaz.
`tests/test_catalog.py` bu tutarlılığı her push'ta doğrular.

Yeni bir parametre eklemek için tek yapılacak: `PARAMETER_CATALOG`'a bir kayıt
girmek. Form alanı, OCR desteği ve sapma tespiti otomatik gelir.

### Klinik indeksler

Tek tek parametrelere bakmak, birden fazla parametrenin **oranında** saklı
bilgiyi kaçırır. `CLINICAL_INDICES` bölümü, literatürde tanımlı 16 formülü
hesaplar — tamamen deterministik, her biri kaynak gösterilmiş:

| İndeks | Ne ayırır |
| --- | --- |
| De Ritis (AST/ALT) | alkolik ↔ viral hepatit |
| Mentzer (MCV/RBC) | talasemi ↔ demir eksikliği |
| Transferrin satürasyonu | demir eksikliği ↔ demir yüklenmesi |
| BUN/Kreatinin | prerenal ↔ intrensek renal azotemi |
| FIB-4 | karaciğer fibrozis riski |
| HOMA-IR | insülin direnci |
| eGFR (CKD-EPI 2021) | kronik böbrek hastalığı evresi |
| NLR, PLR | sistemik inflamatuar yük |
| TG/HDL, Non-HDL | aterojenik risk |
| Ca×P, Ozmolarite | mineral-kemik ve sıvı-elektrolit dengesi |

Bu katmanın değeri ölçüldü: dil modelinin ayıramadığı alkolik/viral hepatit
ayrımını De Ritis oranı tek bölme işlemiyle yapıyor. Ayrıca **tüm parametreleri
referans aralığında olan** bir hastada TG/HDL = 3.61 çıkarak parametre bazlı
kontrolün göremediği riski yakalıyor.

Eşikler, yorum metinleri ve kaynakça `database.json`'dadır; formüller
`indices.py` içinde aynı kimliklerle durur (JSON'dan formül `eval` etmek hem
güvensiz hem test edilemez olurdu). `catalog.validate()` ikisinin eşleştiğini
her açılışta doğrular.

Bazı indeksler yalnızca belirli bir tablo varken anlamlıdır — Mentzer indeksi
mikrositoz yoksa hesaplanmaz, aksi hâlde sağlıklı hastada "demir eksikliği
lehine" gibi yanıltıcı bir yorum üretirdi. Bu, `applicable_when` alanıyla
tanımlanır.

---

## Modeller

Sistem iki dil modeli kullanır ve **ikisi de opsiyoneldir** — hiçbiri kurulmasa
bile deterministik kural motoru tam çalışır. Ölçülen isabet oranları için
[Kıyaslama](#kıyaslama) bölümüne bakın.

| Model | Görevi | Zorunlu mu | Boyut |
| --- | --- | --- | --- |
| [`Ruhadam2020/checkpoint-85239`](https://huggingface.co/Ruhadam2020/checkpoint-85239) | Bulgu örüntüsünden olası klinik tabloları sıralar | Hayır — yoksa temel BERTurk'e düşer | 423 MB |
| [`Qwen/Qwen2.5-3B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) | Kural motorunun klinik özetini gerekçelendirip anlaşılır dile çevirir | Hayır — yoksa gerekçeli anlatı üretilmez | 5,9 GB |

### 1. BERTurk — alan uyarlaması

[`dbmdz/bert-base-turkish-cased`](https://huggingface.co/dbmdz/bert-base-turkish-cased)
modelinin **bu proje kapsamında Türkçe tıbbi metinlerle fine-tune edilmiş**
hâli. Hugging Face'te yayında:

```env
HEALTHSCOPE_MODEL_PATH=Ruhadam2020/checkpoint-85239
```

`transformers` bu kimliği ilk açılışta indirir ve önbelleğe alır; yerel bir
dizin yolu da verebilirsiniz. Değişken **boş bırakılırsa** sunucu yine ayağa
kalkar ama fine-tune edilmemiş temel modeli kullanır ve log'a uyarı düşer —
çıkarım kalitesi belirgin şekilde düşer.

### 2. Qwen — hibrit gerekçelendirme katmanı (opsiyonel)

Kural motorunun ürettiği klinik özet üzerinde akıl yürütür. **Teşhis koymaz**;
zaten bulunmuş bulguları gerekçelendirir.

```env
HEALTHSCOPE_LLM_PROVIDER=local
HEALTHSCOPE_LLM_MODEL=Qwen/Qwen2.5-3B-Instruct
HEALTHSCOPE_LLM_QUANTIZE=0
```

Donanım: fp16 olarak **~5,8 GB VRAM** ister; 8 GB'lık bir RTX 4060'ta ölçüldü,
vaka başına ~14 saniye sürüyor. Daha az VRAM'iniz varsa `HEALTHSCOPE_LLM_QUANTIZE=1`
ile 4-bit'e düşürün (`bitsandbytes` gerekir).

GPU'nuz yoksa yerel model yerine bir uç nokta kullanabilirsiniz:

```env
HEALTHSCOPE_LLM_PROVIDER=openai-compatible
HEALTHSCOPE_LLM_BASE_URL=http://localhost:11434/v1
HEALTHSCOPE_LLM_MODEL=qwen2.5:3b
```

Katman kapalıyken (`HEALTHSCOPE_LLM_PROVIDER=none`, varsayılan) sistem eskisi
gibi çalışır; katman hata verse bile analiz sonucu değişmeden döner.

---

## Kurulum

### 1. Backend

Bağımlılıklar **proje içindeki bir sanal ortama** kurulur; global Python'a
dokunulmaz ve kurulum her makinede birebir tekrarlanabilir.

```powershell
# Windows PowerShell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

# NVIDIA GPU varsa önce CUDA'lı torch (yoksa bu satırı atlayın, CPU sürümü kurulur)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

pip install -r requirements.txt
copy .env.example .env       # sonra HEALTHSCOPE_MODEL_PATH'i doldurun
python api_server.py
```

```bash
# macOS / Linux
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python api_server.py
```

Sunucu `http://127.0.0.1:8000` adresinde açılır. `/docs` adresinde interaktif
API dokümantasyonu, `/status` adresinde motor durumu vardır.

> **Not:** Sanal ortam kullanmak sadece temizlik meselesi değil — global
> kurulumda bayat bir `torchvision` sürümü `transformers`'ın pipeline importunu
> sessizce kırabiliyor. `.venv` bu sınıf sorunları tamamen ortadan kaldırır.

`.env` içinde ayarlanabilecekler (hepsi opsiyonel):

| Değişken | Varsayılan | Açıklama |
| --- | --- | --- |
| `HEALTHSCOPE_MODEL_PATH` | — | Fine-tune edilmiş model. HuggingFace kimliği (`Ruhadam2020/checkpoint-85239`) ya da yerel dizin. Boşsa temel model kullanılır — bkz. [Modeller](#modeller). |
| `HEALTHSCOPE_LLM_PROVIDER` | `none` | Hibrit gerekçelendirme katmanı: `none`, `local` ya da `openai-compatible`. |
| `HEALTHSCOPE_POPPLER_PATH` | otomatik | PDF için Poppler `bin` dizini. Boşsa proje kökündeki `POPPLER/` klasöründe ve `PATH` üzerinde aranır. |
| `HEALTHSCOPE_CORS_ORIGINS` | `localhost:3000` | İzinli origin listesi. Sağlık verisi işlendiği için joker (`*`) kullanılmaz. |
| `HEALTHSCOPE_MAX_UPLOAD_MB` | `10` | OCR yükleme sınırı. |
| `HEALTHSCOPE_PORT` | `8000` | Sunucu portu. |

**Kısmi kurulum desteklenir:** EasyOCR/OpenCV kurulu değilse sunucu yine ayağa
kalkar; yalnızca `/upload-report` 503 döner ve arayüz OCR'ı devre dışı gösterir.
Model bulunamazsa `/analyze` açıklayıcı bir hata döner, sunucu çökmez.

#### PDF desteği (opsiyonel)

PDF tahlil raporu yüklemek için Poppler gerekir. İkili dosyalar depoya dahil
değildir — 70 MB'lık platforma özgü bir bağımlılığı sürüm kontrolünde tutmak
doğru değil:

| Platform | Kurulum |
| --- | --- |
| Windows | [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) sürümünü indirip proje köküne `POPPLER/` olarak açın ya da `HEALTHSCOPE_POPPLER_PATH` ile `bin` dizinini gösterin |
| macOS | `brew install poppler` |
| Debian/Ubuntu | `sudo apt install poppler-utils` |

Poppler yoksa görsel (JPG/PNG) yükleme çalışmaya devam eder; yalnızca PDF
girdisi devre dışı kalır.

### 2. Frontend

```bash
npm install
npm run dev
```

Arayüz `http://localhost:3000/HealthScope` adresinde açılır (`basePath`
GitHub Pages için `/HealthScope` olarak ayarlıdır).

Backend farklı bir adreste çalışıyorsa:

```bash
NEXT_PUBLIC_API_URL=http://192.168.1.20:8000 npm run dev
```

---

### Hızlı başlatma (Windows)

`baslat.bat` dosyasına çift tıklamak yeterlidir: sanal ortamı ve `node_modules`'ü
kontrol eder, port 8000 zaten doluysa uyarır, iki sunucuyu ayrı pencerelerde
başlatır ve arayüz hazır olunca tarayıcıyı açar.

---

## Testler

```bash
python -m pytest tests -q
npx eslint src
npm run build
```

### Doğruluk değerlendirmesi

Windows'ta `test.bat` dosyasına çift tıklamak yeterlidir: vaka havuzunu doğrular,
pytest'i çalıştırır, deterministik doğruluğu ölçer ve backend açıksa dil modeli
katmanını da ölçer.

Elle:

```bash
python scripts/evaluate.py             # sunucu çalışıyor olmalı
python scripts/evaluate.py --offline   # sadece deterministik katmanlar
```

`presets.json` içindeki **130 klinik vakayı** çalıştırıp motorun dört katmanını
ayrı ayrı puanlar. Bu ayrım önemlidir: deterministik katmanlar (sapma tespiti,
baskın alan, beslenme eşleşmesi) ile olasılıksal katmanın (dil modeli)
doğrulukları birbirinden çok farklıdır ve tek bir "doğruluk" rakamı bunu gizler.

`presets.json` hem arayüzdeki vaka havuzunu hem de bu değerlendirmeyi besler —
ikisi asla birbirinden sapamaz.

### Vaka havuzunu üretmek

Vakalar elle yazılmaz; `scripts/build_presets.py` içindeki **klinik arketiplerden**
üretilir. Her arketip hastalığın tipik "orta şiddet" panelini tanımlar; hafif ve
ağır varyantlar, değerin *referans sınırından sapma miktarı* ölçeklenerek
türetilir. Böylece sapmanın yönü ve klinik tutarlılık korunur.

```bash
python scripts/build_presets.py --check   # doğrula, yazma
python scripts/build_presets.py           # presets.json'u yeniden üret
```

Betik yazmadan önce her vakayı katalogla karşılaştırır: bilinmeyen parametre,
sapma üretmeyen "etkisiz" vaka ya da kirlenmiş negatif kontrol varsa hata verir.
Yeni bir hastalık eklemek için `ARCHETYPES` listesine bir kayıt girmek yeterlidir —
üç şiddet varyantı, arayüzdeki kart ve testteki beklenen sonuç otomatik oluşur.

`tests/test_catalog.py` veri bütünlüğünü, `tests/test_analysis.py` sapma
matematiğini, prompt güvenliğini, OCR çıkarımını ve `/analyze` uç noktasını
(model sahte bir pipeline ile değiştirilerek) doğrular.

---

## Mimari: kural motoru + hibrit akıl yürütme

Analiz üç katmandan geçer. Deterministik katmanlar sonucu üretir; dil modeli
onların **üzerinde** akıl yürütür — tersi değil.

```
Laboratuvar değerleri
        ↓
1. SAPMA TESPİTİ        referans aralığı karşılaştırması (cinsiyete duyarlı)
        ↓
2. KLİNİK İNDEKSLER     De Ritis, FIB-4, HOMA-IR, eGFR, NLR, Mentzer...
   + bağlam düzelticileri  "AST/ALT>2 ama GGT normal → alkol değil, kas"
   + ayırt edici test      "CK ölçülmeli"
        ↓
3. clinical_brief.py    yapılandırılmış klinik özet üretir
        ↓
4. llm.py               üretken model gerekçeli değerlendirme yazar (opsiyonel)
```

**Neden bu sıra:** dil modeline ham sapma listesi verildiğinde 130 vakada
isabet %50'ydi ve ağır karaciğer / böbrek / anemi vakalarına aynı cevabı
veriyordu. İşlenmiş klinik öznitelik verildiğinde model çok daha isabetli
çalışır; çünkü akıl yürütmenin yarısını kural motoru zaten yapmıştır.

Hibrit katman **tamamen opsiyoneldir**. `HEALTHSCOPE_LLM_PROVIDER=none` iken
sistem eskisi gibi çalışır; katman hata verse bile analiz sonucu değişmeden
döner.

### Kıyaslama

```bash
python scripts/benchmark_inference.py            # 130 vaka, üç katman
python scripts/benchmark_inference.py --limit 20 # hızlı deneme
```

Aynı vaka setinde `baseline` (BERTurk fill-mask), `rules` (kural motoru) ve
`hybrid` (kural → LLM) yaklaşımlarını karşılaştırır. Beklenen klinik konusu
tanımlı 126 vakadaki son ölçüm:

| Yaklaşım | İsabet | Ortalama süre |
| --- | --- | --- |
| BERTurk fill-mask (tek başına) | 82 / 126 (%65) | 27 ms |
| Kural motoru + klinik indeks | 126 / 126 (%100) | < 1 ms |
| **Hibrit: kural motoru → üretken model** | **119 / 126 (%94)** | 14.4 s |

Kural motoru satırındaki %100 **tautolojiktir** — ölçüt, motorun kendi ürettiği
bulgu etiketlerini tarıyor. Anlamlı karşılaştırma birinci ve üçüncü satır
arasındadır: aynı ölçütte tek başına dil modeli %65'te kalırken, kural
motorunun çıkardığı klinik özniteliklerle beslendiğinde %94'e çıkıyor.

Ayrıntı ve yöntem: [`docs/nasil-calisir.md`](docs/nasil-calisir.md).

## API

| Uç nokta | Açıklama |
| --- | --- |
| `GET /status` | Motor durumu, donanım, katalog envanteri, yükleme sınırları. Arayüzdeki tüm metrik kartları bunu tüketir. |
| `POST /analyze` | Tahlil değerleri + biyometri + öykü → sapmalar, klinik örüntüler, beslenme protokolü. |
| `POST /upload-report` | PDF/görsel tahlil raporu → çıkarılan parametre değerleri. |

Her iki ağır uç nokta da `def` (async değil) tanımlıdır; FastAPI bunları
threadpool'da çalıştırır, böylece eşzamanlı istekler event loop'u bloklamaz.

---

## Güvenlik notları

- Kullanıcı metinleri (`kronik`, `genetik_riskler`) prompt'a girmeden önce
  temizlenir: `[MASK]` gibi özel token'lar ve yapısal karakterler kaldırılır,
  uzunluk sınırlanır. Bu bir prompt injection savunmasıdır.
- CORS izinli listesi ile sınırlıdır, `allow_credentials` kapalıdır.
- Yüklemeler boyut ve sayfa sayısı ile sınırlıdır.
- Tahlil verisi diske yazılmaz, dışarı gönderilmez; tüm işleme yereldir.
- Gösterilen olasılıklar, elenen adaylar çıkarıldıktan sonra yeniden normalize
  edilmiş **model skorlarıdır** — klinik olasılık değildir ve yanıtta ham skor
  da korunur.

---

## Yayın

`main` dalına push, GitHub Actions ile **yalnızca arayüzü** GitHub Pages'e
yayınlar. Yapay zekâ çekirdeği yerel çalıştığı için yayınlanan sitede analiz
sayfası "backend çevrimdışı" uyarısı gösterir; bu beklenen davranıştır.
Erişilebilir bir backend varsa repo ayarlarında `NEXT_PUBLIC_API_URL`
variable'ı tanımlanabilir.
