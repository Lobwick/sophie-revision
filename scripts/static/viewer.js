const D=document.body.dataset,SLUG=D.slug,TOTAL=+D.total;let page=+D.page,scale=0,pdf=null,busy=false,again=false;
pdfjsLib.GlobalWorkerOptions.workerSrc="/static/pdfjs/pdf.worker.min.js";
const $=id=>document.getElementById(id),cv=$("c");
async function show(n){n=Math.max(1,Math.min(TOTAL,n|0||1));page=n;$("num").value=n;history.replaceState(null,"","?page="+n);
 if(busy){again=true;return}busy=true;try{const p=await pdf.getPage(n),w=Math.min(innerWidth-24,1100),base=p.getViewport({scale:1}),s=scale||w/base.width,
 dpr=devicePixelRatio||1,v=p.getViewport({scale:s*dpr});cv.width=v.width;cv.height=v.height;cv.style.width=(v.width/dpr)+"px";
 await p.render({canvasContext:cv.getContext("2d"),viewport:v}).promise;cv.hidden=false;$("msg").hidden=true;document.title=document.title.replace(/p\.\d+/,"p."+n);
 if($("txt").style.display==="block")txt()}catch(e){$("msg").hidden=false;$("msg").textContent="Impossible d'afficher la page : "+e.message}busy=false;if(again){again=false;show(page)}}
async function txt(){const r=await fetch("/api/page/"+SLUG+"/"+page);$("txt").textContent=r.ok?(await r.json()).text||"(aucun texte indexé pour cette page)":"Texte indisponible"}
$("prev").onclick=()=>show(page-1);$("next").onclick=()=>show(page+1);$("num").onchange=e=>show(+e.target.value);
$("zi").onclick=()=>{scale=(scale||1.2)*1.2;show(page)};$("zo").onclick=()=>{scale=(scale||1.2)/1.2;show(page)};
$("tg").onclick=()=>{const t=$("txt");t.style.display=t.style.display==="block"?"none":"block";if(t.style.display==="block")txt()};
addEventListener("keydown",e=>{if(e.target.tagName==="INPUT")return;if(e.key==="ArrowRight")show(page+1);if(e.key==="ArrowLeft")show(page-1)});
let x0=null;addEventListener("touchstart",e=>x0=e.touches[0].clientX);addEventListener("touchend",e=>{if(x0===null||scale)return;const d=e.changedTouches[0].clientX-x0;x0=null;if(Math.abs(d)>70)show(page+(d<0?1:-1))});
addEventListener("resize",()=>{if(!scale)show(page)});
pdfjsLib.getDocument("/file/"+SLUG+".pdf").promise.then(d=>{pdf=d;show(page)}).catch(e=>{$("msg").textContent="Impossible d'ouvrir le PDF : "+e.message});
