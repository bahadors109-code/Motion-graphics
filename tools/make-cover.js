// node tools/make-cover.js <project-dir> <out-name> [extra query, e.g. lang=en] [--grid]
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const [dir, out, q = ''] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage();
  p.on('pageerror', e => console.error('PAGE ERROR', e));
  await p.goto('file://' + path.resolve(dir, 'index.html') + '?static' + (q ? '&' + q : ''));
  await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  const png = await p.evaluate(() => { window.renderCover(); return document.getElementById('c').toDataURL('image/png').split(',')[1]; });
  fs.writeFileSync(path.resolve(__dirname, '..', 'output', out + '.png'), Buffer.from(png, 'base64'));
  await b.close();
})();
