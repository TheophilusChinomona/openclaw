// OpenRouter onboarding model selection: turns the live OpenRouter catalog into
// a picker the user can drive with a cursor, instead of asking them to type
// `openrouter/<vendor>/<model>` slugs from memory.
import type { ModelDefinitionConfig } from "openclaw/plugin-sdk/provider-model-shared";

export const OPENROUTER_AUTO_MODEL_REF = "openrouter/auto";

/** Short OpenClaw model refs surfaced by the picker (without the `openrouter/` prefix). */
export type OpenRouterCatalogEntry = {
  /** Upstream OpenRouter slug, e.g. `anthropic/claude-sonnet-4.6`. */
  slug: string;
  name: string;
  contextWindow?: number;
  /** USD per million tokens. */
  inputCost?: number;
  outputCost?: number;
  reasoning?: boolean;
  supportsImages?: boolean;
};

const CURATED_MODEL_SLUGS = [
  "anthropic/claude-sonnet-4.6",
  "anthropic/claude-opus-4.6",
  "openai/gpt-5.4",
  "openai/gpt-5.2",
  "google/gemini-3.5-pro",
  "moonshotai/kimi-k2.6",
  "deepseek/deepseek-v4-pro",
  "z-ai/glm-5.1",
  "x-ai/grok-4.5",
  "qwen/qwen3.5-max",
  "meta-llama/llama-4-maverick",
  "mistralai/mistral-large-3",
] as const;

function normalizeSlug(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const slug = value.trim().toLowerCase();
  return /^[a-z0-9._-]+\/[a-z0-9._:-]+$/.test(slug) ? slug : undefined;
}

export function buildOpenRouterModelRef(slug: string): string {
  return `openrouter/${slug}`;
}

/** Map live catalog model rows into picker entries, preserving catalog order. */
export function collectOpenRouterCatalogEntries(
  models: readonly ModelDefinitionConfig[],
): OpenRouterCatalogEntry[] {
  const entries: OpenRouterCatalogEntry[] = [];
  for (const model of models) {
    // Catalog rows keep the OpenClaw provider prefix (`openrouter/<slug>`).
    const slug = normalizeSlug(
      typeof model.id === "string" ? model.id.replace(/^openrouter\//, "") : undefined,
    );
    if (!slug) {
      continue;
    }
    entries.push({
      slug,
      name: model.name || slug,
      ...(model.contextWindow !== undefined ? { contextWindow: model.contextWindow } : {}),
      ...(model.cost
        ? {
            inputCost: model.cost.input,
            outputCost: model.cost.output,
          }
        : {}),
      ...(model.reasoning ? { reasoning: true } : {}),
      ...(Array.isArray(model.input) && model.input.includes("image")
        ? { supportsImages: true }
        : {}),
    });
  }
  return entries;
}

/**
 * Pick the curated subset that actually exists in the catalog, in curated
 * order. Falls back to the first available entries when nothing curated
 * matches (e.g. a renamed catalog).
 */
export function pickCuratedEntries(
  entries: readonly OpenRouterCatalogEntry[],
  curatedSlugs: readonly string[] = CURATED_MODEL_SLUGS,
): OpenRouterCatalogEntry[] {
  const bySlug = new Map(entries.map((entry) => [entry.slug, entry]));
  const curated = curatedSlugs
    .map((slug) => bySlug.get(slug))
    .filter((entry): entry is OpenRouterCatalogEntry => entry !== undefined);
  if (curated.length > 0) {
    return curated;
  }
  return entries.slice(0, 8);
}

function formatContextWindow(contextWindow: number | undefined): string | undefined {
  if (contextWindow === undefined || contextWindow <= 0) {
    return undefined;
  }
  if (contextWindow >= 1_000_000) {
    const millions = contextWindow / 1_000_000;
    return `${millions % 1 === 0 ? millions.toFixed(0) : millions.toFixed(1)}M ctx`;
  }
  return `${Math.round(contextWindow / 1000)}K ctx`;
}

function formatCostLabel(entry: OpenRouterCatalogEntry): string | undefined {
  const { inputCost, outputCost } = entry;
  if (inputCost === undefined || outputCost === undefined) {
    return undefined;
  }
  if (inputCost === 0 && outputCost === 0) {
    return "free";
  }
  const format = (value: number) => (value < 10 ? value.toFixed(2) : value.toFixed(1));
  return `$${format(inputCost)}/$${format(outputCost)} per Mtok`;
}

/** Build wizard picker options: curated first, then "All models". */
export function buildOpenRouterModelPickerOptions(
  entries: readonly OpenRouterCatalogEntry[],
): Array<{ value: string; label: string; hint?: string }> {
  const curated = pickCuratedEntries(entries);
  const curatedSlugs = new Set(curated.map((entry) => entry.slug));
  const options: Array<{ value: string; label: string; hint?: string }> = curated.map((entry) => ({
    value: buildOpenRouterModelRef(entry.slug),
    label: entry.name,
    hint: [formatContextWindow(entry.contextWindow), formatCostLabel(entry)]
      .filter(Boolean)
      .join(" · "),
  }));
  const remaining = entries.filter((entry) => !curatedSlugs.has(entry.slug));
  if (remaining.length > 0) {
    options.push({
      value: "__all__",
      label: `All models (${entries.length})`,
      hint: "Browse the full OpenRouter catalog",
    });
  }
  options.push({
    value: OPENROUTER_AUTO_MODEL_REF,
    label: "OpenRouter Auto (let OpenRouter choose)",
    hint: "Not recommended — routing varies per request",
  });
  return options;
}

/** Build the full-catalog picker options, alphabetically grouped by vendor. */
export function buildOpenRouterAllModelsOptions(
  entries: readonly OpenRouterCatalogEntry[],
): Array<{ value: string; label: string; hint?: string }> {
  const sorted = [...entries].sort((a, b) =>
    a.slug.localeCompare(b.slug, undefined, { sensitivity: "base" }),
  );
  const options = sorted.map((entry) => ({
    value: buildOpenRouterModelRef(entry.slug),
    label: `${entry.slug} — ${entry.name}`,
    hint: [formatContextWindow(entry.contextWindow), formatCostLabel(entry)]
      .filter(Boolean)
      .join(" · "),
  }));
  options.push({
    value: OPENROUTER_AUTO_MODEL_REF,
    label: "OpenRouter Auto (let OpenRouter choose)",
    hint: "Not recommended — routing varies per request",
  });
  return options;
}
