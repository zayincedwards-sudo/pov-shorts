#!/usr/bin/env node
// YouTube channel branding helper — profile picture, banner, and description via Gemini.
// Uses only Node.js built-ins (fetch is global in Node 18+).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models";
const IMG_MODEL = "gemini-3.1-flash-lite-image";
const TEXT_MODEL = "gemini-flash-latest";

function parseArgs(argv) {
  const args = { name: null, niche: null, style: null, styleRef: null, out: null, apiKey: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--name") args.name = argv[++i];
    else if (a === "--niche") args.niche = argv[++i];
    else if (a === "--style") args.style = argv[++i];
    else if (a === "--style-ref") args.styleRef = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--api-key") args.apiKey = argv[++i];
    else if (a === "--help" || a === "-h") { printHelp(); process.exit(0); }
    else { console.error("Unknown arg: " + a); printHelp(); process.exit(2); }
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node brand.mjs --name "<Channel Name>" --niche "<topic>" [--style "<desc>"] [--style-ref "<reference brand style>"] [--out dir]

  --name       Channel name. Required.
  --niche      Channel topic/niche. Required.
  --style      Optional extra style description.
  --style-ref  Optional reference branding (from the audit) to emulate as similar-but-original.
  --out        Output directory (default ./brand).`);
}

function readApiKey(args) {
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

async function genImage(key, prompt, aspectRatio) {
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { responseModalities: ["TEXT", "IMAGE"], imageConfig: { aspectRatio } },
  };
  const j = await postGenerateContent(key, IMG_MODEL, body);
  const img = (j.candidates?.[0]?.content?.parts || []).find(p => p.inlineData);
  if (!img) throw new Error("no image returned: " + JSON.stringify(j).slice(0, 200));
  return Buffer.from(img.inlineData.data, "base64");
}

async function genText(key, prompt) {
  const body = { contents: [{ parts: [{ text: prompt }] }] };
  const j = await postGenerateContent(key, TEXT_MODEL, body);
  return (j.candidates?.[0]?.content?.parts || []).map(p => p.text || "").join("").trim();
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.name || !args.niche) { console.error("--name and --niche are required.\n"); printHelp(); process.exit(2); }
  const key = readApiKey(args);
  if (!key) { console.error("No Gemini API key. Set env.GEMINI_API_KEY in ~/.deepcode-plus/settings.json."); process.exit(1); }

  const outDir = args.out || "./brand";
  mkdirSync(outDir, { recursive: true });
  const style = args.style || "clean, modern, high-contrast, memorable at small sizes";
  const styleRef = args.styleRef ? ` Match the reference channel's branding style — create SIMILAR but ORIGINAL elements (never copy names, logos, or text): ${args.styleRef}.` : "";

  console.log("Generating profile picture (1:1)...");
  const pfp = await genImage(key, `YouTube channel profile picture (avatar) for the channel "${args.name}" about ${args.niche}. ${style}.${styleRef} No text. Centered subject, bold and readable at small size.`, "1:1");
  writeFileSync(join(outDir, "profile.png"), pfp);

  console.log("Generating banner (16:9)...");
  const banner = await genImage(key, `YouTube channel banner for the channel "${args.name}" about ${args.niche}. ${style}.${styleRef} Wide composition, key subject centered in the safe area, important elements away from edges. No text.`, "16:9");
  writeFileSync(join(outDir, "banner.png"), banner);

  console.log("Writing description...");
  const desc = await genText(key, `Write a YouTube channel description for the channel "${args.name}" about ${args.niche}. ${style}.${styleRef} Include a short value proposition, what viewers can expect, and relevant keywords. 3-5 short paragraphs or bullets. Return only the description text.`);
  writeFileSync(join(outDir, "description.txt"), desc);

  console.log(`Wrote ${join(outDir, "profile.png")}, ${join(outDir, "banner.png")}, ${join(outDir, "description.txt")}`);
}

main().catch(e => { console.error("Error: " + e.message); process.exit(1); });
