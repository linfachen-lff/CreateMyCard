import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import ts from "../../../intermediate_expression/node_modules/typescript/lib/typescript.js";

import { WIDGET_ASSET_CAPABILITIES } from "../../../intermediate_expression/packages/widget-capability-registry/src/asset-capabilities.ts";
import { WIDGET_UX_FIXTURES } from "../../../intermediate_expression/packages/widget-capability-registry/src/ux-fixtures.ts";

const serviceRoot = resolve(import.meta.dirname, "..");
const upstreamRoot = resolve(serviceRoot, "../../intermediate_expression");
const testSourcePath = resolve(upstreamRoot, "tests/card-plan-template.test.ts");
const liveSourcePath = resolve(upstreamRoot, "scripts/verify-card-template-live.ts");
const goldenRoot = resolve(upstreamRoot, "tests/golden/ux-design-2x2");
const outputPath = resolve(serviceRoot, "tests/fixtures/cardplan_golden_scenarios.json");

function unwrap(node: ts.Expression): ts.Expression {
  if (ts.isAsExpression(node) || ts.isParenthesizedExpression(node)) return unwrap(node.expression);
  if (ts.isCallExpression(node) && node.arguments.length === 1) return unwrap(node.arguments[0]);
  return node;
}

function staticValue(node: ts.Expression): unknown {
  const value = unwrap(node);
  if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) return value.text;
  if (ts.isNumericLiteral(value)) return Number(value.text);
  if (value.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (value.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (value.kind === ts.SyntaxKind.NullKeyword) return null;
  if (ts.isArrayLiteralExpression(value)) return value.elements.map((item) => staticValue(item));
  if (ts.isObjectLiteralExpression(value)) {
    return Object.fromEntries(value.properties.map((property) => {
      if (!ts.isPropertyAssignment(property)) throw new Error("Only static properties are allowed");
      const name = property.name;
      const key = ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)
        ? name.text
        : undefined;
      if (key === undefined) throw new Error("Unsupported static property name");
      return [key, staticValue(property.initializer)];
    }));
  }
  throw new Error(`Unsupported static expression: ${ts.SyntaxKind[value.kind]}`);
}

function exportedConstant(path: string, variableName: string): unknown {
  const sourceText = readFileSync(path, "utf8");
  const source = ts.createSourceFile(path, sourceText, ts.ScriptTarget.Latest, true);
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || declaration.name.text !== variableName) continue;
      if (declaration.initializer === undefined) throw new Error(`${variableName} has no value`);
      return staticValue(declaration.initializer);
    }
  }
  throw new Error(`Missing ${variableName} in ${path}`);
}

function goldenSummary(source: string): Record<string, unknown> {
  const rows = source.trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);
  const update = rows.find((row) => "updateComponents" in row)?.updateComponents as
    | { components?: Record<string, unknown>[] }
    | undefined;
  const components = update?.components ?? [];
  const componentTypes: Record<string, number> = {};
  const visibleTexts: string[] = [];
  const actionIds: string[] = [];
  for (const component of components) {
    const type = String(component.component ?? "");
    componentTypes[type] = (componentTypes[type] ?? 0) + 1;
    for (const key of ["content", "label", "valueText"]) {
      if (typeof component[key] === "string" && (component[key] as string).trim()) {
        visibleTexts.push(component[key] as string);
      }
    }
    const action = component.action as { event?: { name?: unknown } } | undefined;
    if (typeof action?.event?.name === "string") actionIds.push(action.event.name);
  }
  const root = components.find((component) => component.id === "root");
  return {
    visibleTexts,
    actionIds,
    componentTypes,
    componentCount: components.length,
    rootComponent: root?.component,
    rootStyles: root?.styles ?? {},
  };
}

function cardParameters(fixture: (typeof WIDGET_UX_FIXTURES)[number]): Record<string, unknown> {
  const required = fixture.cardTemplate.requiredChrome;
  const result: Record<string, unknown> = {};
  for (const candidate of fixture.cardTemplate.headerTextCandidates) {
    if (candidate.key === required.titleKey) result.title = candidate.text;
    if (candidate.key === required.subtitleKey) result.subtitle = candidate.text;
  }
  if (required.iconAssetId !== undefined) {
    result.titleIcon = WIDGET_ASSET_CAPABILITIES.find(
      (asset) => asset.id === required.iconAssetId,
    )?.src;
  }
  if (required.actionId !== undefined) {
    result.action = {
      label: fixture.eventDisplayLabels[required.actionId],
      id: required.actionId,
    };
  }
  return result;
}

const bodySources = exportedConstant(testSourcePath, "GOLDEN_BODY_SOURCES") as Record<string, string>;
const scenes = exportedConstant(liveSourcePath, "scenes") as Record<string, string>[];
const manifest = JSON.parse(readFileSync(resolve(goldenRoot, "manifest.json"), "utf8")) as {
  scenes: { id: string; protocolFile: string }[];
};

const scenarios = scenes.map((scene) => {
  const fixture = WIDGET_UX_FIXTURES.find((item) => item.fixtureId === scene.fixtureId);
  if (fixture === undefined) throw new Error(`Missing fixture ${scene.fixtureId}`);
  const body = bodySources[fixture.fixtureId];
  if (body === undefined) throw new Error(`Missing body ${fixture.fixtureId}`);
  const manifestScene = manifest.scenes.find((item) => item.id === scene.id);
  if (manifestScene === undefined) throw new Error(`Missing Golden ${scene.id}`);
  const golden = readFileSync(resolve(goldenRoot, manifestScene.protocolFile), "utf8");
  const params = JSON.stringify(cardParameters(fixture));
  const rawHybridSource = `Template("card@1", ${params}, ${body.replace(/;$/u, "")});`;
  return {
    ...scene,
    cardSize: fixture.cardSize,
    dataEntries: fixture.dataEntries,
    eventDisplayLabels: fixture.eventDisplayLabels,
    assets: fixture.requiredAssetIds.map((assetId) => {
      const asset = WIDGET_ASSET_CAPABILITIES.find((item) => item.id === assetId);
      if (asset === undefined) throw new Error(`Missing asset ${assetId}`);
      return { id: asset.id, src: asset.src, description: asset.description };
    }),
    cardTemplate: fixture.cardTemplate,
    rawHybridSource,
    goldenFile: manifestScene.protocolFile,
    goldenSha256: createHash("sha256").update(golden).digest("hex"),
    goldenSummary: goldenSummary(golden),
  };
});

mkdirSync(dirname(outputPath), { recursive: true });
const output = `${JSON.stringify({ version: 1, scenarios }, null, 2)}\n`;
if (process.argv.includes("--check")) {
  if (readFileSync(outputPath, "utf8") !== output) {
    throw new Error(`CardPlan Golden fixture drift: ${outputPath}`);
  }
} else {
  writeFileSync(outputPath, output, "utf8");
}
