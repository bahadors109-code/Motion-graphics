// Renders index.html frame-by-frame with Playwright and pipes JPEGs into ffmpeg,
// then muxes narration (with a gap for the guard's line) + music + sfx.
// Usage:
//   node render.js                     -> output/border-smuggler.mp4
//   node render.js --stills 2,9,15     -> build/still-<t>.jpg previews
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const FPS = 30;
const li = process.argv.indexOf('--lang');
const LANG = li > 0 ? process.argv[li + 1] : 'fa';
const SUFFIX = LANG === 'fa' ? '' : '-' + LANG;
const ROOT = __dirname;
const BUILD = path.join(ROOT, 'build');
const OUT = path.join(ROOT, '..', 'output', `border-smuggler${SUFFIX}.mp4`);
fs.mkdirSync(BUILD, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });

async function page() {
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await browser.newPage({ viewport: { width: 540, height: 960 } });
  p.on('pageerror', e => console.error('PAGE ERROR', e));
  await p.goto('file://' + path.join(ROOT, 'index.html') + '?static&lang=' + LANG);
  await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  return { browser, p };
}
const grab = (p, t) => p.evaluate(t => { window.renderFrame(t); return document.getElementById('c').toDataURL('image/jpeg', 0.93).split(',')[1]; }, t);

async function stills(ts) {
  const { browser, p } = await page();
  for (const t of ts) fs.writeFileSync(path.join(BUILD, `still${SUFFIX}-${t}.jpg`), Buffer.from(await grab(p, t), 'base64'));
  await browser.close();
}

async function video() {
  const { browser, p } = await page();
  const duration = await p.evaluate(() => window.DURATION);
  const frames = Math.round(duration * FPS);
  const silent = path.join(BUILD, `video${SUFFIX}.mp4`);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', silent], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    const buf = Buffer.from(await grab(p, i / FPS), 'base64');
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 60 === 0) console.log(`frame ${i}/${frames}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();

  await mux(duration);
}

// audio: narration split at 22.1s so the guard's line gets a 2.6s gap,
// music ducked under the voice, then loudness-normalised to -15 LUFS.
async function mux(duration = 43) {
  const silent = path.join(BUILD, `video${SUFFIX}.mp4`);
  execFileSync('python3', [path.join(ROOT, 'music.py'), BUILD], { stdio: 'inherit' });
  // narration phrases: [audioStart, audioEnd, offset] — each phrase is moved onto its scene
  const NAR = {
    fa: { file: 'narration.mp3', segs: [[0, 22.1, 0.5], [22.1, 99, 3.1]] },
    en: { file: 'narration-en.mp3', segs: [[0, 12.65, 0.35], [12.65, 22.9, -0.15], [22.9, 25.1, 2.19], [25.1, 29.1, 2.73], [29.1, 30.64, 4.47], [30.64, 99, 6.12]] },
  }[LANG];
  const nar = path.join(ROOT, 'assets', NAR.file);
  const parts = NAR.segs.map(([a, b, o], k) =>
    `[0:a]atrim=${a}:${b},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,adelay=${Math.round((a + o) * 1000)}|${Math.round((a + o) * 1000)}[n${k}]`);
  const filter = [
    ...parts,
    `${NAR.segs.map((_, k) => `[n${k}]`).join('')}amix=inputs=${NAR.segs.length}:normalize=0:duration=longest,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=${duration},asplit=2[voice][key]`,
    `[1:a]volume=0.5[mus]`,
    `[mus][key]sidechaincompress=threshold=0.05:ratio=3:attack=30:release=450[duck]`,
    `[2:a]volume=0.45[fx]`,
    `[voice][duck][fx]amix=inputs=3:normalize=0:duration=first,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=44100[a]`,
  ].join(';');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', nar, '-i', path.join(BUILD, 'music.wav'), '-i', path.join(BUILD, 'sfx.wav'), '-i', silent,
    '-filter_complex', filter, '-map', '3:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k', '-t', String(duration), '-movflags', '+faststart', OUT], { stdio: 'inherit' });
  console.log('wrote', OUT);
}

const i = process.argv.indexOf('--stills');
if (process.argv.includes('--mux-only')) mux().catch(e => { console.error(e); process.exit(1); });
else if (i > 0) stills(process.argv[i + 1].split(',').map(Number)).catch(e => { console.error(e); process.exit(1); });
else video().catch(e => { console.error(e); process.exit(1); });
