// Renders index.html frame-by-frame with Playwright, pipes JPEGs into ffmpeg,
// then mixes music + SFX (+ the English voice-over once assets/narration-en.mp3 exists).
// Usage:
//   node render.js                    -> output/the-bait.mp4
//   node render.js --mux-only         -> re-mix audio onto the last rendered frames
//   node render.js --stills 2,9.5     -> build/still-<t>.jpg previews
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const FPS = 30;
const ROOT = __dirname;
const BUILD = path.join(ROOT, 'build');
const OUT = path.join(ROOT, '..', 'output', 'the-bait.mp4');
const SILENT = path.join(BUILD, 'video.mp4');
fs.mkdirSync(BUILD, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });

// Voice-over phrases [audioStart, audioEnd, offsetIntoVideo, pitch?] — filled in once the ElevenLabs file arrives.
const NARRATION = { file: path.join(ROOT, 'assets', 'narration-en.mp3'), segs: [
  [0, 5.1, .5],                     // Out of all the passengers…
  [5.1, 7.7, .9],                   // A few seconds were all he needed.
  [7.7, 11.0, 1.63],                // He grabbed the suitcase… (on the grab)
  [11.0, 14.9, 4.55],               // He was expecting cash. Maybe even jewelry… (with the thought bubble)
  [14.9, 23.0, 17.93],              // The police were hunting someone…
  [23.0, 99, 19.2],                 // This time, the bait was waiting for the thief.
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

function mux(duration = 46.5) {
  execFileSync('python3', [path.join(ROOT, 'music.py'), BUILD], { stdio: 'inherit' });
  const hasVoice = fs.existsSync(NARRATION.file);
  const inputs = ['-i', path.join(BUILD, 'music.wav'), '-i', path.join(BUILD, 'sfx.wav'), '-i', SILENT];
  let filter;
  if (hasVoice) {
    inputs.push('-i', NARRATION.file);
    const parts = NARRATION.segs.map(([a, b, o, pitch], k) =>
      `[3:a]atrim=${a}:${b},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,${pitch ? `asetrate=${Math.round(44100 * pitch)},aresample=44100,atempo=${(1 / pitch).toFixed(4)},` : ''}adelay=${Math.round((a + o) * 1000)}|${Math.round((a + o) * 1000)}[n${k}]`);
    filter = [...parts,
      `${NARRATION.segs.map((_, k) => `[n${k}]`).join('')}amix=inputs=${NARRATION.segs.length}:normalize=0:duration=longest,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=${duration},acompressor=threshold=0.08:ratio=3:attack=5:release=120:makeup=1.6,volume=1.25,asplit=2[voice][key]`,
      `[0:a]volume=0.32[mus]`, `[mus][key]sidechaincompress=threshold=0.04:ratio=4:attack=25:release=500[duck]`, `[1:a]volume=0.35[fx]`,
      `[voice][duck][fx]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=44100[a]`].join(';');
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
