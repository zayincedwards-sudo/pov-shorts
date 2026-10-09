#!/usr/bin/env node
// YouTube content producer — generates script, titles, description, and thumbnail
// from a topic + a channel config (and optional playbook) using Gemini.
// Uses only Node.js built-ins (fetch is global in Node 18+).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models";
const TEXT_MODEL = "gemini-flash-latest";
const IMG_MODEL = "gemini-3.1-flash-lite-image";

function parseArgs(argv) {
  const args = { topic: null, topics: null, config: null, out: null, apiKey: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--topic") args.topic = argv[++i];
    else if (a === "--topics") args.topics = argv[++i];
    else if (a === "--config") args.config = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--api-key") args.apiKey = argv[++i];
    else if (a === "--help" || a === "-h") { printHelp(); process.exit(0); }
    else { console.error("Unknown arg: " + a); printHelp(); process.exit(2); }
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node produce.mjs (--topic "<text>" | --topics file.txt) [--config channel-config.json] [--out dir]

  --topic    Single topic. (Use --topics for a batch.)
  --topics   File with one topic per line.
  --config   Optional channel-config.json (channelName, niche, style, playbookPath).
  --out      Output directory (default ./produce).`);
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

function loadConfig(path) {
  if (!path || !existsSync(path)) return {};
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return {}; }
}

function slugify(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "video";
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

async function genText(key, prompt) {
  const body = { contents: [{ parts: [{ text: prompt }] }] };
  const j = await postGenerateContent(key, TEXT_MODEL, body);
  return (j.candidates?.[0]?.content?.parts || []).map(p => p.text || "").join("").trim();
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const topics = [];
  if (args.topic) topics.push(args.topic);
  if (args.topics) {
    if (!existsSync(args.topics)) { console.error("Topics file not found: " + args.topics); process.exit(1); }
    topics.push(...readFileSync(args.topics, "utf8").split("\n").map(s => s.trim()).filter(Boolean));
  }
  if (topics.length === 0) { console.error("Provide --topic or --topics.\n"); printHelp(); process.exit(2); }

  const key = readApiKey(args);
  if (!key) { console.error("No Gemini API key. Set env.GEMINI_API_KEY in ~/.deepcode-plus/settings.json."); process.exit(1); }

  const cfg = loadConfig(args.config);
  const channelName = cfg.channelName || "this channel";
  const niche = cfg.niche || "";
  const style = cfg.style || "high-retention, fast-paced, curiosity-driven";
  const playbook = cfg.playbookPath && existsSync(cfg.playbookPath) ? readFileSync(cfg.playbookPath, "utf8") : "";

  const outRoot = args.out || "./produce";
  mkdirSync(outRoot, { recursive: true });

  for (const topic of topics) {
    const slug = slugify(topic);
    const dir = join(outRoot, slug);
    mkdirSync(dir, { recursive: true });
    console.log(`\n=== ${topic} ===`);

    const context = `Channel: ${channelName}${niche ? ` (${niche})` : ""}\nStyle guide: ${style}${playbook ? `\n\nPlaybook (proven tactics):\n${playbook.slice(0, 3000)}` : ""}`;

    console.log("  script...");
    const script = await genText(key, `${context}\n\nWrite a complete YouTube video script for the topic: "${topic}".\nStructure: attention hook in the first 10 seconds, then a clear narrative with pacing notes, a mid-video payoff/re-engagement beat, and a strong call-to-action ending. Include spoken narration and [visual/stock] cues in brackets. Aim for ~3-5 minutes of spoken content.`);
    writeFileSync(join(dir, "script.md"), script);

    console.log("  titles...");
    const titles = await genText(key, `${context}\n\nGenerate 3 YouTube titles for a video on: "${topic}". Make them clickable, curiosity-driven, and under 60 characters each. Output one per line, numbered 1-3, no extra commentary.`);
    writeFileSync(join(dir, "titles.txt"), titles);

    console.log("  description...");
    const desc = await genText(key, `${context}\n\nWrite a YouTube description for a video on: "${topic}". Include a 2-sentence hook, relevant keywords, and a call to subscribe. Keep it under 150 words.`);
    writeFileSync(join(dir, "description.txt"), desc);

    console.log("  shots...");
    const shots = await genText(key, `${context}\n\nHere is the script:\n${script}\n\nList every distinct image or visual frame that should appear on screen, in the exact order they appear in the script. For each one, output exactly one line in this pipe-delimited format (no numbering, no other commentary):\n<type> || <short description> || <motion> || <text>\n\nwhere:\n- <type> is "photo" (a real photograph) or "drawing" (illustration, diagram, 3D render, animation frame, chart, infographic, or graphic).\n- <motion> is "none", "zoom-in", "zoom-out", "pan-left", or "pan-right". Use "none" unless camera movement genuinely adds impact to this specific shot. Be conservative — never add motion just for variety.\n- <text> is a short on-screen caption (2-5 words, e.g. a key number or phrase) ONLY if it reinforces the point, otherwise "none". Be conservative.\n\nExample lines:\ndrawing || 3D animation of the Moon receding from Earth || zoom-in || 3.8 CM PER YEAR\nphoto || close-up of a human fingernail || none || none`);
    writeFileSync(join(dir, "shots.txt"), shots);

    console.log("  thumbnail...");
    const thumbPrompt = `${context}\n\nCreate a high-CTR YouTube thumbnail for a video titled "${topic}". Bold, high contrast, one clear focal subject, dramatic lighting, minimal text.`;
    const thumb = await genImage(key, thumbPrompt, "16:9");
    writeFileSync(join(dir, "thumbnail.png"), thumb);

    const title0 = (titles.split("\n").find(l => /^1[\.\)]/.test(l.trim())) || titles.split("\n")[0] || topic).replace(/^1[\.\)]\s*/, "").trim();
    const meta = { topic, slug, title: title0, channelName, niche, style };
    writeFileSync(join(dir, "publish.json"), JSON.stringify(meta, null, 2));

    console.log(`  -> ${dir} (script.md, titles.txt, description.txt, shots.txt, thumbnail.png)`);
  }

  console.log(`\nDone. ${topics.length} package(s) in ${outRoot}`);
  console.log("Next: placeholders (make-placeholders), voiceover (11labs), assembly (ffmpeg). See SKILL.md.");
}

main().catch(e => { console.error("Error: " + e.message); process.exit(1); });
