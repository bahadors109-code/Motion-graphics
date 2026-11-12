const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const root = path.resolve(__dirname, '..');
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] }); const p = await b.newPage();
  p.on('pageerror', e => console.error('PAGE ERROR', e));
  await p.goto('file://' + path.join(root, 'index.html') + '?static');
  await p.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  const style = process.argv[2] || '1';
  const png = await p.evaluate(s => { (s === '2' ? window.renderCover2 : window.renderCover)(); return document.getElementById('c').toDataURL('image/png').split(',')[1]; }, style);
  fs.writeFileSync(path.join(root, '..', 'output', style === '2' ? 'missing-nail-cover-2.png' : 'missing-nail-cover.png'), Buffer.from(png, 'base64'));
  await b.close();
})();
