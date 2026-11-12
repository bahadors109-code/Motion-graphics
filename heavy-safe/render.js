// Renders index.html frame-by-frame with Playwright, pipes JPEGs into ffmpeg,
// then mixes music + SFX (+ the English voice-over once assets/narration-en.mp3 exists).
// Usage:
//   node render.js                    -> output/heavy-safe.mp4
//   node render.js --mux-only         -> re-mix audio onto the last rendered frames
//   node render.js --stills 2,9.5     -> build/still-<t>.jpg previews
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const FPS = 30;
const ROOT = __dirname;
const BUILD = path.join(ROOT, 'build');
const OUT = path.join(ROOT, '..', 'output', 'heavy-safe.mp4');
const SILENT = path.join(BUILD, 'video.mp4');
fs.mkdirSync(BUILD, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });

// Voice-over phrases [audioStart, audioEnd, offsetIntoVideo, pitch?] — filled in once the ElevenLabs file arrives.
const NARRATION = { file: path.join(ROOT, 'assets', 'narration-en.mp3'), segs: [
  [0, 5.9, .5],                     // They had heard… / So they went straight for the safe.
  [5.9, 9.3, 2.22],                 // No matter what they tried, it wouldn't open.
  [9.3, 12.9, 1.91],                // In the end, they decided to take the whole safe.
  [12.9, 16.7, 5.94, .82],          // thief: All this weight… it must be full of gold!
  [16.7, 25.55, 16.6],              // The merchant had been expecting them…
  [25.55, 99, 17.49],               // The heaviest thing wasn't the most valuable.
] };

async function page() {
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await browser.newPage({ viewport: { width: 540, height: 960 } });
  p.on('pageerror', e => console.error('PAGE ERROR', e));
  await p.goto('file://' + path.join(ROOT, 'index.html') + '?static');
  await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  return { browser, p };
}
const grab = (p, t) => p.evaluate(t => { window.renderFrame(t); return document.getElementById('c').toDataURL('image/jpeg', 0.93).split(',')[1]; }, t);

async function stills(ts) {
  const { browser, p } = await page();
  for (const t of ts) fs.writeFileSync(path.join(BUILD, `still-${t}.jpg`), Buffer.from(await grab(p, t), 'base64'));
  await browser.close();
}

async function video() {
  const { browser, p } = await page();
  const duration = await p.evaluate(() => window.DURATION);
  const frames = Math.round(duration * FPS);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', SILENT], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let i = 0; i < frames; i++) {
    const buf = Buffer.from(await grab(p, i / FPS), 'base64');
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`frame ${i}/${frames}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  mux(duration);
}

function mux(duration = 47) {
  execFileSync('python3', [path.join(ROOT, 'music.py'), BUILD], { stdio: 'inherit' });
  const hasVoice = fs.existsSync(NARRATION.file);
  const inputs = ['-i', path.join(BUILD, 'music.wav'), '-i', path.join(BUILD, 'sfx.wav'), '-i', SILENT];
  let filter;
  if (hasVoice) {
    inputs.push('-i', NARRATION.file);
    const parts = NARRATION.segs.map(([a, b, o, pitch], k) =>
      `[3:a]atrim=${a}:${b},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,${pitch ? `asetrate=${Math.round(44100 * pitch)},aresample=44100,atempo=${(1 / pitch).toFixed(4)},` : ''}adelay=${Math.round((a + o) * 1000)}|${Math.round((a + o) * 1000)}[n${k}]`);
    filter = [...parts,
      `${NARRATION.segs.map((_, k) => `[n${k}]`).join('')}amix=inputs=${NARRATION.segs.length}:normalize=0:duration=longest,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=${duration},acompressor=threshold=0.06:ratio=4:attack=5:release=120:makeup=2,equalizer=f=3000:t=q:w=1:g=3,volume=2.1,asplit=2[voice][key]`,
      `[0:a]volume=0.22[mus]`, `[mus][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=500[duck]`, `[1:a]volume=0.32[fx]`,
      `[voice][duck][fx]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-11:TP=-1:LRA=8,aresample=44100[a]`].join(';');
  } else {
    filter = `[0:a]volume=0.6[mus];[1:a]volume=0.5[fx];[mus][fx]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[a]`;
  }
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filter, '-map', '2:v', '-map', '[a]',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', String(duration),
    '-movflags', '+faststart', OUT], { stdio: 'inherit' });
  console.log('wrote', OUT, hasVoice ? '(with voice-over)' : '(music + sfx only)');
}

const si = process.argv.indexOf('--stills');
if (process.argv.includes('--mux-only')) mux();
else if (si > 0) stills(process.argv[si + 1].split(',').map(Number)).catch(e => { console.error(e); process.exit(1); });
else video().catch(e => { console.error(e); process.exit(1); });
