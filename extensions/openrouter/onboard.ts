// Openrouter setup module handles plugin onboarding behavior.
import {
  createAliasOnlyPresetAppliers,
  type OpenClawConfig,
} from "openclaw/plugin-sdk/provider-onboard";

export const OPENROUTER_DEFAULT_MODEL_REF = "openrouter/auto";
const openrouterPresetAppliers = createAliasOnlyPresetAppliers({
  modelRef: OPENROUTER_DEFAULT_MODEL_REF,
  alias: "OpenRouter",
});

export function applyOpenrouterProviderConfig(cfg: OpenClawConfig): OpenClawConfig {
  return openrouterPresetAppliers.applyProviderConfig(cfg);
}

export function applyOpenrouterConfig(cfg: OpenClawConfig): OpenClawConfig {
  return openrouterPresetAppliers.applyConfig(cfg);
}

/**
 * Apply the OpenRouter onboarding preset with a specific model ref as the
 * primary default (alias + primary), used when onboarding picked a concrete
 * model from the live catalog instead of the `openrouter/auto` fallback.
 */
export function applyOpenrouterConfigForModel(
  cfg: OpenClawConfig,
  modelRef: string,
): OpenClawConfig {
  if (modelRef === OPENROUTER_DEFAULT_MODEL_REF) {
    return applyOpenrouterConfig(cfg);
  }
  const appliers = createAliasOnlyPresetAppliers({ modelRef, alias: "OpenRouter" });
  return appliers.applyConfig(cfg);
}
