/**
 * Parametre kataloğu — frontend tarafı.
 *
 * Backend ile TAM AYNI `database.json` dosyasını okur. Form alanları,
 * referans aralıkları ve besin protokolleri artık elle senkronize edilmez;
 * bu yüzden "formda alan var ama backend tanımıyor" hatası imkânsızdır.
 * JSON build sırasında bundle'a gömülür, çalışma zamanında fetch gerekmez.
 */
import database from "../../database.json";

export type Accent = "red" | "emerald" | "purple" | "rose" | "amber" | "cyan";

export interface ParameterGroup {
  id: string;
  label: string;
  accent: Accent;
  icon: string;
}

export interface Parameter {
  id: string;
  label: string;
  short: string;
  unit: string;
  domain: string;
  group: string;
  order: number;
  refMin: number;
  refMax: number;
  /** Arayüzde gösterilen referans metni, ör. "70-99". */
  refText: string;
  /**
   * Cinsiyete özgü aralıklar. Kreatinin, hemoglobin, ferritin gibi
   * parametrelerde fizyolojik fark gerçektir; tek aralık yanlış alarm üretir.
   */
  refMale?: { min: number; max: number };
  refFemale?: { min: number; max: number };
  /** Sapma yönüne göre bağlı besin protokolü anahtarları. */
  nutrition: { high?: string; low?: string };
}

export interface NutritionProtocol {
  key: string;
  compounds: string[];
  foods: string[];
  synergy: string;
  inhibitors: string[];
}

interface RawParameter {
  label: string;
  short: string;
  unit: string;
  domain: string;
  group: string;
  order: number;
  ref: { min: number; max: number };
  ref_male?: { min: number; max: number };
  ref_female?: { min: number; max: number };
  ocr: string[];
  nutrition: Record<string, string>;
}

interface RawGroup {
  label: string;
  accent: string;
  icon: string;
}

interface RawProtocol {
  compounds: string[];
  foods: string[];
  synergy: string;
  inhibitors: string[];
}

const rawGroups = database.PARAMETER_GROUPS as Record<string, RawGroup>;
const rawParameters = database.PARAMETER_CATALOG as Record<string, RawParameter>;
const rawProtocols = database.BIO_NUTRITION_DB as Record<string, RawProtocol>;

/** Referans aralığını insan okunur hâle getirir (gereksiz ondalıkları atar). */
const formatRange = (min: number, max: number) => `${min}-${max}`;

export const PARAMETERS: Parameter[] = Object.entries(rawParameters)
  .map(([id, meta]) => ({
    id,
    label: meta.label,
    short: meta.short,
    unit: meta.unit,
    domain: meta.domain,
    group: meta.group,
    order: meta.order,
    refMin: meta.ref.min,
    refMax: meta.ref.max,
    refText: formatRange(meta.ref.min, meta.ref.max),
    refMale: meta.ref_male,
    refFemale: meta.ref_female,
    nutrition: meta.nutrition as Parameter["nutrition"],
  }))
  .sort((a, b) => a.order - b.order);

export type Sex = "male" | "female" | string;

/** Backend ile aynı mantık: cinsiyete özgü aralık varsa onu, yoksa geneli döner. */
export function rangeFor(parameter: Parameter, sex?: Sex): { min: number; max: number } {
  if (sex) {
    const isMale = ["male", "erkek", "m", "e"].includes(String(sex).trim().toLowerCase());
    const specific = isMale ? parameter.refMale : parameter.refFemale;
    if (specific) return specific;
  }
  return { min: parameter.refMin, max: parameter.refMax };
}

export function referenceText(parameter: Parameter, sex?: Sex): string {
  const { min, max } = rangeFor(parameter, sex);
  return formatRange(min, max);
}

/** Bir parametrenin referans aralığı cinsiyete göre değişiyor mu? */
export function isSexSpecific(parameter: Parameter): boolean {
  return Boolean(parameter.refMale || parameter.refFemale);
}

export const PARAMETER_BY_ID: Record<string, Parameter> = Object.fromEntries(
  PARAMETERS.map((parameter) => [parameter.id, parameter]),
);

export const GROUPS: ParameterGroup[] = Object.entries(rawGroups).map(([id, meta]) => ({
  id,
  label: meta.label,
  accent: meta.accent as Accent,
  icon: meta.icon,
}));

/** Her grup ve o gruba ait parametreler — form bunun üzerinden render edilir. */
export const GROUPED_PARAMETERS: Array<ParameterGroup & { parameters: Parameter[] }> = GROUPS.map(
  (group) => ({
    ...group,
    parameters: PARAMETERS.filter((parameter) => parameter.group === group.id),
  }),
).filter((group) => group.parameters.length > 0);

export const PROTOCOLS: NutritionProtocol[] = Object.entries(rawProtocols).map(([key, value]) => ({
  key,
  ...value,
}));

export const PROTOCOL_BY_KEY: Record<string, NutritionProtocol> = Object.fromEntries(
  PROTOCOLS.map((protocol) => [protocol.key, protocol]),
);

/** Bir protokolü tetikleyen parametreler — gıda veritabanı sayfası bunu gösterir. */
export function parametersForProtocol(protocolKey: string): Array<{ parameter: Parameter; direction: "Yüksek" | "Düşük" }> {
  const matches: Array<{ parameter: Parameter; direction: "Yüksek" | "Düşük" }> = [];
  for (const parameter of PARAMETERS) {
    if (parameter.nutrition.high === protocolKey) matches.push({ parameter, direction: "Yüksek" });
    if (parameter.nutrition.low === protocolKey) matches.push({ parameter, direction: "Düşük" });
  }
  return matches;
}

export const CATALOG_STATS = {
  parameterCount: PARAMETERS.length,
  groupCount: GROUPS.length,
  indexCount: Object.keys((database as { CLINICAL_INDICES?: object }).CLINICAL_INDICES ?? {}).length,
  protocolCount: PROTOCOLS.length,
  foodCount: new Set(PROTOCOLS.flatMap((protocol) => protocol.foods)).size,
  compoundCount: new Set(PROTOCOLS.flatMap((protocol) => protocol.compounds)).size,
};

/**
 * Tailwind derleme sırasında sınıf adlarını statik olarak tarar; `text-${x}-500`
 * gibi şablon dizeleri üretilen CSS'e girmez. Bu yüzden renkler tam sınıf adı
 * olarak burada sabitlenir.
 */
export interface AccentClasses {
  text: string;
  border: string;
  chip: string;
  groupHover: string;
  /** Grafik serileri için ham renk (recharts gibi CSS sınıfı alamayan API'ler). */
  hex: string;
}

export const ACCENT_CLASSES: Record<Accent, AccentClasses> = {
  red: { text: "text-red-400", border: "focus:border-red-500", chip: "bg-red-500/10 text-red-400", groupHover: "group-hover:text-red-400", hex: "#f87171" },
  emerald: { text: "text-emerald-400", border: "focus:border-emerald-500", chip: "bg-emerald-500/10 text-emerald-400", groupHover: "group-hover:text-emerald-400", hex: "#34d399" },
  purple: { text: "text-purple-400", border: "focus:border-purple-500", chip: "bg-purple-500/10 text-purple-400", groupHover: "group-hover:text-purple-400", hex: "#c084fc" },
  rose: { text: "text-rose-400", border: "focus:border-rose-500", chip: "bg-rose-500/10 text-rose-400", groupHover: "group-hover:text-rose-400", hex: "#fb7185" },
  amber: { text: "text-amber-400", border: "focus:border-amber-500", chip: "bg-amber-500/10 text-amber-400", groupHover: "group-hover:text-amber-400", hex: "#fbbf24" },
  cyan: { text: "text-cyan-400", border: "focus:border-cyan-500", chip: "bg-cyan-500/10 text-cyan-400", groupHover: "group-hover:text-cyan-400", hex: "#22d3ee" },
};
