/**
 * Klinik alan → organ eşlemesi ve şiddet hesabı.
 *
 * Bu katman GÖRSELLEŞTİRİCİDEN BAĞIMSIZDIR. Şu an SVG şeması kullanılıyor;
 * ileride three.js ile 3B modele geçilirse yalnızca çizim katmanı değişir,
 * buradaki eşleme ve şiddet mantığı aynı kalır.
 */
import type { AbnormalParameter } from "@/lib/api";

export type OrganId =
  | "beyin"
  | "tiroid"
  | "kalp"
  | "akciger"
  | "karaciger"
  | "safra"
  | "pankreas"
  | "dalak"
  | "mide"
  | "bobrek"
  | "kas"
  | "damar"
  | "kemik";

export interface Organ {
  id: OrganId;
  label: string;
  /** Bu organı etkileyen klinik alanlar. */
  domains: string[];
}

/**
 * Hangi organ hangi klinik alandan etkilenir.
 * Bir alan birden çok organı ilgilendirebilir (elektrolit → böbrek + kalp).
 */
export const ORGANS: Organ[] = [
  { id: "tiroid", label: "Tiroid", domains: ["Endokrinoloji"] },
  { id: "kalp", label: "Kalp", domains: ["Kardiyovasküler", "Elektrolit"] },
  { id: "damar", label: "Damar yatağı", domains: ["Kardiyovasküler", "Hematoloji"] },
  { id: "karaciger", label: "Karaciğer", domains: ["Hepatoloji"] },
  { id: "safra", label: "Safra kesesi", domains: ["Hepatoloji", "Gastroenteroloji"] },
  { id: "pankreas", label: "Pankreas", domains: ["Endokrinoloji", "Gastroenteroloji"] },
  { id: "mide", label: "Mide / bağırsak", domains: ["Gastroenteroloji"] },
  { id: "dalak", label: "Dalak / lenf", domains: ["İmmünoloji"] },
  { id: "bobrek", label: "Böbrekler", domains: ["Nefroloji", "Elektrolit"] },
  { id: "kemik", label: "Kemik iliği", domains: ["Hematoloji"] },
  { id: "kas", label: "İskelet kası", domains: ["Kas-İskelet"] },
  { id: "beyin", label: "Merkezi sinir sistemi", domains: ["Elektrolit"] },
  { id: "akciger", label: "Akciğer", domains: [] },
];

/**
 * Parametre düzeyinde organ eşlemesi — alan eşlemesini EZER.
 *
 * Alan bazlı eşleme tek başına yanıltıcı olabiliyor: "Endokrinoloji" hem
 * tiroidi hem pankreası kapsar, dolayısıyla yüksek insülin tiroidi de
 * boyuyordu. Aşağıdaki parametreler doğrudan ilgili organa bağlanır.
 */
const PARAMETER_ORGANS: Record<string, OrganId[]> = {
  // Pankreas — glukoz metabolizması ve ekzokrin enzimler
  insulin: ["pankreas"],
  glukoz: ["pankreas"],
  hba1c: ["pankreas"],
  amilaz: ["pankreas"],
  lipaz: ["pankreas"],

  // Tiroid ekseni
  tsh: ["tiroid"],
  ft3: ["tiroid"],
  ft4: ["tiroid"],
  parathormon: ["tiroid", "kemik"],

  // Kemik–mineral ekseni
  kalsiyum: ["kemik", "bobrek"],
  fosfor: ["kemik", "bobrek"],
  vit_d: ["kemik"],
  alp: ["karaciger", "kemik"],

  // Elektrolit — hedef organlar
  sodyum: ["bobrek", "beyin"],
  potasyum: ["bobrek", "kalp"],

  // Safra yolu
  total_bilirubin: ["karaciger", "safra"],
  direkt_bilirubin: ["karaciger", "safra"],
  ggt: ["karaciger", "safra"],

  // Kas
  ck: ["kas"],

  // Eritrosit serisi — kemik iliği ve dolaşım
  hgb: ["kemik", "damar"],
  hct: ["kemik", "damar"],
  rbc: ["kemik", "damar"],
  plt: ["kemik", "damar"],
  ferritin: ["kemik", "karaciger"],
  demir: ["kemik", "damar"],

  // Lipid — damar duvarı
  hdl: ["damar"],
  ldl: ["damar"],
  total_kolesterol: ["damar"],
  trigliserid: ["damar", "karaciger"],
};

export type Severity = "normal" | "hafif" | "orta" | "agir";

export interface OrganState {
  organ: Organ;
  severity: Severity;
  /** 0-1 arası normalize yük; renk yoğunluğu için. */
  intensity: number;
  /** Bu organa katkı veren bulgular. */
  findings: AbnormalParameter[];
}

/** Şiddet eşikleri — `severity` alanı referans aralığı genişliğinin katıdır. */
const THRESHOLDS: Array<{ min: number; level: Severity }> = [
  { min: 1.5, level: "agir" },
  { min: 0.5, level: "orta" },
  { min: 0.0, level: "hafif" },
];

function classify(total: number): Severity {
  for (const { min, level } of THRESHOLDS) {
    if (total >= min) return level;
  }
  return "normal";
}

/**
 * Bulguları organlara dağıtır.
 *
 * Bir bulgu, alanına karşılık gelen TÜM organlara katkı verir; örneğin
 * potasyum bozukluğu hem böbreği hem kalbi ilgilendirir.
 */
export function mapFindingsToOrgans(findings: AbnormalParameter[]): OrganState[] {
  const buckets = new Map<OrganId, { total: number; items: AbnormalParameter[] }>();

  for (const finding of findings) {
    const severity = typeof finding.severity === "number" ? finding.severity : 0;
    // Parametreye özel eşleme varsa onu kullan; yoksa alanına düş.
    const override = PARAMETER_ORGANS[finding.parameter.toLowerCase()];
    const targets = override ?? ORGANS.filter((o) => o.domains.includes(finding.domain)).map((o) => o.id);

    for (const organ of ORGANS) {
      if (!targets.includes(organ.id)) continue;
      const bucket = buckets.get(organ.id) ?? { total: 0, items: [] };
      // Karekök sıkıştırma: tek bir aşırı değer organı tamamen kırmızıya
      // boyamasın (backend'deki alan puanlamasıyla aynı mantık).
      bucket.total += Math.sqrt(Math.max(severity, 0));
      bucket.items.push(finding);
      buckets.set(organ.id, bucket);
    }
  }

  const maxTotal = Math.max(...[...buckets.values()].map((b) => b.total), 1);

  return ORGANS.map((organ) => {
    const bucket = buckets.get(organ.id);
    const total = bucket?.total ?? 0;
    return {
      organ,
      severity: total > 0 ? classify(total) : "normal",
      intensity: total > 0 ? Math.min(total / maxTotal, 1) : 0,
      findings: bucket?.items ?? [],
    };
  });
}

/**
 * Şiddet → organ dolgusu.
 *
 * Tek renk skalası kasıtlı: şema klinik bir diyagram, gerçekçi bir illüstrasyon
 * değil. Organın doğal rengi bilgi taşımaz, şiddeti taşır — bu yüzden renk
 * yalnızca şiddete ayrıldı. Anatomik doğruluk biçimden okunur, renkten değil.
 */
export const SEVERITY_FILL: Record<Severity, string> = {
  normal: "var(--organ-normal)",
  hafif: "var(--organ-mild)",
  orta: "var(--organ-moderate)",
  agir: "var(--organ-severe)",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  normal: "Bulgu yok",
  hafif: "Hafif etkilenme",
  orta: "Orta etkilenme",
  agir: "Belirgin etkilenme",
};
