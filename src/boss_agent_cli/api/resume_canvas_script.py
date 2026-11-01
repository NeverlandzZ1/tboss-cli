"""Official resume renderer traversal; observe final composited canvas text."""

ONLINE_RESUME_JS = r"""
async (args) => {
 const wrapper = document.createElement('div');
 Object.assign(wrapper.style, {position:'fixed', left:'-10000px', top:'0',
  width:'730px', height:'800px', overflowY:'auto', pointerEvents:'none'});
 const frame = document.createElement('iframe');
 const recommended=args.resumeSource==='recommend';
 frame.src = '/web/frame/c-resume/?source='+(recommended?'recommend':'chat-resume-online');
 Object.assign(frame.style, {display:'block', width:'100%', height:'1200px', border:'0'});
 frame.setAttribute('aria-hidden','true');
 const connectionId = `boss-canvas-${Date.now()}-${Math.random()}`;
 const scenes = new WeakMap(), restores = [], output = new Map();
 let completed=null, settled=false, lastDraw=0, lastScroll=0, steps=0, bottomPasses=0;
 let capped=false, unsupported=false, copied=0, snapshots=0;
 let drawVersion=0, pendingDrawVersion=null, renderStalled=false;
 let measuredHeight=0, heightChangedAt=0;
 const syncHeight = () => {
  const root=frame.contentDocument.getElementById('resume');
  const height=root ? Math.ceil(root.getBoundingClientRect().height) : 0;
  if(!Number.isFinite(height)||height<=0)return false;
  if(height!==measuredHeight){measuredHeight=height;heightChangedAt=Date.now();bottomPasses=0;}
  // Official ResizeObserver schedules this through rAF, which may be delayed in
  // background tabs. Never use the bootstrap iframe height as resume height.
  frame.style.height=height+'px';
  return true;
 };
 const scene = canvas => {
  const previous=scenes.get(canvas);
  if (!previous || previous.width!==canvas.width || previous.height!==canvas.height)
   scenes.set(canvas,{width:canvas.width,height:canvas.height,rows:new Map()});
  return scenes.get(canvas).rows;
 };
 const put = (canvas,row) => {
  const rows=scene(canvas);
  if(rows.size>=50000){capped=true;return;}
  rows.set(JSON.stringify([row.x,row.y,row.text]),row);
 };
 const point = (ctx,x,y) => ctx.getTransform().transformPoint({x,y});
 const install = win => {
  for(const C of [win.CanvasRenderingContext2D,win.OffscreenCanvasRenderingContext2D]){
   if(!C)continue;
   const hook=(name,observe)=>{
    const original=C.prototype[name];if(typeof original!=='function')return;
    C.prototype[name]=function(...values){
     const result=original.apply(this,values);
     try{observe(this,...values);lastDraw=Date.now();drawVersion++;}catch(_){unsupported=true;}
     return result;
    };
    restores.push(()=>{C.prototype[name]=original;});
   };
   for(const method of ['fillText','strokeText'])hook(method,(ctx,text,x,y)=>{
    if(ctx.globalAlpha===0)return;
    const p=point(ctx,x,y),m=ctx.measureText(String(text));
    const scale=Math.hypot(ctx.getTransform().a,ctx.getTransform().b)||1;
    put(ctx.canvas,{text:String(text),x:p.x,y:p.y,w:m.width*scale});
   });
   hook('clearRect',(ctx,x,y,w,h)=>{
    const a=point(ctx,x,y),b=point(ctx,x+w,y+h);
    const rows=scene(ctx.canvas);
    for(const [key,row] of rows)if(row.x>=Math.min(a.x,b.x)&&row.x<Math.max(a.x,b.x)&&
     row.y>=Math.min(a.y,b.y)&&row.y<=Math.max(a.y,b.y))rows.delete(key);
   });
   hook('reset',ctx=>scenes.delete(ctx.canvas));
   hook('drawImage',(ctx,image,...v)=>{
    if(!scenes.has(image))return;
    let sx=0,sy=0,sw=image.width,sh=image.height,dx,dy,dw,dh;
    if(v.length===2){[dx,dy]=v;dw=sw;dh=sh;}
    else if(v.length===4){[dx,dy,dw,dh]=v;}
    else if(v.length===8){[sx,sy,sw,sh,dx,dy,dw,dh]=v;}
    else {unsupported=true;return;}
    if(!sw||!sh)return;
    for(const row of [...scene(image).values()]){
     if(row.x+row.w<sx||row.x>=sx+sw||row.y<sy||row.y>sy+sh)continue;
     const p=point(ctx,dx+(row.x-sx)*dw/sw,dy+(row.y-sy)*dh/sh);
     put(ctx.canvas,{...row,x:p.x,y:p.y,w:row.w*Math.abs(dw/sw)});copied++;
    }
   });
  }
 };
 const snapshot = () => {
  for(const canvas of frame.contentDocument.querySelectorAll('canvas')){
   const rect=canvas.getBoundingClientRect();
   if(!rect.width||!rect.height||!canvas.width||!canvas.height)continue;
   const scaleX=rect.width/canvas.width,scaleY=rect.height/canvas.height;
   // Frame-relative CSS coordinates include the renderer's translateY(scrollTop).
   for(const row of scene(canvas).values()){
    if(row.x<0||row.x>=canvas.width||row.y<0||row.y>canvas.height)continue;
    const x=Math.round((rect.left+row.x*scaleX)*10)/10;
    const y=Math.round((rect.top+row.y*scaleY)*10)/10;
    const item={canvas:0,text:row.text,x,y};
    if(output.size<100000)output.set(JSON.stringify(item),item);else capped=true;
   }
  }
  snapshots++;
 };
 return await new Promise(resolve=>{
  const finish=(error,reachedBottom=false,timedOut=false)=>{
   if(settled)return;settled=true;
   clearTimeout(timer);clearInterval(poll);
   window.removeEventListener('message',onMessage);
   for(const restore of restores)restore();
   const height=wrapper.scrollHeight;
   wrapper.remove();
   if(error||!completed||!output.size){resolve({ok:false,error:error||'online resume rendered no text'});return;}
   resolve({ok:true,data:completed,canvas:{draws:[...output.values()],capped,timed_out:timedOut,
    composited:true,reached_bottom:reachedBottom,unsupported,snapshots,scroll_steps:steps,
    content_height:height,copied_glyphs:copied,height_measured:measuredHeight>0,
    measured_height:measuredHeight,render_stalled:renderStalled}});
  };
  const timer=setTimeout(()=>{if(completed)try{snapshot();}catch(_){}finish(null,false,true);},args.timeoutMs||25000);
  const onMessage=event=>{
   if(event.source!==frame.contentWindow||event.origin!==location.origin||event.data?.connectionId!==connectionId)return;
   const m=event.data;
   if(m.type==='IFRAME_DONE'){
    const base=m.data?.abstractData?.geekBaseInfo;
    if(!base||(!base.encryptGeekId&&!base.userId)||(base.encryptGeekId&&base.encryptGeekId!==args.encryptUid)||
     (args.uid&&base.userId&&String(args.uid)!==String(base.userId))){finish('online resume identity missing or mismatched');return;}
    completed=m.data;
   }else if(['WASM_ERROR','WASM_INIT_ERROR','WASM_NO_SUPPORT'].includes(m.type))finish(m.data?.message||m.type);
  };
  window.addEventListener('message',onMessage);
  const poll=setInterval(()=>{
   if(!completed||Date.now()-Math.max(lastDraw,lastScroll)<350)return;
   try{
    if(!syncHeight()||Date.now()-heightChangedAt<600)return;
    if(pendingDrawVersion!==null){
     if(drawVersion===pendingDrawVersion){
      if(Date.now()-lastScroll>2000){renderStalled=true;finish(null,false);}
      return;
     }
     pendingDrawVersion=null;
    }
    snapshot();
    const end=Math.max(0,wrapper.scrollHeight-wrapper.clientHeight);
    if(wrapper.scrollTop>=end-2){
     if(++bottomPasses>=2){finish(null,true);return;}
     lastScroll=Date.now();return;
    }
    bottomPasses=0;
    if(steps>=60){finish(null,false);return;}
    pendingDrawVersion=drawVersion;
    wrapper.scrollTop=Math.min(end,wrapper.scrollTop+wrapper.clientHeight*0.75);
    steps++;lastScroll=Date.now();
   }catch(_){finish('online resume traversal failed');}
  },100);
  frame.addEventListener('load',()=>{
   if(settled)return;
   try{
    if(frame.contentWindow.location.origin!==location.origin)throw new Error('origin');
    install(frame.contentWindow);
    const requestParams=recommended?{
     encryptJid:args.encryptJobId,expectId:args.expectId,securityId:args.securityId,
     lid:args.lid,entrance:0,wayType:0,sourceType:3
    }:{
     encryptJid:args.encryptJobId,securityId:args.securityId,encryptExpectId:args.encryptExpectId,
     expectId:args.expectId,scene:0,source:1,uid:args.encryptUid};
    frame.contentWindow.postMessage({type:'SET_RESUME',connectionId,data:{requestParams,dataSourceParams:{
     encryptJobId:args.encryptJobId,resumeSource:recommended?'recommend-resume':'chat-resume-online',encryptGeekId:args.encryptUid,
     geekId:args.uid,jobId:args.jobId,lid:recommended?args.lid:'',
     ...(recommended?{isPreview:false,scrollCheckEnable:false,singleViewer:false}: {})}}},location.origin);
   }catch(_){finish('online resume frame unavailable; check login/security verification');}
  },{once:true});
  wrapper.appendChild(frame);document.body.appendChild(wrapper);
 });
}
"""
