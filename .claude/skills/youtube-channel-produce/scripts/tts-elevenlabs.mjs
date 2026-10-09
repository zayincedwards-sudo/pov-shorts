#!/usr/bin/env node
// ElevenLabs text-to-speech helper. UNTESTED — requires ELEVENLABS_API_KEY.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const API = "https://api.elevenlabs.io/v1";

function parseArgs(argv) {
  const args = { text: null, file: null, voiceId: null, out: null, apiKey: null, model: "eleven_multilingual_v2" };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--text") args.text = argv[++i];
    else if (a === "--file") args.file = argv[++i];
    else if (a === "--voice-id") args.voiceId = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--api-key") args.apiKey = argv[++i];
    else if (a === "--model") args.model = argv[++i];
    else if (a === "--help" || a === "-h") { printHelp(); process.exit(0); }
    else { console.error("Unknown arg: " + a); printHelp(); process.exit(2); }
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node tts-elevenlabs.mjs (--text "<narration>" | --file script.md) --voice-id <ID> [--out voiceover.mp3]

  --text       Narration text to speak.
  --file       File to read as text (e.g. a cleaned narration file).
  --voice-id   ElevenLabs voice ID. Required.
  --model      Model (default eleven_multilingual_v2).
  --out        Output mp3 path.`);
}

function readKey(args) {
  if (args.apiKey) return args.apiKey;
  if (process.env.ELEVENLABS_API_KEY) return process.env.ELEVENLABS_API_KEY;
  const p = join(homedir(), ".deepcode-plus", "settings.json");
  if (existsSync(p)) {
    try {
      const c = JSON.parse(readFileSync(p, "utf8"));
      if (c?.env?.ELEVENLABS_API_KEY) return c.env.ELEVENLABS_API_KEY;
    } catch {}
  }
  return null;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const key = readKey(args);
  if (!key) { console.error("No ELEVENLABS_API_KEY. Set env.ELEVENLABS_API_KEY in ~/.deepcode-plus/settings.json."); process.exit(1); }
  if (!args.voiceId) { console.error("--voice-id is required."); process.exit(1); }

  let text = args.text || "";
  if (!text && args.file && existsSync(args.file)) text = readFileSync(args.file, "utf8");
  text = text.trim();
  if (!text) { console.error("No text. Provide --text or --file."); process.exit(1); }

  const url = `${API}/text-to-speech/${encodeURIComponent(args.voiceId)}`;
  const r = await fetch(url, {
    method: "POST",
    headers: { "xi-api-key": key, "Content-Type": "application/json" },
    body: JSON.stringify({ text, model_id: args.model, voice_settings: { stability: 0.5, similarity_boost: 0.75 } }),
  });
  if (!r.ok) { const t = await r.text(); console.error("ElevenLabs failed (" + r.status + "): " + t.slice(0, 300)); process.exit(1); }
  const buf = Buffer.from(await r.arrayBuffer());
  const out = args.out || "voiceover.mp3";
  writeFileSync(out, buf);
  console.log("Wrote " + out + " (" + buf.length + " bytes)");
}

main().catch(e => { console.error("Error: " + e.message); process.exit(1); });
