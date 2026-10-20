import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src", import.meta.url).pathname.replace(
  /^\/([A-Za-z]:)/,
  "$1",
);

function walk(dir) {
  const files = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) files.push(...walk(path));
    else if (/\.(tsx|ts|jsx)$/.test(entry)) files.push(path);
  }
  return files;
}

const offenders = [];

for (const file of walk(root)) {
  const source = readFileSync(file, "utf8");
  const lines = source.split("\n");
  lines.forEach((line, index) => {
    const hasMediaTag = /<(img|video)\b/.test(line);
    const hasProtectedUrl =
      /(getEvidence|getCameraSnapshot|\/snapshot|\/evidence\/)/.test(line);
    const isBlob = /objectUrl|blobUrl/.test(line);
    if (hasMediaTag && hasProtectedUrl && !isBlob) {
      offenders.push(`${file}:${index + 1}: ${line.trim()}`);
    }
  });
}

if (offenders.length > 0) {
  console.error("Plain <img>/<video> tags referencing protected media found:");
  for (const offender of offenders) console.error(`  ${offender}`);
  console.error(
    "\nUse useAuthenticatedBlob + AuthenticatedImage (blob object URLs) instead.",
  );
  process.exit(1);
}

console.log("No plain <img>/<video> tags reference protected media");
