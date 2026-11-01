"""Exercise compositing, traversal, identity guards and cleanup without a browser."""
import json
import shutil
import subprocess

import pytest

from boss_agent_cli.api.recruiter_client import _ONLINE_RESUME_ACTION_JS


@pytest.mark.parametrize("mode,ok", [("success", True), ("mismatch", False), ("empty", False),
	("wasm_error", False), ("load_error", False), ("timeout", True), ("stalled", True)])
def test_canvas_browser_lifecycle(mode, ok):
	node = shutil.which("node")
	if not node:
		pytest.skip("Node is required for browser-JS lifecycle tests")
	harness = r"""
const mode=MODE;
let now=0,removed=false,callback,timerId=0,scroll=0;
const timers=new Map(),intervals=new Map(),listeners=new Set();
Date.now=()=>now;
globalThis.location={origin:'https://www.zhipin.com'};
const canvas={width:730,height:800,getBoundingClientRect(){return {left:0,top:scroll,width:730,height:800}}};
class Context{
 constructor(c){this.canvas=c;this.globalAlpha=1;}
 getTransform(){return {a:1,b:0,transformPoint:p=>p}}
 measureText(s){return {width:s.length*10}}
 fillText(){} strokeText(){} clearRect(){} drawImage(){} reset(){}
}
const original=Context.prototype.fillText;
const ctx=new Context(canvas);
function render(){
 ctx.clearRect(0,0,730,800);
 const tile={width:730,height:800};const off=new Context(tile);
 off.fillText('查看全部',0,10);off.clearRect(0,0,730,800);
 off.fillText(scroll===0?'第一页':'最后一页',0,20);
 off.fillText(' repeated',90,20);
 ctx.drawImage(tile,0,0,730,800,0,0,730,800);
}
const wrapper={style:{},clientHeight:800,get scrollHeight(){return parseInt(frame.style.height)},
 get scrollTop(){return scroll},set scrollTop(value){scroll=value;if(mode!=='stalled')render()},
 appendChild(){},remove(){removed=true}};
const win={location:{origin:mode==='load_error'?'https://other.invalid':location.origin},CanvasRenderingContext2D:Context,
 postMessage(m){
  if(mode!=='empty')render();
  const data=mode==='wasm_error'?{type:'WASM_ERROR',data:{message:'failed'}}:
   {type:'IFRAME_DONE',data:{abstractData:{geekBaseInfo:{encryptGeekId:mode==='mismatch'?'wrong':'target',userId:123}}}};
  for(const fn of [...listeners])fn({origin:location.origin,source:win,data:{...data,connectionId:m.connectionId}});
 }
};
const frame={style:{},contentWindow:win,contentDocument:{querySelectorAll(){return [canvas]},getElementById(){return {getBoundingClientRect(){return {height:1400}}}}},
 setAttribute(){},addEventListener(type,fn){callback=fn;}};
globalThis.document={createElement(tag){return tag==='div'?wrapper:frame},body:{appendChild(){callback()}}};
globalThis.setTimeout=fn=>{timers.set(++timerId,fn);return timerId};
globalThis.clearTimeout=id=>timers.delete(id);
globalThis.setInterval=fn=>{intervals.set(++timerId,fn);return timerId};
globalThis.clearInterval=id=>intervals.delete(id);
globalThis.window={addEventListener(t,fn){listeners.add(fn)},removeEventListener(t,fn){listeners.delete(fn)}};
const pending=(SCRIPT)({encryptUid:'target',uid:123,timeoutMs:25000});
if(mode!=='timeout'&&mode!=='empty')for(let i=0;i<14;i++){now+=500;for(const fn of [...intervals.values()])fn()}
for(const fn of [...timers.values()])fn();
pending.then(result=>console.log(JSON.stringify({result,removed,restored:Context.prototype.fillText===original,
 timers:timers.size,intervals:intervals.size,listeners:listeners.size})));
""".replace("MODE", json.dumps(mode)).replace("SCRIPT", _ONLINE_RESUME_ACTION_JS)
	run = subprocess.run([node, "-e", harness], capture_output=True, text=True, encoding="utf-8", timeout=10, check=True)
	value = json.loads(run.stdout)
	assert value["result"]["ok"] is ok
	assert value["removed"] and value["restored"]
	assert value["timers"] == value["intervals"] == value["listeners"] == 0
	if ok:
		capture = value["result"]["canvas"]
		text = "".join(row["text"] for row in capture["draws"])
		assert "查看全部" not in text
		assert "第一页" in text
		if mode == "success":
			assert "最后一页" in text
			assert capture["reached_bottom"]
			assert capture["scroll_steps"] == 1
			assert capture["content_height"] == 1400  # not the bootstrap 1200px
			assert capture["height_measured"]
		elif mode == "stalled":
			assert capture["render_stalled"] and not capture["reached_bottom"]
		else:
			assert capture["timed_out"] and not capture["reached_bottom"]
