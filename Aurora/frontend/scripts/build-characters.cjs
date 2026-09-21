/**
 * Builds the web-ready character art in public/characters/ from the raw
 * transparent PNGs in aura-project-assests/. Ported from the design project's
 * sprite builders (_alpha.js / _buildchar.js / _face.js) so the output honours
 * the same contract:
 *
 *  - sprites: 700x680 canvas, figure ~600px tall, feet pinned at (350, 668),
 *    ONE scale per character (median figure height) so poses crossfade without
 *    the body changing size. Frames can arrive at mixed resolutions, so the
 *    scale is normalised to a 1376px-wide reference frame.
 *  - faces: 3 expressions per character cropped to ONE shared square box so
 *    only the mouth moves when they crossfade.
 *  - scenarios: two-character vignettes trimmed to their content box, native
 *    aspect kept.
 *
 * Run: node scripts/build-characters.cjs   (from frontend/)
 * Output is WebP with alpha — visually the same as the PNG deliveries at a
 * fraction of the size.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "aura-project-assests");
const OUT = path.join(__dirname, "..", "public", "characters");

const CW = 700, CH = 680, FX = 350, FY = 668, TARGET = 600, REF_W = 1376;
const ALPHA_MIN = 40;
const WEBP = { quality: 90, alphaQuality: 100, effort: 5 };

const CAST = {
  eida:   { dir: "Eida",   prefix: "",       sig: "eida_signature.png" },
  maya:   { dir: "Maya",   prefix: "maya_",  sig: "maya_signature.png" },
  amy:    { dir: "Amy",    prefix: "",       sig: "amy_signature.png" },
  ryan:   { dir: "Ryan",   prefix: "ryan_",  sig: "ryan_signature.png" },
  alan:   { dir: "Alan",   prefix: "",       sig: "alan_signature.png" },
  lessac: { dir: "Lessak", prefix: "",       sig: "lessak_Signature.png" },
};

// output pose -> candidate raw file stems (the raw folders are inconsistently named)
const POSES = {
  idle: ["idle"],
  idle_angled: ["idle_angled", "idle_angle"],
  laughing: ["laughing"],
  listening: ["listening"],
  talking_emphatic: ["talking_ampathic", "talking_emphatic"],
  talking_open: ["talking_open"],
  thinking: ["thinking", "think"],
  wave: ["wave"],
};

const FACES = { neutral: ["neutral"], smiling: ["laughing", "laugh"], speaking: ["talking"] };

const SCENARIOS = {
  casual: "casual_Scenario.png",
  interview: "interview_scenario.png",
  travel: "travel_scenario.png",
  debate: "debate_Scenario.png",
  seminar: "explanation_sceanrio.png",
  cafe: "cafe_scenario.png",
  phone: "call_sceanrio.png",
};

function findFile(dir, prefix, stems) {
  for (const stem of stems) {
    const p = path.join(dir, `${prefix}${stem}.png`);
    if (fs.existsSync(p)) return p;
  }
  throw new Error(`no file for ${stems.join("/")} in ${dir}`);
}

async function load(file) {
  const { data, info } = await sharp(file).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  return { file, data, W: info.width, H: info.height, m: metrics(data, info.width, info.height) };
}

// Silhouette bounds plus the feet centre (mean midpoint of the bottom 3% of rows).
function metrics(d, W, H) {
  const rowA = new Array(H).fill(-1), rowB = new Array(H).fill(-1);
  let x0 = W, y0 = H, x1 = 0, y1 = 0;
  for (let y = 0; y < H; y++) {
    let a = -1, b = -1;
    const base = y * W * 4;
    for (let x = 0; x < W; x++) if (d[base + x * 4 + 3] > ALPHA_MIN) { if (a < 0) a = x; b = x; }
    rowA[y] = a; rowB[y] = b;
    if (a >= 0) { if (a < x0) x0 = a; if (b > x1) x1 = b; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  }
  const from = Math.max(y0, y1 - Math.round((y1 - y0) * 0.03));
  let sum = 0, n = 0;
  for (let y = from; y <= y1; y++) if (rowA[y] >= 0) { sum += (rowA[y] + rowB[y]) / 2; n++; }
  return { x0, y0, x1, y1, h: y1 - y0 + 1, feetCx: n ? sum / n : (x0 + x1) / 2, feetY: y1 };
}

/**
 * Draws `frame` scaled by `s` onto a transparent cw x ch canvas with the
 * scaled image's top-left at (left, top), clipping whatever falls outside.
 */
async function drawScaled(frame, s, left, top, cw, ch, out) {
  const w2 = Math.max(1, Math.round(frame.W * s)), h2 = Math.max(1, Math.round(frame.H * s));
  const resized = await sharp(frame.file).ensureAlpha().resize(w2, h2, { kernel: "lanczos3" }).png().toBuffer();
  const L = Math.round(left), T = Math.round(top);
  const ix0 = Math.max(0, L), iy0 = Math.max(0, T);
  const ix1 = Math.min(cw, L + w2), iy1 = Math.min(ch, T + h2);
  let layers = [];
  if (ix1 > ix0 && iy1 > iy0) {
    const piece = await sharp(resized)
      .extract({ left: ix0 - L, top: iy0 - T, width: ix1 - ix0, height: iy1 - iy0 })
      .png().toBuffer();
    layers = [{ input: piece, left: ix0, top: iy0 }];
  }
  await sharp({ create: { width: cw, height: ch, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite(layers)
    .webp(WEBP)
    .toFile(out);
}

const median = (vals) => { const s = vals.slice().sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

async function buildSprites(id, cfg) {
  const dir = path.join(SRC, "Step 4 — Core pose set, all six", cfg.dir);
  const frames = {};
  for (const [pose, stems] of Object.entries(POSES)) frames[pose] = await load(findFile(dir, cfg.prefix, stems));
  frames.signature = await load(path.join(SRC, "Step 7 — Signature poses", cfg.sig));

  // One scale per character, from the median CORE figure height, normalised
  // to the reference frame width so mixed-resolution sheets land at one size.
  const core = Object.keys(POSES).map((p) => frames[p]);
  const base = TARGET / median(core.map((f) => f.m.h * (REF_W / f.W)));

  const report = [];
  for (const [pose, f] of Object.entries(frames)) {
    const s = base * (REF_W / f.W);
    await drawScaled(f, s, FX - f.m.feetCx * s, FY - f.m.feetY * s, CW, CH,
      path.join(OUT, "sprites", `${id}_${pose}.webp`));
    report.push(`${pose}:${Math.round(f.m.h * s)}`);
  }
  console.log(`sprites ${id.padEnd(6)} scale=${base.toFixed(4)} ${report.join(" ")}`);
}

async function buildFaces(id, cfg, S = 320) {
  const dir = path.join(SRC, "Step 2 — Headshots", cfg.dir);
  const exprs = {};
  for (const [expr, stems] of Object.entries(FACES)) {
    // headshot filenames always carry the character prefix (the raw folder spells Lessac "lessak")
    const f = await load(findFile(dir, `${id === "lessac" ? "lessak" : id}_`, stems));
    exprs[expr] = { ...f, n: { x0: f.m.x0 / f.W, x1: f.m.x1 / f.W, y0: f.m.y0 / f.W, y1: f.m.y1 / f.W } };
  }
  const list = Object.values(exprs);
  // Tightest horizontal extent, median vertical — see the note in _face.js.
  const x0 = Math.max(...list.map((f) => f.n.x0)), x1 = Math.min(...list.map((f) => f.n.x1));
  const y0 = median(list.map((f) => f.n.y0)), y1 = median(list.map((f) => f.n.y1));
  const w = x1 - x0, h = y1 - y0;
  const side = Math.max(w, h) * 1.06;
  const cx = (x0 + x1) / 2, cy = y0 + h * 0.46;
  const sx = cx - side / 2, sy = cy - side / 2;
  for (const [expr, f] of Object.entries(exprs)) {
    const k = S / (side * f.W);
    await drawScaled(f, k, -sx * f.W * k, -sy * f.W * k, S, S, path.join(OUT, "faces", `${id}_${expr}.webp`));
  }
  console.log(`faces   ${id.padEnd(6)} side=${side.toFixed(3)}`);
}

async function buildScenarios() {
  for (const [key, file] of Object.entries(SCENARIOS)) {
    const f = await load(path.join(SRC, "Step 9 — Scenario poses", file));
    const { x0, y0, x1, y1 } = f.m;
    const width = x1 - x0 + 1, height = y1 - y0 + 1;
    // Displayed at <= ~400px tall, so cap the long side to keep the payload sane.
    const cap = Math.min(1, 1100 / Math.max(width, height));
    await sharp(f.file).ensureAlpha()
      .extract({ left: x0, top: y0, width, height })
      .resize(Math.round(width * cap), Math.round(height * cap), { kernel: "lanczos3" })
      .webp(WEBP)
      .toFile(path.join(OUT, "scenes", `${key}.webp`));
    console.log(`scene   ${key.padEnd(9)} ${Math.round(width * cap)}x${Math.round(height * cap)} aspect=${(width / height).toFixed(2)}`);
  }
}

(async () => {
  for (const d of ["sprites", "faces", "scenes"]) fs.mkdirSync(path.join(OUT, d), { recursive: true });
  for (const [id, cfg] of Object.entries(CAST)) {
    await buildSprites(id, cfg);
    await buildFaces(id, cfg);
  }
  await buildScenarios();
})().catch((e) => { console.error(e); process.exit(1); });
