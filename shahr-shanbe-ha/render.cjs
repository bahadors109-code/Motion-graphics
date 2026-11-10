// Render index.html to MP4 (1080x1920, 30fps) — usage: node render.cjs [out.mp4] [fps]
const {chromium}=require('playwright');const {spawn}=require('child_process');const path=require('path');
const out=process.argv[2]||'shahr-shanbe-ha.mp4', FPS=+(process.argv[3]||30);
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
  ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();
  if(!require('fs').existsSync(path.resolve(__dirname,'assets/narration.mp3'))){console.log('done (no narration) →',out);return;}
  // mux narrator voice + background music (ducked under the voice)
  const tmp=out.replace(/\.mp4$/,'')+'.noaudio.mp4';require('fs').renameSync(out,tmp);
  const music=path.resolve(__dirname,'assets/music.mp3'), hasMusic=require('fs').existsSync(music);
  const args=['-y','-loglevel','error','-i',tmp,'-i',path.resolve(__dirname,'assets/narration.mp3')];
  let fc;
  if(hasMusic){args.push('-i',music);
    fc=`[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,asplit=2[v1][v2];[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.09,afade=t=out:st=${dur-2.5}:d=2.5[m];[m][v2]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=600[md];[v1][md]amix=inputs=2:normalize=0:duration=first,volume=2.2,alimiter=limit=0.95[a]`;}
  else fc='[1:a]apad[a]';
  args.push('-filter_complex',fc,'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-t',String(dur),'-movflags','+faststart',out);
  await new Promise(r=>spawn('ffmpeg',args,{stdio:'inherit'}).on('close',r));
  require('fs').unlinkSync(tmp);console.log('done →',out);
})();
