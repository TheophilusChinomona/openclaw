// OpenRouter onboarding model-selection tests: catalog mapping and picker options.
import { describe, expect, it } from "vitest";
import {
  buildOpenRouterAllModelsOptions,
  buildOpenRouterModelPickerOptions,
  buildOpenRouterModelRef,
  collectOpenRouterCatalogEntries,
  OPENROUTER_AUTO_MODEL_REF,
  pickCuratedEntries,
} from "./model-selection.js";

function catalogRow(params: {
  id: string;
  name?: string;
  reasoning?: boolean;
  image?: boolean;
  contextWindow?: number;
  inputCost?: number;
  outputCost?: number;
}) {
  return {
    id: params.id,
    name: params.name ?? params.id,
    reasoning: params.reasoning ?? false,
    input: params.image ? ["text", "image"] : ["text"],
    cost: {
      input: params.inputCost ?? 0,
      output: params.outputCost ?? 0,
      cacheRead: 0,
      cacheWrite: 0,
    },
    contextWindow: params.contextWindow ?? 200000,
    maxTokens: 8192,
  };
}

describe("buildOpenRouterModelRef", () => {
  it("prefixes upstream slugs with the openrouter provider prefix", () => {
    expect(buildOpenRouterModelRef("anthropic/claude-sonnet-4.6")).toBe(
      "openrouter/anthropic/claude-sonnet-4.6",
    );
  });
});

describe("collectOpenRouterCatalogEntries", () => {
  it("maps live catalog rows into picker entries", () => {
    const entries = collectOpenRouterCatalogEntries([
      catalogRow({
        id: "openrouter/anthropic/claude-sonnet-4.6",
        name: "Anthropic: Claude Sonnet 4.6",
        reasoning: true,
        image: true,
        contextWindow: 1_000_000,
        inputCost: 3,
        outputCost: 15,
      }),
      catalogRow({ id: "openrouter/moonshotai/kimi-k2.6", name: "MoonshotAI: Kimi K2.6" }),
    ]);
    expect(entries).toEqual([
      {
        slug: "anthropic/claude-sonnet-4.6",
        name: "Anthropic: Claude Sonnet 4.6",
        contextWindow: 1_000_000,
        inputCost: 3,
        outputCost: 15,
        reasoning: true,
        supportsImages: true,
      },
      {
        slug: "moonshotai/kimi-k2.6",
        name: "MoonshotAI: Kimi K2.6",
        contextWindow: 200000,
        inputCost: 0,
        outputCost: 0,
      },
    ]);
  });

  it("skips rows without a usable namespaced slug", () => {
    const entries = collectOpenRouterCatalogEntries([
      catalogRow({ id: "openrouter/auto" }),
      catalogRow({ id: "openrouter/bad-slug-no-slash" }),
      catalogRow({ id: "openrouter/meta-llama/llama-3.3-70b:free", name: "Llama free" }),
    ]);
    expect(entries.map((entry) => entry.slug)).toEqual(["meta-llama/llama-3.3-70b:free"]);
  });
});

describe("pickCuratedEntries", () => {
  it("returns curated models in curated order when most exist", () => {
    const entries = collectOpenRouterCatalogEntries([
      catalogRow({ id: "openrouter/google/gemini-3.5-pro", name: "Gemini" }),
      catalogRow({ id: "openrouter/anthropic/claude-sonnet-4.6", name: "Sonnet" }),
      catalogRow({ id: "openrouter/openai/gpt-5.4", name: "GPT" }),
      catalogRow({ id: "openrouter/other/model", name: "Other" }),
    ]);
    const curated = pickCuratedEntries(entries);
    expect(curated.map((entry) => entry.slug)).toEqual([
      "anthropic/claude-sonnet-4.6",
      "openai/gpt-5.4",
      "google/gemini-3.5-pro",
    ]);
  });

  it("falls back to the first entries when the curated set no longer matches", () => {
    const entries = collectOpenRouterCatalogEntries([
      catalogRow({ id: "openrouter/aaa/first" }),
      catalogRow({ id: "openrouter/bbb/second" }),
      catalogRow({ id: "openrouter/ccc/third" }),
    ]);
    expect(pickCuratedEntries(entries).map((entry) => entry.slug)).toEqual([
      "aaa/first",
      "bbb/second",
      "ccc/third",
    ]);
  });
});

describe("buildOpenRouterModelPickerOptions", () => {
  it("lists curated models first with context and pricing hints, then all-models entry", () => {
    const entries = collectOpenRouterCatalogEntries([
      catalogRow({
        id: "openrouter/anthropic/claude-sonnet-4.6",
        name: "Anthropic: Claude Sonnet 4.6",
        contextWindow: 1_000_000,
        inputCost: 3,
        outputCost: 15,
      }),
      catalogRow({ id: "openrouter/aaa/first" }),
      catalogRow({ id: "openrouter/bbb/second" }),
      catalogRow({ id: "openrouter/ccc/third" }),
    ]);
    const options = buildOpenRouterModelPickerOptions(entries);
    expect(options[0]).toMatchObject({
      value: "openrouter/anthropic/claude-sonnet-4.6",
      label: "Anthropic: Claude Sonnet 4.6",
      hint: "1M ctx · $3.00/$15.0 per Mtok",
    });
    expect(options.at(-2)).toMatchObject({
      value: "__all__",
      label: "All models (4)",
    });
    expect(options.at(-1)).toMatchObject({ value: OPENROUTER_AUTO_MODEL_REF });
  });
});

describe("buildOpenRouterAllModelsOptions", () => {
  it("sorts by slug and includes auto last", () => {
    const entries = collectOpenRouterCatalogEntries([
      catalogRow({ id: "openrouter/zzz/last", name: "Last" }),
      catalogRow({ id: "openrouter/aaa/first", name: "First" }),
    ]);
    const options = buildOpenRouterAllModelsOptions(entries);
    expect(options.map((option) => option.value)).toEqual([
      "openrouter/aaa/first",
      "openrouter/zzz/last",
      OPENROUTER_AUTO_MODEL_REF,
    ]);
    expect(options[0]?.label).toBe("aaa/first — First");
  });
});
