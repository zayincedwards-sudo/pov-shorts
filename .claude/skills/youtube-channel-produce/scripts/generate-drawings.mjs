#!/usr/bin/env node
// Generates DRAWING/illustration shots via Gemini image generation.
// Reads shots.txt (lines like "drawing | <description>" or "photo | <description>"),
// and for each "drawing" line generates an image named shot-<NN>.png (NN = video order).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models";
const IMG_MODEL = "gemini-3.1-flash-lite-image";

function parseArgs(argv) {
  const args = { shots: null, out: null, aspect: "16:9", apiKey: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--shots") args.shots = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--aspect") args.aspect = argv[++i];
    else if (a === "--api-key") args.apiKey = argv[++i];
    else if (a === "--help" || a === "-h") { printHelp(); process.exit(0); }
    else { console.error("Unknown arg: " + a); printHelp(); process.exit(2); }
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node generate-drawings.mjs --shots shots.txt --out shots/ [--aspect 16:9]

  --shots   shots.txt from produce.mjs (lines like "drawing | <desc>").
  --out     Output directory (default ./shots).
  --aspect  Aspect ratio for generated drawings (default 16:9).`);
}

function readKey(args) {
  if (args.apiKey) return args.apiKey;
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;
  const p = join(homedir(), ".deepcode-plus", "settings.json");
  if (existsSync(p)) {
    try {
      const c = JSON.parse(readFileSync(p, "utf8"));
      if (c?.env?.GEMINI_API_KEY) return c.env.GEMINI_API_KEY;
    } catch {}
  }
  return null;
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function postGenerateContent(key, model, body, retries = 4) {
  for (let attempt = 1; ; attempt++) {
    const r = await fetch(`${ENDPOINT}/${model}:generateContent?key=${encodeURIComponent(key)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (r.ok) return await r.json();
    const j = await r.json().catch(() => ({}));
    const err = new Error(`${model} (${r.status}): ${j.error?.message || JSON.stringify(j).slice(0, 200)}`);
    const retryable = r.status === 429 || r.status >= 500;
    if (!retryable || attempt >= retries) throw err;
    console.error(`  (retry ${attempt}/${retries} after HTTP ${r.status})`);
    await sleep(attempt * 1500);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.shots || !existsSync(args.shots)) { console.error("--shots file is required."); process.exit(1); }
  const key = readKey(args);
  if (!key) { console.error("No Gemini API key. Set env.GEMINI_API_KEY in ~/.deepcode-plus/settings.json."); process.exit(1); }

  const lines = readFileSync(args.shots, "utf8").split("\n").map(s => s.trim()).filter(Boolean);
  const outDir = args.out || "shots";
  mkdirSync(outDir, { recursive: true });

  let i = 0, n = 0;
  for (const line of lines) {
    i++;
    const parts = line.split("||");
    const type = (parts[0] || "").trim().toLowerCase();
    if (type !== "drawing") continue;
    const desc = (parts[1] || "").trim();
    const num = String(i).padStart(2, "0");
    const body = {
      contents: [{ parts: [{ text: `${desc}. Clean, high-quality illustration. No text or labels.` }] }],
      generationConfig: { responseModalities: ["TEXT", "IMAGE"], imageConfig: { aspectRatio: args.aspect } },
    };
    const j = await postGenerateContent(key, IMG_MODEL, body);
    const img = (j.candidates?.[0]?.content?.parts || []).find(p => p.inlineData);
    if (!img) { console.error(`  shot-${num}: no image returned`); continue; }
    writeFileSync(join(outDir, `shot-${num}.png`), Buffer.from(img.inlineData.data, "base64"));
    console.log(`Wrote ${join(outDir, `shot-${num}.png`)}  (drawing: ${desc.slice(0, 60)})`);
    n++;
  }
  console.log(`Done: generated ${n} drawing(s).`);
}

main().catch(e => { console.error("Error: " + e.message); process.exit(1); });
