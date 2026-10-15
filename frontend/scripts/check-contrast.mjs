import { readFileSync } from "node:fs";
import { parse, converter } from "culori";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

const vars = {};
for (const match of css.matchAll(/--([a-z0-9-]+):\s*([^;]+);/gi)) {
  const value = match[2].trim();
  if (value.startsWith("var(") || value.startsWith("calc(")) continue;
  vars[match[1]] = value;
}

const toRgb = converter("rgb");

function rgba(reference) {
  const value = vars[reference] ?? reference;
  const parsed = parse(value);
  if (!parsed) throw new Error(`Cannot parse color: ${reference} -> ${value}`);
  const c = toRgb(parsed);
  return [c.r, c.g, c.b, c.alpha ?? 1];
}

function over(fg, bg) {
  const a = fg[3];
  return [
    fg[0] * a + bg[0] * (1 - a),
    fg[1] * a + bg[1] * (1 - a),
    fg[2] * a + bg[2] * (1 - a),
    1,
  ];
}

function luminance([r, g, b]) {
  const f = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function ratio(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

const WHITE = [1, 1, 1, 1];
const BLACK = [0, 0, 0, 1];

const surface1 = rgba("surface-1");
const surface2 = rgba("surface-2");

const textPairs = [
  ["foreground", "background"],
  ["foreground", "surface-1"],
  ["foreground", "surface-2"],
  ["muted-foreground", "background"],
  ["muted-foreground", "surface-1"],
  ["primary-foreground", "primary"],
  ["sev-critical on critical-bg", over(rgba("sev-critical-bg"), surface1), rgba("sev-critical")],
  ["sev-high on high-bg", over(rgba("sev-high-bg"), surface1), rgba("sev-high")],
  ["sev-medium on medium-bg", over(rgba("sev-medium-bg"), surface1), rgba("sev-medium")],
  ["sev-low on low-bg", over(rgba("sev-low-bg"), surface1), rgba("sev-low")],
  ["ok on ok-bg", over(rgba("ok-bg"), surface1), rgba("ok")],
];

const glassHud = rgba("glass-hud-bg");
textPairs.push(
  ["glass-hud text over white frame", over(glassHud, WHITE), WHITE],
  ["glass-hud text over black frame", over(glassHud, BLACK), WHITE],
);

const uiPairs = [
  ["primary icon/border vs background", "primary", "background"],
  ["ring vs background", "ring", "background"],
  ["border-strong vs surface-2", "border-strong", "surface-2"],
  ["sev-critical vs background", "sev-critical", "background"],
  ["sev-high vs background", "sev-high", "background"],
  ["sev-medium vs background", "sev-medium", "background"],
  ["sev-low vs background", "sev-low", "background"],
  ["ok vs background", "ok", "background"],
];

let failures = 0;

function check(label, a, b, min) {
  const value = ratio(a, b);
  const pass = value >= min;
  if (!pass) failures += 1;
  const status = pass ? "PASS" : "FAIL";
  console.log(
    `${status}  ${value.toFixed(2)}:1  (min ${min})  ${label}`,
  );
}

console.log("Text pairs (min 4.5:1)");
for (const pair of textPairs) {
  if (pair.length === 3) {
    check(pair[0], pair[1], pair[2], 4.5);
  } else {
    check(pair[0], rgba(pair[0]), rgba(pair[1]), 4.5);
  }
}

console.log("\nUI pairs (min 3:1)");
for (const pair of uiPairs) {
  if (pair.length === 3) {
    check(pair[0], rgba(pair[1]), rgba(pair[2]), 3);
  } else {
    check(pair[0], rgba(pair[0]), rgba(pair[1]), 3);
  }
}

if (failures > 0) {
  console.error(`\n${failures} contrast failure(s)`);
  process.exit(1);
}
console.log("\nAll contrast checks passed");
