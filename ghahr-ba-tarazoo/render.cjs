// Render index.html to MP4 (1080x1920, 30fps) — usage: node render.cjs [out.mp4] [fps]
const {chromium}=require('playwright');const {spawn}=require('child_process');const path=require('path');
const out=process.argv[2]||'ghahr-ba-tarazoo.mp4', FPS=+(process.argv[3]||30);
(async()=>{
  const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1080,height:1920}});
  await pg.goto('file://'+path.resolve(__dirname,'index.html')+'?render=1');
  await pg.waitForFunction(()=>window.__ready);
  const dur=await pg.evaluate(()=>window.DUR), n=Math.round(dur*FPS);
  const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(FPS),'-i','-',
    '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',out],{stdio:['pipe','inherit','inherit']});
  for(let i=0;i<n;i++){
    await pg.evaluate(t=>renderAt(t),i/FPS);
    const buf=await pg.screenshot({type:'png'});
    if(!ff.stdin.write(buf)) await new Promise(r=>ff.stdin.once('drain',r));
    if(i%60===0) process.stdout.write(`frame ${i}/${n}\n`);
  }
  ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();console.log('done →',out);
})();
