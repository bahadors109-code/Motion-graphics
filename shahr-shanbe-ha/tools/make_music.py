# Generates a soft, warm background loop (assets/music.wav) — original, synthesized.
# Gentle pads + music-box arpeggio + soft kick/shaker, C major, I–vi–IV–V, 96 BPM.
import numpy as np, wave, sys
SR=44100; DUR=float(sys.argv[1]) if len(sys.argv)>1 else 36.0; BPM=96; B=60/BPM
n=int(SR*DUR); t=np.arange(n)/SR; L=np.zeros(n); Rr=np.zeros(n)
mid=lambda m:440*2**((m-69)/12)
chords=[[48,55,60,64,67],[45,52,57,60,64],[41,48,53,57,60],[43,50,55,59,62]]  # C Am F G
bar=4*B
def add(sig,start,pan=0.0,gain=1.0):
    i=int(start*SR); j=min(n,i+len(sig)); 
    if i>=n: return
    s=sig[:j-i]*gain; L[i:j]+=s*(1-pan)/1; Rr[i:j]+=s*(1+pan)/1
# pads
for k in range(int(DUR/bar)+1):
    ch=chords[k%4]; st=k*bar; d=bar+0.6; tt=np.arange(int(d*SR))/SR
    env=np.minimum(1,tt/0.9)*np.minimum(1,(d-tt)/0.8)
    for m in ch[1:]:
        f=mid(m); s=(np.sin(2*np.pi*f*tt)+0.5*np.sin(2*np.pi*f*1.003*tt+1)+0.25*np.sin(2*np.pi*2*f*tt))*env
        add(s,st,pan=((m%5)-2)*0.15,gain=0.035)
    f=mid(ch[0]-12+12); add(np.sin(2*np.pi*f*tt)*env,st,gain=0.06)   # soft bass
# music-box arpeggio (8ths)
pat=[0,2,3,4,3,2,1,2]
for k in range(int(DUR/(B/2))):
    st=k*B/2; ch=chords[int(st//bar)%4]; m=ch[1:][pat[k%8]%4]+12
    if st<2.0: continue
    d=1.4; tt=np.arange(int(d*SR))/SR; f=mid(m)
    env=np.exp(-tt*4.5)*np.minimum(1,tt/0.004)
    s=(np.sin(2*np.pi*f*tt)+0.3*np.sin(2*np.pi*3*f*tt)*np.exp(-tt*9))*env
    add(s,st,pan=0.35 if k%2 else -0.35,gain=0.05)
# soft kick on 1 & 3, shaker on offbeats (from bar 2)
rng=np.random.default_rng(3)
for k in range(int(DUR/B)):
    st=k*B
    if st<bar: continue
    if k%2==0:
        tt=np.arange(int(.35*SR))/SR; f=55+60*np.exp(-tt*30)
        add(np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt*12),st,gain=0.10)
    tt=np.arange(int(.08*SR))/SR; nz=rng.standard_normal(len(tt)); nz=np.diff(np.concatenate([[0],nz]))
    add(nz*np.exp(-tt*60),st+B/2,pan=0.2,gain=0.012)
# master: fade in/out, normalize
fade=np.minimum(1,t/1.5)*np.minimum(1,(DUR-t)/3.0)
L*=fade; Rr*=fade; pk=max(np.abs(L).max(),np.abs(Rr).max()); L/=pk/0.8; Rr/=pk/0.8
out=np.stack([L,Rr],1); out=(out*32767).astype(np.int16)
with wave.open(sys.argv[2] if len(sys.argv)>2 else 'music.wav','wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
