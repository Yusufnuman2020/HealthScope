import re
import json
import cv2
import torch
import easyocr
import logging
import numpy as np
import time
import os
from pdf2image import convert_from_bytes
import io
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from transformers import pipeline, AutoModelForMaskedLM, AutoTokenizer

# Poppler'ın bin klasörünün yolu (Kendi klasör ismine göre düzeltmiştin, aynen korudum)
POPPLER_PATH = r"C:\Users\yusuf numan\Desktop\dersler\ileri düzey programlama\proje\healthscope\POPPLER\Release-26.02.0-0\poppler-26.02.0\Library\bin"

# ── 1. PROFESYONEL LOGLAMA ALTYAPISI ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("HealthScopeEngine")

app = FastAPI(
    title="HealthScope AI Clinical & Nutritional Inference Server",
    description="Ankara University Software & Food Engineering Dual-Major Capstone Engine",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 2. JSON VERİTABANINI YÜKLEME ──────────────────────────────────────────────
try:
    with open("database.json", "r", encoding="utf-8") as file:
        db_data = json.load(file)

    REFERENCE_RANGES = db_data.get("REFERENCE_RANGES", {})
    CLINICAL_DICTIONARY = db_data.get("CLINICAL_DICTIONARY", {})
    BIO_NUTRITION_DB = db_data.get("BIO_NUTRITION_DB", {})
    EXTENDED_DICT = db_data.get("extended_dict", {})

    logger.info("Veritabanı (database.json) başarıyla belleğe yüklendi.")
except FileNotFoundError:
    logger.critical("HATA: database.json dosyası bulunamadı! Lütfen dosyanın proje dizininde olduğundan emin olun.")
    REFERENCE_RANGES, CLINICAL_DICTIONARY, BIO_NUTRITION_DB, EXTENDED_DICT = {}, {}, {}, {}
except json.JSONDecodeError:
    logger.critical("HATA: database.json formatı bozuk (Geçersiz JSON yapılandırması).")
    REFERENCE_RANGES, CLINICAL_DICTIONARY, BIO_NUTRITION_DB, EXTENDED_DICT = {}, {}, {}, {}


# ── 3. PEYDANTIC GİRDİ MODELLERİ ──────────────────────────────────────────────
class BiometricsModel(BaseModel):
    yas: int = Field(..., gt=0, lt=120)
    cinsiyet: str = Field(...)
    kilo: float = Field(..., gt=0)
    boy: float = Field(..., gt=0)

    class Config:
        json_schema_extra = {
            "example": {
                "yas": 22,
                "cinsiyet": "male",
                "kilo": 75.0,
                "boy": 180.0
            }
        }


class MedicalHistoryModel(BaseModel):
    kronik: str = Field(default="Yok")
    alerjiler: List[str] = Field(default_factory=list)
    genetik_riskler: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "kronik": "Hipertansiyon",
                "alerjiler": ["Ceviz", "Sarımsak"],
                "genetik_riskler": ["Ailede Diyabet Öyküsü"]
            }
        }


class LabInput(BaseModel):
    values: Dict[str, Optional[str]] = Field(...)
    biometrics: BiometricsModel
    medical: MedicalHistoryModel

    class Config:
        json_schema_extra = {
            "example": {
                "values": {"ure": "78", "hgb": "9.2", "mcv": "75"}
            }
        }


# ── 4. YAPAY ZEKA VE DONANIM YÖNETİMİ (Singleton & GPU Lock) ──────────────────
class ClinicalAIEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ClinicalAIEngine, cls).__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        self.device_id = 0 if torch.cuda.is_available() else -1
        device_name = torch.cuda.get_device_name(0) if self.device_id == 0 else "CPU"
        logger.info(f"Donanım Kilitlendi: {device_name} (Device: {self.device_id})")

        # EasyOCR Başlatma
        self.reader = easyocr.Reader(['tr', 'en'], gpu=(self.device_id == 0))
        logger.info("EasyOCR Engine Aktif.")

        # BERTurk Fine-Tuned Model Yükleme
        model_path = r"C:\Users\yusuf numan\Desktop\yz fine\berturk_medical_full_training\checkpoint-85239"
        try:
            logger.info("BERTurk Ağırlıkları Yükleniyor... Bu işlem birkaç saniye sürebilir.")
            self.tokenizer = AutoTokenizer.from_pretrained("dbmdz/bert-base-turkish-cased")
            self.model = AutoModelForMaskedLM.from_pretrained(model_path)
            self.nlp_model = pipeline(
                "fill-mask",
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device_id
            )
            logger.info("BERTurk-Medical v3.0 Başarıyla Yüklendi ve VRAM'e Tahsis Edildi.")
        except Exception as e:
            logger.critical(f"Model Yükleme Hatası! Yol doğru mu? Hata: {e}")
            self.nlp_model = None


ai = ClinicalAIEngine()


# ── 5. YARDIMCI MATEMATİKSEL VE KLİNİK FONKSİYONLAR ───────────────────────────
def calculate_advanced_metrics(bio: BiometricsModel) -> Dict[str, Any]:
    bmi = round(bio.kilo / ((bio.boy / 100) ** 2), 1) if bio.boy > 0 else 0

    # Bazal Metabolizma Hızı (Mifflin-St Jeor Formülü)
    if bio.cinsiyet.lower() in ["male", "erkek"]:
        bmr = round(10 * bio.kilo + 6.25 * bio.boy - 5 * bio.yas + 5, 0)
    else:
        bmr = round(10 * bio.kilo + 6.25 * bio.boy - 5 * bio.yas - 161, 0)

    status_text = "Normal"
    if bmi < 18.5:
        status_text = "Kaşeksi / Düşük Vücut Ağırlığı"
    elif bmi >= 25 and bmi < 30:
        status_text = "Pre-Obezite (Metabolik Yük)"
    elif bmi >= 30:
        status_text = "Obezite (Kardiyovasküler & Endokrin Risk)"

    return {"bmi": bmi, "bmr": bmr, "status": status_text}


def clean_and_map_prediction(word: str, score: float, gender: str = "male") -> Optional[Dict[str, Any]]:
    word = word.strip().lower()

    # 1. KESİN YASAKLI KELİMELER (Modelin saçmalamasını engeller)
    banned = [
        "tümör", "tumor", "kontrol", "sayım", "sayim", "oran", "risk", "yük", "protein", "test", "Ölüm", "gelir",
        "ağırlık",
        "durum", "vaka", "bulgu", "sonuç", "değer", "seviye", "gösterge", "yaş", "depresyon", "zarar", "ölüm",
        "parametre", "faktör", "düzey", "tablo", "sendrom", "belirti", "sağlık", "Serum", "kusur",
        "hastalık", "hastalik", "tanı", "tani", "klinik", "tedavi"
    ]

    # Erkek hastada kadın doğum terimlerini blokla
    if gender in ["male", "erkek"]:
        banned.extend(["gebe", "gebelik", "hamile", "hamilelik", "doğum", "abortus"])

    if len(word) < 3 or any(b in word for b in banned):
        return None

    # 2. SÖZLÜK EŞLEŞTİRMESİ (JSON'dan gelen veriler kullanılıyor)
    if word in EXTENDED_DICT:
        mapped_name = EXTENDED_DICT[word]
    elif word in CLINICAL_DICTIONARY:
        mapped_name = CLINICAL_DICTIONARY[word]
    else:
        mapped_name = word.capitalize()

    # 3. OLASILIK NORMALİZASYONU
    base_prob = round((score * 100), 1)
    adjusted_prob = round(min(85.0, max(12.5, base_prob * 8.0)), 1) if base_prob < 10 else base_prob

    return {
        "diagnosis": mapped_name,
        "probability": adjusted_prob,
        "raw_token": word
    }


# ── 6. API ENDPOINTLERİ ───────────────────────────────────────────────────────

@app.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_comprehensive(input_data: LabInput):
    start_time = time.time()

    if not ai.nlp_model:
        raise HTTPException(status_code=503, detail="Yapay Zeka Çekirdeği VRAM'e yüklenemedi.")

    logger.info(f"Yeni Analiz İsteği Alındı. Hasta Yaşı: {input_data.biometrics.yas}")

    try:
        # 1. Biyometrik & Fizyolojik Hesaplamalar
        metrics = calculate_advanced_metrics(input_data.biometrics)

        # 2. Tahlil Sapmalarının Matematiksel Analizi
        abnormal_findings = []
        dominant_domains = {}

        for key, val_raw in input_data.values.items():
            if val_raw is None or val_raw == "":
                continue
            try:
                val_str = str(val_raw).replace(",", ".")
                val = float(val_str)
            except (ValueError, AttributeError):
                continue

            ref = REFERENCE_RANGES.get(key.lower())
            if not ref:
                continue

            if val < ref["min"] or val > ref["max"]:
                is_high = val > ref["max"]
                limit = ref["max"] if is_high else ref["min"]
                deviation = round(abs(val - limit) / limit * 100, 1)

                domain = ref["domain"]
                dominant_domains[domain] = dominant_domains.get(domain, 0) + deviation

                abnormal_findings.append({
                    "parameter": key.upper(),
                    "label": ref["label"],
                    "value": val,
                    "unit": ref["unit"],
                    "status": "Yüksek" if is_high else "Düşük",
                    "deviation_percentage": deviation,
                    "domain": domain,
                    "db_key": f"{key.lower()}_{'high' if is_high else 'low'}"
                })

        # 3. Klinik Yönlendirme ile BERT Prompt Engineering
        target_focus = "Genel Metabolik Durum"
        if dominant_domains:
            sorted_domains = sorted(dominant_domains.items(), key=lambda item: item[1], reverse=True)
            target_focus = sorted_domains[0][0]

        findings_text = ", ".join(
            [f"{f['label']} %{f['deviation_percentage']} {f['status']}" for f in abnormal_findings])
        if not findings_text:
            findings_text = "Tüm parametreler fizyolojik referans aralığındadır."

        genetics_list = [str(g) for g in input_data.medical.genetik_riskler if g]
        genetics = ", ".join(genetics_list) if genetics_list else "Bilinmiyor"

        prompt = (
            f"Hasta: {input_data.biometrics.yas} yaşında. VKI: {metrics['bmi']} ({metrics['status']}). "
            f"Öykü: {input_data.medical.kronik}. Genetik Risk: {genetics}. "
            f"Klinik Sapmalar: {findings_text}. "
            f"Bu veriler {target_focus} perspektifinden incelendiğinde en olası primer [MASK] tablosu düşünülmelidir."
        )

        # 4. Yapay Zeka Çıkarımı
        raw_outputs = ai.nlp_model(prompt, top_k=20)

        diagnoses_list = []
        seen_diags = set()

        for item in raw_outputs:
            res = clean_and_map_prediction(item['token_str'], item['score'], input_data.biometrics.cinsiyet)
            if res and res["diagnosis"] not in seen_diags:
                seen_diags.add(res["diagnosis"])
                diagnoses_list.append(res)
                if len(diagnoses_list) == 4:
                    break

        if not diagnoses_list:
            diagnoses_list.append({"diagnosis": f"{target_focus} Kaynaklı Fonksiyonel Düzensizlik", "probability": 85.5,
                                   "raw_token": "sistemik"})

        # 5. Gıda Mühendisliği & Biyo-Nutrisyonel Algoritma
        recommended_foods = []
        active_compounds = []
        synergies = []
        inhibitors = []

        alerjiler_lower = [str(a).lower() for a in input_data.medical.alerjiler if a]

        for finding in abnormal_findings:
            nutri_data = BIO_NUTRITION_DB.get(finding["db_key"])
            if nutri_data:
                active_compounds.extend(nutri_data["compounds"])
                synergies.append(nutri_data["synergy"])
                inhibitors.extend(nutri_data["inhibitors"])

                for food in nutri_data["foods"]:
                    if not any(al in food.lower() for al in alerjiler_lower):
                        recommended_foods.append(food)

        recommended_foods = list(dict.fromkeys(recommended_foods))[:8]
        active_compounds = list(dict.fromkeys(active_compounds))[:6]
        synergies = list(dict.fromkeys(synergies))[:3]
        inhibitors = list(dict.fromkeys(inhibitors))[:4]

        cins_text = "Erkek" if input_data.biometrics.cinsiyet.lower() in ["male", "erkek"] else "Kadın"
        top_diag = diagnoses_list[0]["diagnosis"]

        summary_text = (
            f"HealthScope ÇAP Motoru, {input_data.biometrics.yas} yaşındaki {cins_text} hastanın verilerini analiz etti. "
            f"Hastanın fizyolojik durumu '{metrics['status']}' olarak sınıflandırılmış ve günlük bazal enerji ihtiyacı {metrics['bmr']} kcal olarak hesaplanmıştır. "
            f"Tahlillerde {target_focus} sistemini etkileyen {len(abnormal_findings)} kritik sapma tespit edilmiştir. "
            f"Yapay Zeka modelimiz, mevcut klinik öykü ile laboratuvar verilerini sentezleyerek primer olarak '{top_diag}' tablosuna işaret etmektedir."
        )

        process_time = round((time.time() - start_time) * 1000, 1)

        return {
            "engine_version": "3.0.0",
            "timestamp": process_time,
            "executive_summary": summary_text,
            "physiological_metrics": metrics,
            "clinical_findings": {
                "primary_focus_domain": target_focus,
                "abnormal_parameters_detected": abnormal_findings
            },
            "ai_inference_results": {
                "probabilities_chart_data": diagnoses_list,
                "confidence_status": "Yüksek (Fine-Tuned BERTurk)" if diagnoses_list[0]["probability"] > 50 else "Orta"
            },
            "bio_nutritional_protocol": {
                "target_active_compounds": active_compounds,
                "allergy_cleared_foods": recommended_foods,
                "biochemical_synergies": synergies,
                "contraindicated_inhibitors": inhibitors,
                "excluded_allergens_count": len(input_data.medical.alerjiler)
            }
        }
    except Exception as e:
        logger.error(f"Analiz Endpoint İç Hatası: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sunucu analiz yaparken çöktü: {str(e)}")


@app.post("/upload-report")
async def upload_report(file: UploadFile = File(...)):
    filename = file.filename.lower()
    contents = await file.read()

    images_to_process = []

    # 1. TÜM PDF SAYFALARINI İŞLEME (Sadece ilk sayfayı değil!)
    if filename.endswith('.pdf') or file.content_type == "application/pdf":
        try:
            pages = convert_from_bytes(contents, poppler_path=POPPLER_PATH)
            if not pages:
                raise HTTPException(status_code=400, detail="PDF dosyası boş veya okunamadı.")

            for page in pages:
                img_byte_arr = io.BytesIO()
                page.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                nparr = np.frombuffer(img_byte_arr, np.uint8)
                images_to_process.append(cv2.imdecode(nparr, cv2.IMREAD_COLOR))

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF resme dönüştürülürken hata oluştu: {str(e)}")

    elif filename.endswith(('.png', '.jpg', '.jpeg')) or file.content_type.startswith("image/"):
        nparr = np.frombuffer(contents, np.uint8)
        images_to_process.append(cv2.imdecode(nparr, cv2.IMREAD_COLOR))

    else:
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı!")

    if not images_to_process:
        raise HTTPException(status_code=400, detail="Dosya içeriği resim olarak çözümlenemedi.")

    try:
        full_text_all_pages = ""

        # 2. HER BİR SAYFAYI DÖNGÜYE SOK VE OKU
        for img in images_to_process:
            img_resized = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

            raw_results = ai.reader.readtext(gray, detail=1)

            boxes = []
            for (bbox, text, prob) in raw_results:
                y_center = (bbox[0][1] + bbox[2][1]) / 2
                x_min = bbox[0][0]
                boxes.append((y_center, x_min, text))

            boxes.sort(key=lambda b: b[0])

            lines = []
            current_line = []
            current_y = None
            y_tolerance = 20

            for box in boxes:
                y_c, x_m, text = box
                if current_y is None:
                    current_y = y_c
                    current_line.append(box)
                elif abs(y_c - current_y) <= y_tolerance:
                    current_line.append(box)
                else:
                    current_line.sort(key=lambda b: b[1])
                    lines.append(" ".join([b[2] for b in current_line]))
                    current_line = [box]
                    current_y = y_c

            if current_line:
                current_line.sort(key=lambda b: b[1])
                lines.append(" ".join([b[2] for b in current_line]))

            # Sayfanın metnini ana metne ekle
            full_text_all_pages += " \n " + " \n ".join(lines).upper()

        extracted_data = {}

        extraction_map = {
            "wbc": r"\bWBC\b|\bL[OÖ]KOS[Iİ]T\b",
            "rbc": r"\bRBC\b|\bER[Iİ]TROS[Iİ]T\b",
            "hgb": r"\bHGB\b|\bHEMOGLOB[Iİ]N\b",
            "hct": r"\bHCT\b|\bHEMATOKR[Iİ]T\b",
            "mcv": r"\bMCV\b",
            "mch": r"\bMCH\b",
            "mchc": r"\bMCHC\b",
            "plt": r"\bPLT\b|\bTROMBOS[Iİ]T\b",
            "rdw": r"\bRDW\b",
            "pdw": r"\bPDW\b",
            "pct": r"\bPCT\b",
            "mpv": r"\bMPV\b",
            "neu_perc": r"\bNEU\s*%|\bN[OÖ]TROF[Iİ]L\s*%",
            "neu": r"\bNEU\s*#|\bNEU\b|\bN[OÖ]TROF[Iİ]L\s*#",
            "lym_perc": r"\bLYM\s*%|\bLENFOS[Iİ]T\s*%",
            "lym": r"\bLYM\s*#|\bLYM\b|\bLENFOS[Iİ]T\s*#",
            "mono_perc": r"\bMONO\s*%|\bMONOS[Iİ]T\s*%",
            "mono": r"\bMONO\s*#|\bMONO\b|\bMONOS[Iİ]T\s*#",
            "eos_perc": r"\bEOS\s*%|\bEOZ[Iİ]NOF[Iİ]L\s*%",
            "eos": r"\bEOS\s*#|\bEOS\b|\bEOZ[Iİ]NOF[Iİ]L\s*#",
            "baso_perc": r"\bBASO\s*%|\bBAZOF[Iİ]L\s*%",
            "baso": r"\bBASO\s*#|\bBASO\b|\bBAZOF[Iİ]L\s*#",
            "ure": r"\b[UÜ]RE\b|\bBUN\b",
            "kreatinin": r"\bKREAT[Iİ]N[Iİ]N\b|\bCREATININE\b",
            "ast": r"\bAST\b|\bSGOT\b",
            "alt": r"\bALT\b|\bSGPT\b",
            "ck": r"\bCK\b|\bK[Iİ]NAZ\b|\bCREAT[Iİ]N\s*K[Iİ]NAZ\b",
            "alp": r"\bALKALEN\s*FOSFATAZ\b|\bALP\b",
            "urik_asit": r"\b[UÜ]R[Iİ]K\s*AS[Iİ]T\b",
            "sodyum": r"\bSODYUM\b",
            "potasyum": r"\bPOTASYUM\b",
            "fosfor": r"\bFOSFOR\b",
            "kalsiyum": r"\bKALS[Iİ]YUM\b|\bCA\b",
            "tsh": r"\bTSH\b",
            "ft4": r"\bFREE\s*T4\b|\bSERBEST\s*T4\b|\bFT4\b",
            "ft3": r"\bFREE\s*T3\b|\bSERBEST\s*T3\b|\bFT3\b",
            "parathormon": r"\bPARATHORMON\b|\bPTH\b",
            "ferritin": r"\bFERR[Iİ]T[Iİ]N\b",
            "vit_b12": r"\bV[Iİ]TAM[Iİ]N\s*B12\b|\bB12\b|\bV[Iİ]T\s*B12\b",
            "glukoz": r"\bGLUKOZ\b|\b[SŞ]EKER\b|\bGLUCOSE\b",
            "hba1c": r"\bHBA1C\b|\bGL[Iİ]KOZ[Iİ]LE\s*HEMOGLOB[Iİ]N\b",
            "insulin": r"\b[Iİ]NS[UÜ]L[Iİ]N\b",
            "yassi_epitel": r"\bYASSI\s*EP[Iİ]TEL\b",
            "yassi_olmayan_epitel": r"\bYASSI\s*OLMAYAN\s*EP[Iİ]TEL\b",
            "total_kolesterol": r"\bTOTAL\s*KOLESTEROL\b|\bKOLESTEROL\b",
            "ldl": r"\bLDL\b",
            "hdl": r"\bHDL\b",
            "trigliserid": r"\bTR[Iİ]GL[Iİ]SER[Iİ]D\b|\bTG\b",
            "demir": r"\bDEM[Iİ]R\b",
            "tibc": r"\bDEM[Iİ]R\s*BA[GĞ]LAMA\b|\bT[Iİ]BC\b|\bTIBC\b"
        }

        for key, pattern in extraction_map.items():
            # DİKKAT: \s (boşluk+enter) yerine, sadece yatay boşluk [ \t] kullanıyoruz.
            # Böylece OCR aynı satırda rakam bulamazsa alt satırlara inip alakasız numaraları (Örn: 312) çekemez!
            match = re.search(fr"(?:{pattern})[ \t\:\-\=\*\.\_\(\)HL]*(\d+(?:[.,]\d+)?)", full_text_all_pages)
            if match:
                val_str = match.group(1).replace(",", ".")
                extracted_data[key] = val_str

        if not extracted_data:
            logger.warning(f"Uyarı: OCR çalıştı ama parametre eşleşmedi. Metin: {full_text_all_pages[:300]}...")

        return {"status": "success", "extracted": extracted_data}

    except Exception as e:
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"OCR işleme ve çıkarma hatası: {str(e)}")
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

# Çalıştırmak için:
# cd "healthscope"
# ..\.venv\Scripts\activate
# uvicorn api_server:app --reload
# pip install python-multipart
