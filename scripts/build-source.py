import argparse,concurrent.futures,hashlib,json,os,pathlib,subprocess,tempfile,time,urllib.request,urllib.parse
import fitz
from PIL import Image
P=pathlib.Path;ROOT=P.cwd();args=argparse.ArgumentParser();args.add_argument('--start',type=int,required=True);args.add_argument('--end',type=int,required=True);a=args.parse_args()
parts=json.loads((ROOT/'source-parts.json').read_text());assert parts['complete'] and len(parts['parts'])==24
source_sha=hashlib.sha256(json.dumps(parts['parts'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
base='https://raw.githubusercontent.com/aokid666/zz-suyi-manual-2027-1/main/'
public='https://aokid666.github.io/'+os.environ['GITHUB_REPOSITORY'].split('/')[1]+'/'
(ROOT/'img/suyi').mkdir(parents=True,exist_ok=True);(ROOT/'data').mkdir(exist_ok=True)
jobs=[]
def digest(b):return hashlib.sha256(b).hexdigest()
with tempfile.TemporaryDirectory() as tmp:
 for part in parts['parts']:
  if part['endPage']<a.start or part['startPage']>a.end:continue
  path=P(tmp)/P(part['file']).name
  for attempt in range(4):
   try:
    with urllib.request.urlopen(base+urllib.parse.quote(part['file']),timeout=180) as r:raw=r.read()
    assert digest(raw)==part['sha256'] and len(raw)==part['bytes'];path.write_bytes(raw);break
   except Exception:
    if attempt==3:raise
    time.sleep(3)
  doc=fitz.open(path);assert len(doc)==part['pageCount']
  for i,pg in enumerate(doc):
   n=part['startPage']+i
   if not a.start<=n<=a.end:continue
   images=pg.get_images(full=True);assert len(images)==1,(n,'not a single embedded scan')
   img=images[0];pix=fitz.Pixmap(doc,img[0]);assert pix.n==3 and not pix.alpha,(n,'unexpected image color space')
   im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);rgb_hash=digest(im.tobytes());alpha_hash=None
   if img[1]:
    mask=fitz.Pixmap(doc,img[1]);assert (mask.width,mask.height)==im.size and mask.n==1
    alpha_hash=digest(mask.samples)
    if mask.samples!=b'\xff'*len(mask.samples):im.putalpha(Image.frombytes('L',im.size,mask.samples))
   out=ROOT/f'img/suyi/{n:04}.png';im.save(out,format='PNG')
   with Image.open(out) as check:assert check.size==im.size and digest(check.convert('RGB').tobytes())==rgb_hash,(n,'original RGB pixels changed')
   rects=pg.get_image_rects(img[0]);assert len(rects)==1
   rect=rects[0];box=[rect.x0/pg.rect.width,rect.y0/pg.rect.height,rect.width/pg.rect.width,rect.height/pg.rect.height]
   jobs.append(dict(page=n,width=pg.rect.width,height=pg.rect.height,pixelWidth=pix.width,pixelHeight=pix.height,imageBox=box,url=public+str(out.relative_to(ROOT)),sha256=digest(out.read_bytes()),bytes=out.stat().st_size,imageMethod='embedded-original-pixels-lossless',originalRgbSha256=rgb_hash,originalAlphaSha256=alpha_hash,pdfUrl='https://aokid666.github.io/zz-suyi-manual-2027-1/'+urllib.parse.quote(part['file']),pdfPage=i+1,pdfSha256=part['sha256'],pdfPart=part['file'],text=pg.get_text().strip()))
  print('Extracted original pixels:',part['file'],flush=True)
 def ocr(row):
  if not row['text']:
   env=os.environ.copy();env['OMP_THREAD_LIMIT']='1'
   r=subprocess.run(['tesseract',str(ROOT/f"img/suyi/{row['page']:04}.png"),'stdout','-l','chi_sim+eng','--psm','3'],capture_output=True,text=True,env=env,timeout=150)
   assert r.returncode==0,(row['page'],r.stderr[-500:]);row['text']=r.stdout.strip();row['textMethod']='ocr-tesseract-chi_sim-eng'
  else:row['textMethod']='pdf-text'
  if row['page']%10==0:print('OCR complete:',row['page'],flush=True)
  return row
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:pages=list(pool.map(ocr,jobs))
pages.sort(key=lambda p:p['page']);assert [p['page'] for p in pages]==list(range(a.start,a.end+1))
assert sum(bool(p['text']) for p in pages)>len(pages)*.85
out={'source':{'id':'suyi-manual-2027','title':'苏一提分手册','sha256':source_sha},'startPage':a.start,'endPage':a.end,'pages':pages,'parts':parts['parts']}
(ROOT/'data/source.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
(ROOT/'.nojekyll').write_text('')
print('Validated source range:',a.start,a.end,'pages',len(pages),'image bytes',sum(p['bytes'] for p in pages),flush=True)
