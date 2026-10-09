#!/usr/bin/env node
// Assemble a slideshow video from a sequence of images (+ optional voiceover) via ffmpeg.
// Per-shot motion (zoom/pan) and on-screen text are applied ONLY when flagged in shots.txt.
// Static shots preserve aspect ratio (letterboxed); motion shots fill the frame (cover+crop).
import { readdirSync, readFileSync, writeFileSync, existsSync, mkdirSync, globSync } from "node:fs";
import { homedir } from "node:os";
import { join, extname } from "node:path";
import { execFileSync } from "node:child_process";

function parseArgs(argv) {
  const args = { images: null, audio: null, out: null, shots: null, duration: 5, width: 1920, height: 1080, fps: 30 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--images") args.images = argv[++i];
    else if (a === "--audio") args.audio = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--shots") args.shots = argv[++i];
    else if (a === "--duration") args.duration = parseFloat(argv[++i]) || 5;
    else if (a === "--width") args.width = parseInt(argv[++i], 10) || 1920;
    else if (a === "--height") args.height = parseInt(argv[++i], 10) || 1080;
    else if (a === "--fps") args.fps = parseInt(argv[++i], 10) || 30;
    else if (a === "--help" || a === "-h") { printHelp(); process.exit(0); }
    else { console.error("Unknown arg: " + a); printHelp(); process.exit(2); }
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node assemble.mjs --images <dir> [--shots shots.txt] --out video.mp4 [--audio voiceover.mp3] [--duration 5]

  --images    Directory of images (shot-01.png, shot-02.png, ...). Required.
  --shots     Optional shots.txt ("type || description || motion || text") for per-shot motion/text.
  --audio     Voiceover audio file (optional).
  --out       Output mp4. Required.
  --duration  Seconds per image (default 5).`);
}

function imageFiles(dir) {
  const exts = [".png", ".jpg", ".jpeg", ".webp", ".bmp"];
  return readdirSync(dir).filter(f => exts.includes(extname(f).toLowerCase())).sort();
}

const MOTIONS = new Set(["zoom-in", "zoom-out", "pan-left", "pan-right"]);

// Parse shots.txt -> map: index (1-based) -> { motion, text }
function parseShots(path) {
  const map = {};
  if (!path || !existsSync(path)) return map;
  readFileSync(path, "utf8").split("\n").map(s => s.trim()).filter(Boolean).forEach((line, idx) => {
    const parts = line.split("||").map(s => s.trim());
    const motion = (parts[2] || "none").toLowerCase();
    const text = parts[3] || "";
    map[idx + 1] = {
      motion: MOTIONS.has(motion) ? motion : "none",
      text: text && text !== "none" ? text : "",
    };
  });
  return map;
}

function escapeText(s) {
  return s.replace(/\\/g, "\\\\").replace(/:/g, "\\:").replace(/'/g, "\\'").replace(/%/g, "\\%");
}

let _font;
function resolveFont() {
  if (_font) return _font;
  for (const f of ["arialbd.ttf", "arial.ttf"]) {
    if (existsSync("C:/Windows/Fonts/" + f)) { _font = "C\\:/Windows/Fonts/" + f; return _font; }
  }
  _font = "Arial";
  return _font;
}

function buildFilter(shot, args) {
  const W = args.width, H = args.height, fps = args.fps;
  const frames = Math.max(1, Math.round(args.duration * fps));
  const motion = shot?.motion || "none";
  const text = shot?.text || "";

  let chain;
  if (motion === "none") {
    chain = `scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=black`;
  } else {
    // Fast crop-based motion (zoompan is far too slow). Scale up for panning room, then animate the crop window.
    const Z = 1.2;
    chain = `scale=${Math.round(W * Z)}:${Math.round(H * Z)}:force_original_aspect_ratio=increase`;
    const D = Math.max(0.01, args.duration);
    const dir = (motion === "zoom-out" || motion === "pan-right") ? `(1-t/${D})` : `t/${D}`;
    chain += `,crop=${W}:${H}:x='(iw-${W})*${dir}':y='(ih-${H})/2'`;
  }

  if (text) {
    chain += `,drawtext=fontfile='${resolveFont()}':text='${escapeText(text)}':fontsize=72:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-text_h-120`;
  }
  return chain;
}

let _ffmpeg;
function resolveFfmpeg() {
  if (_ffmpeg) return _ffmpeg;
  if (process.env.FFMPEG_PATH && existsSync(process.env.FFMPEG_PATH)) return (_ffmpeg = process.env.FFMPEG_PATH);
  const candidates = globSync(join(homedir(), "AppData", "Local", "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg_*", "ffmpeg-*", "bin", "ffmpeg.exe"));
  _ffmpeg = candidates.length ? candidates[0] : "ffmpeg";
  return _ffmpeg;
}

function run(cmd) {
  try { execFileSync(resolveFfmpeg(), cmd, { stdio: "inherit" }); }
  catch (e) {
    console.error("ffmpeg failed. Is it installed? Try: winget install Gyan.FFmpeg");
    console.error(e.message);
    process.exit(1);
  }
}

let _ffprobe;
function resolveFfprobe() {
  if (_ffprobe) return _ffprobe;
  const ff = resolveFfmpeg();
  _ffprobe = ff === "ffmpeg" ? "ffprobe" : ff.replace(/ffmpeg\.exe$/, "ffprobe.exe");
  return _ffprobe;
}

function getAudioDuration(audioPath) {
  try {
    const out = execFileSync(resolveFfprobe(), ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audioPath], { encoding: "utf8" });
    const d = parseFloat(out.trim());
    return Number.isFinite(d) && d > 0 ? d : null;
  } catch {
    return null;
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.images || !existsSync(args.images)) { console.error("--images dir is required."); process.exit(1); }
  if (!args.out) { console.error("--out is required."); process.exit(1); }

  const files = imageFiles(args.images);
  if (files.length === 0) { console.error("No images found in " + args.images); process.exit(1); }
  const shots = parseShots(args.shots);

  // If a voiceover is provided, size each image so the slideshow matches the narration length.
  if (args.audio && existsSync(args.audio)) {
    const ad = getAudioDuration(args.audio);
    if (ad) { args.duration = ad / files.length; console.log(`audio ${ad.toFixed(1)}s -> ${args.duration.toFixed(2)}s/image`); }
  }

  const tmp = join(args.images, "_clips");
  mkdirSync(tmp, { recursive: true });

  const clips = [];
  files.forEach((f, i) => {
    const num = i + 1;
    const shot = shots[num] || {};
    const clip = join(tmp, `clip-${String(num).padStart(3, "0")}.mp4`);
    const vf = buildFilter(shot, args);
    const cmd = ["-y", "-loop", "1", "-i", join(args.images, f), "-vf", vf, "-t", String(args.duration), "-r", String(args.fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", clip];
    console.log(`encoding ${f} (${num}/${files.length})  motion=${shot.motion || "none"}  text=${shot.text ? "yes" : "no"}`);
    run(cmd);
    clips.push(clip);
  });

  const listFile = join(tmp, "concat.txt");
  writeFileSync(listFile, clips.map(c => `file '${c.replace(/\\/g, "/").replace(/'/g, "'\\''")}'`).join("\n") + "\n");

  const audioArgs = args.audio && existsSync(args.audio) ? ["-i", args.audio, "-c:a", "aac", "-shortest"] : ["-an"];
  console.log("concatenating...");
  run(["-y", "-f", "concat", "-safe", "0", "-i", listFile, ...audioArgs, "-c:v", "copy", args.out]);
  console.log("Wrote " + args.out);
}

main();
