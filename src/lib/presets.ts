/**
 * Klinik vaka havuzu — demo ve test için hazır hasta profilleri.
 *
 * Anahtarlar `database.json` içindeki PARAMETER_CATALOG kimlikleriyle birebir
 * aynıdır; `npm run build` sırasında `validatePresets` bunu doğrular.
 */
import presetData from "../../presets.json";
import { PARAMETER_BY_ID } from "./catalog";

export interface PresetCase {
  name: string;
  description: string;
  biometrics: { boy: string; kilo: string; yas: string; cinsiyet: "male" | "female" };
  medical: { kronik: string; genetik: string; alerjiler: string[] };
  labValues: Record<string, string>;
  /**
   * `scripts/evaluate.py` için beklenen sonuç. Arayüz bunu yalnızca filtreleme
   * ve özet göstermek için kullanır; vakanın kendisini etkilemez.
   */
  expected?: {
    primary_domain: string;
    must_flag: string[];
    key_protocols: string[];
    clinical_topic: string[];
  };
}

/**
 * Vaka verisi `presets.json` dosyasindan gelir; ayni dosyayi
 * `scripts/evaluate.py` degerlendirme araci da okur. Boylece arayuzdeki
 * demo vakalari ile dogruluk olcumu birebir ayni veriyi kullanir.
 */
export const PRESET_CASES: PresetCase[] = presetData as PresetCase[];

/** Vaka havuzu filtresi için, vakalarda gerçekten geçen klinik alanlar. */
export const PRESET_DOMAINS: string[] = Array.from(
  new Set(PRESET_CASES.map((preset) => preset.expected?.primary_domain).filter(Boolean) as string[]),
).sort();


/**
 * Preset anahtarlarının katalogda karşılığı olduğunu doğrular.
 * Geliştirme modunda konsola uyarı basar — sessiz veri kaybını önler.
 */
export function validatePresets(): string[] {
  const problems: string[] = [];
  for (const preset of PRESET_CASES) {
    for (const key of Object.keys(preset.labValues)) {
      if (!PARAMETER_BY_ID[key]) {
        problems.push(`"${preset.name}" içindeki "${key}" katalogda yok`);
      }
    }
  }
  return problems;
}
