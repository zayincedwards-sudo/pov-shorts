#!/usr/bin/env node
// Gemini image generation helper (gemini-3.1-flash-lite-image).
// Uses only Node.js built-ins (fetch is global in Node 18+).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, extname, basename, dirname } from "node:path";

const MODEL_DEFAULT = "gemini-3.1-flash-lite-image";
const ENDPOINT_BASE = "https://generativelanguage.googleapis.com/v1beta/models";

const MIME = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
};

const ASPECT_RATIOS = new Set([
  "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9",
]);

function printHelp() {
  console.log(`Usage: node generate.mjs --prompt "<text>" [options]

Options:
  --prompt <text>        Required. Text prompt / edit instruction.
  --image <path-or-url>  Reference image (repeatable). Local path, HTTP(S) URL,
                         or data URL.
  --aspect-ratio <ratio> Aspect ratio for text-to-image only (e.g. 1:1, 16:9).
  --output <path>        Output PNG path. Default: derived or gemini-output.png.
  --model <name>         Model name. Default: ${MODEL_DEFAULT}.
  --api-key <key>        Override API key (else GEMINI_API_KEY env, else
                         ~/.deepcode-plus/settings.json env.GEMINI_API_KEY).
  --help, -h             Show this help.`);
}

function parseArgs(argv) {
  const args = {
    prompt: null,
    images: [],
    aspectRatio: null,
    output: null,
    apiKey: null,
    model: MODEL_DEFAULT,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case "--prompt": args.prompt = argv[++i]; break;
      case "--image": args.images.push(argv[++i]); break;
      case "--aspect-ratio": args.aspectRatio = argv[++i]; break;
      case "--output": args.output = argv[++i]; break;
      case "--model": args.model = argv[++i]; break;
      case "--api-key": args.apiKey = argv[++i]; break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
      default:
        console.error(`Unknown argument: ${a}\n`);
        printHelp();
        process.exit(2);
    }
  }
  return args;
}

function readApiKey(args) {
  if (args.apiKey) return args.apiKey;
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;
  const settingsPath = join(homedir(), ".deepcode-plus", "settings.json");
  if (existsSync(settingsPath)) {
    try {
      const cfg = JSON.parse(readFileSync(settingsPath, "utf8"));
      const key = cfg?.env?.GEMINI_API_KEY;
      if (key) return key;
    } catch (e) {
      console.error(`Warning: could not parse ${settingsPath}: ${e.message}`);
    }
  }
  return null;
}

function mimeForPath(p) {
  return MIME[extname(p).toLowerCase()] || "image/png";
}

function isDataUrl(s) {
  return /^data:/i.test(s);
}

function isHttpUrl(s) {
  return /^https?:\/\//i.test(s);
}

// Resolve a reference image into { mimeType, data } (base64 string).
function resolveImage(ref) {
  if (isDataUrl(ref)) {
    const m = ref.match(/^data:([^;]+);base64,(.*)$/is);
    if (!m) throw new Error(`Unsupported data URL: ${ref.slice(0, 40)}...`);
    return { mimeType: m[1], data: m[2] };
  }
  if (isHttpUrl(ref)) {
    throw new Error(
      "HTTP(S) image URLs are not yet supported by this helper; " +
      "download the file locally and pass its path instead."
    );
  }
  if (!existsSync(ref)) {
    throw new Error(`Reference image not found: ${ref}`);
  }
  const data = readFileSync(ref).toString("base64");
  return { mimeType: mimeForPath(ref), data };
}

function buildRequestBody(args, images) {
  const parts = [{ text: args.prompt }];
  for (const img of images) {
    parts.push({ inlineData: { mimeType: img.mimeType, data: img.data } });
  }
  const generationConfig = { responseModalities: ["TEXT", "IMAGE"] };
  // aspectRatio applies to pure text-to-image; editing keeps input dimensions.
  if (images.length === 0 && args.aspectRatio) {
    if (!ASPECT_RATIOS.has(args.aspectRatio)) {
      throw new Error(
        `Unsupported aspect ratio "${args.aspectRatio}". ` +
        `Supported: ${[...ASPECT_RATIOS].join(", ")}`
      );
    }
    generationConfig.imageConfig = { aspectRatio: args.aspectRatio };
  }
  return { contents: [{ parts }], generationConfig };
}

async function generate(args) {
  const apiKey = readApiKey(args);
  if (!apiKey) {
    throw new Error(
      "No Gemini API key found. Set it in ~/.deepcode-plus/settings.json " +
      "under env.GEMINI_API_KEY, or pass --api-key, or set GEMINI_API_KEY."
    );
  }

  const images = args.images.map(resolveImage);
  const body = buildRequestBody(args, images);

  const url = `${ENDPOINT_BASE}/${args.model}:generateContent`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": apiKey,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API request failed (${resp.status} ${resp.statusText}): ${text}`);
  }

  const json = await resp.json();

  if (json.error) {
    throw new Error(`API error: ${json.error.message || JSON.stringify(json.error)}`);
  }

  const candidate = json.candidates && json.candidates[0];
  if (!candidate || !candidate.content || !candidate.content.parts) {
    const block = json.promptFeedback?.blockReason;
    throw new Error(
      `No image returned from the API.` +
      (block ? ` Prompt blocked: ${block}` : ` Raw response: ${JSON.stringify(json).slice(0, 500)}`)
    );
  }

  const parts = candidate.content.parts;
  const imageParts = parts.filter((p) => p.inlineData);
  const textParts = parts.filter((p) => p.text);

  if (textParts.length) {
    console.log(`[text] ${textParts.map((p) => p.text).join(" ").trim()}`);
  }

  if (imageParts.length === 0) {
    throw new Error(
      `The model returned no image data. Full response: ${JSON.stringify(json).slice(0, 500)}`
    );
  }

  const outputs = [];
  imageParts.forEach((part, i) => {
    const { mimeType = "image/png", data } = part.inlineData;
    const ext = mimeType.includes("webp") ? ".webp"
      : mimeType.includes("jpeg") || mimeType.includes("jpg") ? ".jpg"
      : ".png";
    let out;
    if (args.output) {
      out = imageParts.length > 1
        ? args.output.replace(/(\.\w+)?$/, `${i > 0 ? `-${i + 1}` : ""}$1`)
        : args.output;
    } else {
      const base = images.length
        ? basename(args.images[0]).replace(/\.[^.]+$/, "") + "-gemini"
        : "gemini-output";
      out = join(process.cwd(), `${base}${ext}`);
    }
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, Buffer.from(data, "base64"));
    outputs.push(out);
  });

  console.log(`Saved: ${outputs.join("\nSaved: ")}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.prompt) {
    console.error("Error: --prompt is required.\n");
    printHelp();
    process.exit(2);
  }
  try {
    await generate(args);
  } catch (e) {
    console.error(`Error: ${e.message}`);
    process.exit(1);
  }
}

main();
