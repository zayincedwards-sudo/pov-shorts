#!/usr/bin/env node
// YouTube channel audit helper — pulls channel + video stats via the YouTube Data API v3.
// Uses only Node.js built-ins (fetch is global in Node 18+).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const API = "https://www.googleapis.com/youtube/v3";

function parseArgs(argv) {
  const args = { channel: null, max: 50, out: null, apiKey: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--channel") args.channel = argv[++i];
    else if (a === "--max") args.max = parseInt(argv[++i], 10) || 50;
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--api-key") args.apiKey = argv[++i];
    else if (a === "--help" || a === "-h") { printHelp(); process.exit(0); }
    else { console.error("Unknown arg: " + a); printHelp(); process.exit(2); }
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node audit.mjs --channel <@handle|id|url> [--max 50] [--out dir]

  --channel   YouTube channel handle (@name), channel ID, or URL. Required.
  --max       Max videos to analyze (default 50).
  --out       Output directory (default ./audit).

  API key is read from ~/.deepcode-plus/settings.json (env.YOUTUBE_API_KEY),
  the YOUTUBE_API_KEY environment variable, or --api-key.`);
}

function readApiKey(args) {
  if (args.apiKey) return args.apiKey;
  if (process.env.YOUTUBE_API_KEY) return process.env.YOUTUBE_API_KEY;
  const p = join(homedir(), ".deepcode-plus", "settings.json");
  if (existsSync(p)) {
    try {
      const c = JSON.parse(readFileSync(p, "utf8"));
      if (c?.env?.YOUTUBE_API_KEY) return c.env.YOUTUBE_API_KEY;
    } catch {}
  }
  return null;
}

function extractHandleOrId(input) {
  input = (input || "").trim();
  const m = input.match(/youtube\.com\/(?:@|channel\/|c\/|user\/)([A-Za-z0-9_.\-]+)/);
  if (m) {
    const seg = m[1];
    return input.includes("/channel/") || seg.startsWith("UC") ? { id: seg } : { handle: "@" + seg };
  }
  if (input.startsWith("@")) return { handle: input };
  if (input.startsWith("UC")) return { id: input };
  return { handle: "@" + input };
}

async function yt(path, params, key) {
  const qs = new URLSearchParams(params);
  const url = `${API}/${path}?${qs.toString()}&key=${encodeURIComponent(key)}`;
  const r = await fetch(url);
  const j = await r.json();
  if (!r.ok) throw new Error(`YouTube API ${path} failed (${r.status}): ${j.error?.message || JSON.stringify(j)}`);
  return j;
}

function engagement(v) {
  const views = parseInt(v.statistics?.viewCount || "0", 10);
  const likes = parseInt(v.statistics?.likeCount || "0", 10);
  const comments = parseInt(v.statistics?.commentCount || "0", 10);
  const eng = views > 0 ? (likes + comments) / views : 0;
  return { views, likes, comments, eng };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.channel) { console.error("--channel is required.\n"); printHelp(); process.exit(2); }
  const key = readApiKey(args);
  if (!key) { console.error("No YouTube API key. Set env.YOUTUBE_API_KEY in ~/.deepcode-plus/settings.json."); process.exit(1); }

  const target = extractHandleOrId(args.channel);
  let channel;
  if (target.id) {
    channel = (await yt("channels", { part: "snippet,statistics,contentDetails", id: target.id, maxResults: 1 }, key)).items?.[0];
  } else {
    channel = (await yt("channels", { part: "snippet,statistics,contentDetails", forHandle: target.handle, maxResults: 1 }, key)).items?.[0];
  }
  if (!channel) { console.error("Channel not found: " + args.channel); process.exit(1); }

  const uploads = channel.contentDetails?.relatedPlaylists?.uploads;
  const channelTitle = channel.snippet?.title;
  const subCount = channel.statistics?.subscriberCount;
  const totalViews = channel.statistics?.viewCount;
  const totalVideos = channel.statistics?.videoCount;

  const videos = [];
  let pageToken;
  while (uploads && videos.length < args.max) {
    const params = { part: "snippet,contentDetails", playlistId: uploads, maxResults: 50 };
    if (pageToken) params.pageToken = pageToken;
    const pl = await yt("playlistItems", params, key);
    for (const item of pl.items || []) {
      if (videos.length >= args.max) break;
      if (!item.contentDetails?.videoId) continue;
      videos.push({
        id: item.contentDetails.videoId,
        title: item.snippet?.title || "(untitled)",
        publishedAt: item.contentDetails.videoPublishedAt || item.snippet?.publishedAt,
        thumb: item.snippet?.thumbnails?.medium?.url || item.snippet?.thumbnails?.default?.url,
      });
    }
    pageToken = pl.nextPageToken;
    if (!pageToken) break;
  }

  const ids = videos.map(v => v.id);
  for (let i = 0; i < ids.length; i += 50) {
    const batch = ids.slice(i, i + 50).join(",");
    const vd = await yt("videos", { part: "snippet,statistics,contentDetails", id: batch, maxResults: 50 }, key);
    for (const item of vd.items || []) {
      const v = videos.find(x => x.id === item.id);
      if (!v) continue;
      const e = engagement(item);
      v.views = e.views; v.likes = e.likes; v.comments = e.comments; v.eng = e.eng;
      v.duration = item.contentDetails?.duration;
      v.tags = item.snippet?.tags || [];
      v.description = (item.snippet?.description || "").slice(0, 500);
    }
  }

  const ranked = videos.filter(v => v.views !== undefined).sort((a, b) => b.eng - a.eng);
  const winners = ranked.slice(0, 10);
  const losers = ranked.slice(-10).reverse();

  const outDir = args.out || "./audit";
  mkdirSync(outDir, { recursive: true });
  const summary = { channelTitle, subCount, totalViews, totalVideos, analyzedVideos: videos.length, winners, losers, all: ranked };
  writeFileSync(join(outDir, "audit.json"), JSON.stringify(summary, null, 2));

  let md = `# Channel Audit: ${channelTitle}\n\n`;
  md += `- Subscribers: ${subCount}\n- Total views: ${totalViews}\n- Videos: ${totalVideos} (analyzed ${videos.length})\n\n`;
  const row = (v) => `| ${String(v.title).replace(/\|/g, "\\|").slice(0, 70)} | ${v.views} | ${v.likes} | ${v.comments} | ${(v.eng * 100).toFixed(2)}% |`;
  md += `## Top videos (by engagement)\n\n| Title | Views | Likes | Comments | Eng% |\n|---|---|---|---|---|\n`;
  for (const v of winners) md += row(v) + "\n";
  md += `\n## Bottom videos\n\n| Title | Views | Likes | Comments | Eng% |\n|---|---|---|---|---|\n`;
  for (const v of losers) md += row(v) + "\n";
  writeFileSync(join(outDir, "audit.md"), md);

  console.log(`Channel: ${channelTitle} (${subCount} subs, ${totalVideos} videos)`);
  console.log(`Analyzed ${videos.length} videos.`);
  console.log(`Wrote ${join(outDir, "audit.json")} and ${join(outDir, "audit.md")}`);
  console.log("\nTop by engagement:");
  winners.slice(0, 5).forEach(v => console.log(`  ${(v.eng * 100).toFixed(2)}%  ${v.views} views  ${String(v.title).slice(0, 60)}`));
}

main().catch(e => { console.error("Error: " + e.message); process.exit(1); });
