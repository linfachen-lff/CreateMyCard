import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import {
  TERSE_TEMPLATE_DEFINITIONS,
  TERSE_TEMPLATE_REGISTRY_VERSION,
} from "../../../intermediate_expression/packages/core/src/terse-template-registry.ts";
import {
  ADAPTIVE_TEMPLATE_FAMILIES,
  ADVANCED_COMPONENT_CAPABILITIES,
  ADVANCED_COMPONENT_DOMAIN_GROUPS,
  ADVANCED_COMPONENT_REGISTRY_VERSION,
  CARD_SIZE_CONTENT_BUDGETS,
} from "../../../intermediate_expression/packages/core/src/advanced-component-registry.ts";
import {
  cardRootComponent,
  cardRootStyles,
  resolveCardPalette,
} from "../../../intermediate_expression/packages/core/src/card-palette.ts";
import {
  CANONICAL_PALETTE_PROFILES,
} from "../../../intermediate_expression/packages/core/src/theme-registry.ts";

const serviceRoot = resolve(import.meta.dirname, "..");
const outputRoot = resolve(serviceRoot, "cloud/data/cardplan_template/source");
const upstreamRoot = resolve(serviceRoot, "../../intermediate_expression");
const checkOnly = process.argv.includes("--check");

function writeOrCheck(path: string, text: string): void {
  if (checkOnly) {
    if (readFileSync(path, "utf8") !== text) throw new Error(`CardPlan source drift: ${path}`);
    return;
  }
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text, "utf8");
}

function writeJson(path: string, value: unknown): void {
  writeOrCheck(path, `${JSON.stringify(value, null, 2)}\n`);
}

const themes = CANONICAL_PALETTE_PROFILES.map((theme) => {
  const palette = resolveCardPalette(theme.themeProfileId);
  if (!palette.ok || palette.value === undefined) {
    throw new Error(`Cannot resolve palette ${theme.themeProfileId}`);
  }
  return {
    ...theme,
    rootComponent: cardRootComponent(palette.value),
    rootStyles: cardRootStyles(palette.value),
  };
});

writeJson(resolve(outputRoot, "template-registry.json"), {
  registryVersion: TERSE_TEMPLATE_REGISTRY_VERSION,
  templates: TERSE_TEMPLATE_DEFINITIONS,
});
writeJson(resolve(outputRoot, "advanced-component-registry.json"), {
  registryVersion: ADVANCED_COMPONENT_REGISTRY_VERSION,
  components: ADVANCED_COMPONENT_CAPABILITIES,
  adaptiveTemplates: ADAPTIVE_TEMPLATE_FAMILIES,
  sizeBudgets: CARD_SIZE_CONTENT_BUDGETS,
  domainGroups: ADVANCED_COMPONENT_DOMAIN_GROUPS,
});
writeJson(resolve(outputRoot, "theme-profiles.json"), {
  themeRegistryVersion: "theme-registry/1",
  themes,
});

const promptGroups = ["card-template-planner", "hybrid-body-generator"];
for (const group of promptGroups) {
  const fragments = group === "card-template-planner"
    ? ["00-chrome-kernel.md", "10-dsl-and-boundary.md"]
    : ["00-hybrid-kernel.md", "10-template-composition.md", "20-action-and-budget.md"];
  for (const fragment of fragments) {
    const source = resolve(upstreamRoot, "docs/prompts", group, fragment);
    const target = resolve(outputRoot, "prompts", group, fragment);
    writeOrCheck(target, readFileSync(source, "utf8"));
  }
}
