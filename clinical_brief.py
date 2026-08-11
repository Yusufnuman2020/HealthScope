# -*- coding: utf-8 -*-
"""Deterministik bulgulardan klinik özet (brief) üretir.

Bu modül hibrit mimarinin kalbidir: kural motorunun çıkardığı öznitelikleri,
bir dil modelinin üzerinde akıl yürütebileceği yapılandırılmış bir metne
çevirir.

Neden gerekli — ölçülmüş gerekçe:
    Eski prompt modele ham sapma listesi veriyordu:
        "AST %951 Yüksek, CRP %250 Yüksek, ALT %228 Yüksek"
    Model bu girdiden klinik örüntü çıkaramadı; 118 vakada isabet %50'ydi ve
    ağır karaciğer / böbrek / anemi vakalarına aynı cevabı verdi.

    Hibrit prompt ise ön işlenmiş klinik öznitelik verir:
        "De Ritis oranı 2.01 (>2, ancak GGT normal -> kas kaynağı olası)"
    Yani kural motoru klinik akıl yürütmenin yarısını zaten yapmış olur.

Modül bilerek dil modelinden BAĞIMSIZDIR: yalnızca metin üretir. Hangi modelin
kullanılacağı `llm.py` sorunudur. Bu sayede özet, model olmadan da test
edilebilir ve `/analyze` yanıtında şeffaflık için ham hâliyle döndürülebilir.
"""
from __future__ import annotations

from typing import Any

#: Özete alınacak azami sapma sayısı — en yüksek sapmalar önce gelir.
MAX_FINDINGS = 12
#: Özete alınacak azami indeks sayısı.
MAX_INDICES = 8


def _format_finding(finding: dict[str, Any]) -> str:
    return (
        f"- {finding['label']}: {finding['value']} {finding['unit']} "
        f"(referans {finding['reference']}) → %{finding['deviation_percentage']} "
        f"{finding['status'].lower()}"
    )


def _format_index(index: dict[str, Any]) -> str:
    line = f"- {index['label']} = {index['value']}{index['unit']}: {index['interpretation']}"
    if index.get("overridden_interpretation"):
        # Bağlam düzelticisi devreye girdiyse bunu modele AÇIKÇA söyle:
        # "şu yorum elendi" bilgisi, modelin yanlış hipoteze sapmasını önler.
        line += f" (bağlam olmadan şöyle yorumlanırdı: {index['overridden_interpretation']})"
    return line


def build(
    *,
    biometrics: dict[str, Any],
    metrics: dict[str, Any],
    history: str,
    genetics: str,
    allergies: list[str],
    abnormal_findings: list[dict[str, Any]],
    clinical_indices: list[dict[str, Any]],
    suggested_tests: list[dict[str, str]],
    primary_domain: str,
    evaluated_count: int,
) -> str:
    """Dil modeline verilecek yapılandırılmış klinik özeti üretir."""
    sex = "erkek" if str(biometrics.get("cinsiyet", "")).lower() in ("male", "erkek") else "kadın"

    sections: list[str] = []

    sections.append(
        "HASTA\n"
        f"- {biometrics['yas']} yaşında {sex}\n"
        f"- VKİ {metrics['bmi']} ({metrics['status']}), bazal metabolizma {metrics['bmr']} kcal\n"
        f"- Öykü: {history}\n"
        f"- Genetik risk: {genetics}\n"
        f"- Alerji: {', '.join(allergies) if allergies else 'bilinen alerji yok'}"
    )

    if abnormal_findings:
        rows = "\n".join(_format_finding(f) for f in abnormal_findings[:MAX_FINDINGS])
        extra = (
            f"\n- (ve {len(abnormal_findings) - MAX_FINDINGS} parametre daha)"
            if len(abnormal_findings) > MAX_FINDINGS
            else ""
        )
        sections.append(
            f"REFERANS DIŞI PARAMETRELER ({len(abnormal_findings)} / {evaluated_count})\n{rows}{extra}"
        )
    else:
        sections.append(
            f"REFERANS DIŞI PARAMETRELER\n- Yok; girilen {evaluated_count} parametrenin tamamı "
            "referans aralığında."
        )

    if clinical_indices:
        flagged = [i for i in clinical_indices if i["level"] != "normal"]
        shown = (flagged or clinical_indices)[:MAX_INDICES]
        rows = "\n".join(_format_index(i) for i in shown)
        sections.append(
            "KLİNİK İNDEKSLER (literatür formülleriyle hesaplandı, güvenilir)\n" + rows
        )

    sections.append(f"BASKIN SİSTEM (sapma yüküne göre)\n- {primary_domain}")

    if suggested_tests:
        rows = "\n".join(f"- {t['label']} ({t['reason']} bulgusunu netleştirir)" for t in suggested_tests)
        sections.append("ÖRÜNTÜYÜ NETLEŞTİRECEK EKSİK TESTLER\n" + rows)

    return "\n\n".join(sections)


#: Dil modeline verilecek sistem talimatı.
#:
#: Bu metin ölçümle seçildi: 2 prompt varyantı × 4 üretim ayarı, 3 klinik vaka
#: üzerinde karşılaştırıldı. Bu sürüm (sıkı kurallar + açık şablon) tekrar
#: oranını %5.6'dan %2.1'e düşürdü ve zorunlu feragat cümlesini 1/3'ten 3/3'e
#: çıkardı. `no_repeat_ngram_size` denendi ve TERK EDİLDİ: tekrarı sıfırlarken
#: her çıktıda bulunması gereken feragat kalıbını da engelliyordu.
SYSTEM_PROMPT = """Sen bir klinik karar destek asistanısın. Hastanın laboratuvar bulguları ve hesaplanmış klinik indeksleri sana yapılandırılmış biçimde veriliyor.

KURALLAR
- Yalnızca verilen bulguları kullan. Yeni sayı, değer, test adı veya tarih uydurma.
- Klinik indekslerin yorumları güvenilirdir; onlarla çelişme. Bir indeksin bağlam düzeltmesi varsa (ör. "GGT normal olduğu için alkol olası değil") o düzeltmeye uy.
- İndeksleri birbirine karıştırma. De Ritis ve FIB-4 karaciğer indeksleridir; NLR ve PLR inflamasyon indeksleridir.
- "Kas kaynaklı AST artışı" ile "karaciğer hastalığı" aynı şey değildir; bulgu neyse onu yaz.
- İlaç, doz veya tedavi önerme. Yalnızca hangi tetkikin ayırt edici olduğunu söyle.
- Kesin teşhis koyma. "ön planda düşünülmelidir", "ayırıcı tanıda yer almalıdır" gibi ifadeler kullan.
- Aynı cümleyi veya ifadeyi tekrarlama. Her cümle yeni bilgi vermeli.
- Toplam 120 kelimeyi aşma. Düzgün Türkçe yaz.

ÇIKTI BİÇİMİ (bu başlıkları aynen kullan)
Değerlendirme: <en fazla 2 cümle, genel tablo>
Olası örüntüler:
1. <örüntü adı> — <tek cümle gerekçe>
2. <örüntü adı> — <tek cümle gerekçe>
Öneri: <hangi tetkik ayırt edicidir>
Not: Bu bir teşhis değildir, hekim değerlendirmesi gereklidir."""


# ── Sohbet katmanı ────────────────────────────────────────────────────────
#: Sohbet, tek seferlik üretimden çok daha geniş bir risk yüzeyi açar: kullanıcı
#: her şeyi sorabilir. Bu prompt kapsamı hastanın KENDİ bulgularıyla sınırlar ve
#: ilaç/doz/prognoz sorularını açıkça reddettirir.
CHAT_SYSTEM_PROMPT = """Sen bir klinik karar destek asistanısın. Kullanıcı, kendi laboratuvar sonuçları hakkında soru soruyor. Hastanın bulguları ve hesaplanmış klinik indeksleri sana aşağıda veriliyor.

KAPSAM
- Yalnızca aşağıdaki bulgular hakkında konuş. Bu bulgularda olmayan bir değer, test veya tarih uydurma.
- Soru bu bulgularla ilgili değilse (genel sağlık tavsiyesi, başka bir hastalık, kişisel konular) kibarca kapsamın dışında olduğunu söyle ve hekime yönlendir.
- Cevabı bulgularda yoksa "bu panelde bu bilgi yok" de. Tahmin yürütme.

YASAKLAR
- İlaç adı, doz veya tedavi önerme. Sadece hangi tetkikin ayırt edici olduğunu söyleyebilirsin.
- Kesin teşhis koyma, prognoz verme, "iyileşirsin" / "ciddi değil" gibi güvence verme.
- Klinik indekslerin yorumlarıyla çelişme. Bir indeksin bağlam düzeltmesi varsa ona uy.

ÜSLUP
- Türkçe, sade ve anlaşılır. Hastaya açıklıyorsun, hekime rapor yazmıyorsun.
- En fazla 4 cümle. Aynı şeyi tekrarlama.
- Endişe yaratacak dramatik ifadelerden kaçın; nesnel ol.
- Gerektiğinde "bunu hekiminizle değerlendirmelisiniz" ile bitir."""

#: Arayüzde gösterilen hazır sorular. Serbest metin yerine yönlendirme, hem
#: cevaplanabilir soruları öne çıkarır hem de kapsam dışı soru olasılığını azaltır.
SUGGESTED_QUESTIONS: tuple[str, ...] = (
    "Bu sonuçlar genel olarak ne anlama geliyor?",
    "En dikkat çekici bulgu hangisi?",
    "Önerilen tetkik neden gerekli?",
    "Hangi besinlere dikkat etmeliyim?",
    "Bu değerler neden yükselmiş olabilir?",
)


def build_chat_context(brief: str) -> str:
    """Sohbetin her turunda modele yeniden verilecek bağlam."""
    return f"HASTANIN BULGULARI\n\n{brief}"
