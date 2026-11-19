const $ = id => document.getElementById(id);
let image = null, imageData = null, objects = [], focusPoints = [], start = null, busy = false;
const canvas = $('canvas'), ctx = canvas.getContext('2d');
function message(text) { $('status').textContent = text; }
function refresh() {
  $('generate').disabled = busy || !image || !objects.length;
  $('objects').replaceChildren();
  const entries=[...objects.map((obj,i)=>({obj,i,kind:'defect'})),...focusPoints.map((obj,i)=>({obj,i,kind:'context'}))];
  entries.forEach(({obj,i,kind}) => {
    const row=document.createElement('div');row.className='row';
    const text=document.createElement('span');text.textContent=`${kind==='defect'?'Д':'Т'}${i+1}. ${obj.label} · [${obj.bbox.join(', ')}]`;
    text.style.color=kind==='defect'?'#60ffb8':'#ffbd66';
    const change=document.createElement('button');change.textContent=kind==='defect'?'В точку':'В дефект';change.disabled=busy;
    change.onclick=()=>{const from=kind==='defect'?objects:focusPoints,to=kind==='defect'?focusPoints:objects;to.push(from.splice(i,1)[0]);refresh();draw();};
    const remove=document.createElement('button');remove.textContent='×';remove.className='remove';remove.disabled=busy;
    remove.setAttribute('aria-label',`Удалить ${obj.label}`);
    remove.onclick=()=>{(kind==='defect'?objects:focusPoints).splice(i,1);refresh();draw();};
    row.append(text,change,remove);$('objects').append(row);
  });
  const targetCount=objects.length+($('useFocus').checked?focusPoints.length:0)+Number($('overview').checked);
  $('focusSummary').textContent=(focusPoints.length&&$('useFocus').checked)||$('overview').checked?`Целей осмотра: ${targetCount}. Минимальная длительность: ${4*targetCount} с. На каждой точке — фиксация 2 с.`:'Дополнительные точки необязательны. Без них используется обычный маршрут.';

}
function draw(draft) {
  if (!image) return;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  const sx = canvas.width/image.naturalWidth, sy = canvas.height/image.naturalHeight;
  const entries=[...objects.map((o,i)=>({...o,tag:`Д${i+1}`,kind:'defect'})),...focusPoints.map((o,i)=>({...o,tag:`Т${i+1}`,kind:'context'})),...(draft?[{bbox:draft,tag:'',kind:$('boxKind').value}]:[])];
  entries.forEach(obj=>{
    const [x1,y1,x2,y2]=obj.bbox;
    ctx.strokeStyle=obj.kind==='defect'?'#60ffb8':'#ffbd66';ctx.lineWidth=2;
    ctx.strokeRect(x1*sx,y1*sy,(x2-x1)*sx,(y2-y1)*sy);
    ctx.fillStyle=ctx.strokeStyle;ctx.font='16px system-ui';ctx.fillText(obj.tag,x1*sx+4,y1*sy+19);
  });

}
function validBox(box) {
  return image && Array.isArray(box) && box.length === 4 && box.every(Number.isFinite) &&
    box[0]>=0 && box[1]>=0 && box[2]>box[0] && box[3]>box[1] && box[2]<=image.naturalWidth && box[3]<=image.naturalHeight;
}
function addBox(box, label) {
  const kind=$('boxKind').value;
  if(kind==='context'&&focusPoints.length>=14)throw new Error('Не больше 14 дополнительных точек осмотра.');
  if(kind==='context'&&!label.trim())label=`Точка осмотра ${focusPoints.length+1}`;
  if (!label.trim()) throw new Error('Введите название дефекта.');
  if (!validBox(box)) throw new Error('Проверьте bbox: x1 < x2, y1 < y2, координаты внутри исходного фото.');
  if (objects.length >= 100) throw new Error('Не больше 100 рамок.');
  (kind==='context'?focusPoints:objects).push({label: label.trim(), bbox: box}); refresh(); draw();
}
async function loadPhoto(file) {
    if (!file) return;
    if (file.size > 40*1024*1024) throw new Error('Максимальный размер фото — 40 МБ.');
    const data = await new Promise((resolve,reject) => { const r = new FileReader(); r.onload=()=>resolve(r.result); r.onerror=reject; r.readAsDataURL(file); });
    const loaded = new Image(); loaded.src = data; await loaded.decode();
    if (loaded.naturalWidth*loaded.naturalHeight>50000000 || Math.max(loaded.naturalWidth,loaded.naturalHeight)>16000) throw new Error('Максимум 50 Мп и 16000 px по стороне.');
    image = loaded; imageData = data; objects = []; focusPoints = [];
    canvas.width = Math.min(1400, image.naturalWidth); canvas.height = Math.round(canvas.width*image.naturalHeight/image.naturalWidth);
    canvas.style.display='block'; $('empty').hidden=true;
    $('dimensions').textContent=`Исходное фото: ${image.naturalWidth} × ${image.naturalHeight} px`;
    message('Введите название дефекта и нарисуйте рамку.'); refresh(); draw();
}
$('photo').onchange = async e => {try {await loadPhoto(e.target.files[0]);}catch(err){message(err.message);}};
function point(event) { const r=canvas.getBoundingClientRect(); return [Math.round(Math.max(0,Math.min(1,(event.clientX-r.left)/r.width))*image.naturalWidth),Math.round(Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))*image.naturalHeight)]; }
function rectangle(a,b) { return [Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0]),Math.max(a[1],b[1])]; }
canvas.onpointerdown = e => { if(!image||busy)return; start=point(e); canvas.setPointerCapture(e.pointerId); };
canvas.onpointermove = e => { if(start)draw(rectangle(start,point(e))); };
canvas.onpointerup = e => { if(!start)return; const box=rectangle(start,point(e)); start=null; try {addBox(box,$('label').value);}catch(err){message(err.message);draw();} };
canvas.onpointercancel = () => {start=null;draw();};
$('add').onclick = () => {try{addBox($('coords').value.split(/[\s,;]+/).filter(Boolean).map(Number),$('label').value);}catch(e){message(e.message);}};
async function importAnnotations(file) {
  if (!image) throw new Error('Сначала загрузите фото или перетащите фото и разметку вместе.');
  if (!file) return;
  if (file.size > 2_000_000) throw new Error('Разметка должна быть не больше 2 МБ.');
  const text=await file.text();
  let data;
  if (/\.xml$/i.test(file.name)) {
    const response=await fetch('/api/import-voc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({xml:text,width:image.naturalWidth,height:image.naturalHeight})});
    data=await response.json();if(!response.ok)throw new Error(data.error);
  } else { data=JSON.parse(text); }
  data.objects=data.objects??[];data.focus_points=data.focus_points??[];
  if(!Array.isArray(data.objects)||!Array.isArray(data.focus_points)||!data.objects.length&&!data.focus_points.length||data.objects.length+objects.length>100||data.focus_points.length+focusPoints.length>14)throw new Error('Проверьте массивы objects и focus_points (до 100 дефектов и 14 точек).');
  if(!data.objects.every(o=>typeof o.label==='string'&&o.label.trim()&&o.label.length<=160&&validBox(o.bbox)))throw new Error('Проверьте названия и координаты bbox в разметке.');
  if(!data.focus_points.every(o=>validBox(o.bbox)&&(!o.label||typeof o.label==='string'&&o.label.length<=160)))throw new Error('Проверьте дополнительные точки осмотра.');
  focusPoints.push(...data.focus_points.map((o,i)=>({label:o.label||`Точка осмотра ${focusPoints.length+i+1}`,bbox:o.bbox})));
  objects.push(...data.objects.map(o=>({label:o.label,bbox:o.bbox})));refresh();draw();message(`Импортировано ${data.objects.length} рамок из ${file.name}.`);
}
$('annotations').onchange = async e => {try{await importAnnotations(e.target.files[0]);}catch(err){message(err.message);}};
let importing=false;
async function acceptFiles(files) {
  if(busy||importing)return;
  importing=true;
  try{
    const list=Array.from(files), photos=list.filter(f=>/\.(jpe?g|png|webp)$/i.test(f.name)), labels=list.filter(f=>/\.(json|xml)$/i.test(f.name));
    if(photos.length>1)throw new Error('Перетаскивайте одно фото и его разметку за один раз.');
    if(list.length!==photos.length+labels.length)throw new Error('Поддерживаются JPEG, PNG, WebP, JSON и XML.');
    if(photos.length)await loadPhoto(photos[0]);
    for(const file of labels)await importAnnotations(file);
  }catch(err){message(err.message);}finally{importing=false;}
}
for (const id of ['stage','dropAnnotations']) {
  const zone=$(id);
  zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('dragover');});
  zone.addEventListener('dragleave',()=>zone.classList.remove('dragover'));
  zone.addEventListener('drop',e=>{e.preventDefault();e.stopPropagation();zone.classList.remove('dragover');acceptFiles(e.dataTransfer.files);});
}
window.addEventListener('dragover',e=>e.preventDefault());
window.addEventListener('drop',e=>{e.preventDefault();acceptFiles(e.dataTransfer.files);});
$('generate').onclick = async () => {
  busy=true; refresh(); $('result').hidden=true; $('progress').hidden=false; $('progress').value=0;
  document.querySelectorAll('input,select,#add,#shuffleSeed').forEach(e=>e.disabled=true);
  try {
    message('Загрузка и подготовка фото…');
    const response=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:imageData,objects,overview:$('overview').checked,blur_strength:Number($('blur').value)/100,noise_strength:Number($('noise').value)/100,focus_points:$('useFocus').checked?focusPoints:[],duration:Number($('duration').value),width:Number($('width').value),fps:Number($('fps').value),seed:Number($('seed').value),motion:$('motion').value,parallax_strength:Number($('parallax').value)})});
    const created=await response.json(); if(!response.ok)throw new Error(created.error);
    while(true){
      await new Promise(r=>setTimeout(r,800));
      const statusResponse=await fetch(`/api/jobs/${created.job_id}`);
      const job=await statusResponse.json(); if(!statusResponse.ok)throw new Error(job.error);
      $('progress').value=job.progress;
      message(`${job.stage || 'Обработка'} · ${job.progress}%`);
      if(job.status==='error')throw new Error(job.error);
      if(job.status==='done'){
        const base=`/output/${created.job_id}/`, meta=job.result;
        $('video').src=job.video_url; $('zip').href=job.url; $('mp4').href=job.video_url;
        $('json').href=base+'annotations.json'; $('tracks').href=base+'tracks.jsonl';
        $('metrics').textContent=`${meta.video.width} × ${meta.video.height} · ${meta.video.fps} FPS · ${meta.video.duration_s.toFixed(2)} с · ${meta.video.frame_count} кадров · генерация и проверка ${meta.generation_seconds.toFixed(1)} с`;
        $('depthResult').hidden=!meta.depth;
        if(meta.depth){$('depthImage').src=base+'depth_effective.png';$('depthRaw').href=base+'depth_raw.png';$('depthEffective').href=base+'depth_effective.png';}
        $('warnings').textContent=[...(meta.depth?.warnings || []),...(meta.flight_plan?.warnings || []),...meta.objects.filter(o=>o.keyframe_warning).map(o=>`${o.label}: ${o.keyframe_warning}`)].join(' ');
        $('keys').replaceChildren();
        meta.objects.forEach(o=>{if(!o.keyframe)return;const card=document.createElement('div'),img=document.createElement('img'),caption=document.createElement('p');img.src=base+o.keyframe.image;img.alt=o.label;caption.textContent=`${o.label} · ${o.keyframe.timecode_s.toFixed(2)} с`;card.append(img,caption);$('keys').append(card);});
        $('result').hidden=false;message('Готово. Можно скачать ZIP или отдельные файлы.');break;
      }
    }
  }catch(e){message(`Ошибка: ${e.message}`);}
  finally{busy=false;document.querySelectorAll('input,select,#add,#shuffleSeed').forEach(e=>e.disabled=false);$('motion').onchange();refresh();}
};

$('motion').onchange=()=>{const depth=$('motion').value==='depth';$('parallax').disabled=!depth;$('depthHint').hidden=!depth;};
$('shuffleSeed').onclick=()=>{if(busy)return;$('seed').value=crypto.getRandomValues(new Uint32Array(1))[0]%2147483648;message('Новый seed выбран. Нажмите «Создать видео» для нового маршрута.');};

$('useFocus').onchange=()=>refresh();
$('boxKind').onchange=()=>{$('label').value='';$('label').placeholder=$('boxKind').value==='context'?'Название элемента (необязательно)':'Название дефекта';};
refresh();

for(const id of ["blur","noise"])$(id).oninput=()=>$(id+"Value").textContent=$(id).value+"%";

$('overview').onchange=()=>refresh();
