import React, {useRef} from 'react';
import {clipStart, resizeClip} from './export-utils.js';

export default function ClipTimeline({length, duration, speed=1, start, cursor, disabled, custom=false, pulse=0, onMove, onResize, onPreview}) {
  const track = useRef(null), drag = useRef(null);
  const width = length ? Math.min(100, duration / length * 100) : 30;
  function move(e) {
    if (!drag.current) return;
    onMove(clipStart(drag.current.start + (e.clientX - drag.current.x) / drag.current.width * length, length, duration));
  }
  function resize(edge, value){onResize(resizeClip(start,start+duration,edge,value,length));}
  function handle(edge){
    const position=edge==='start'?start:start+duration;
    return <div className={`selection-handle handle-${edge}`} role="slider" aria-label={edge==='start'?'调整自定义片段起点':'调整自定义片段终点'} aria-valuemin={edge==='start'?0:start+Math.min(.1,length)} aria-valuemax={edge==='start'?start+duration-Math.min(.1,length):length} aria-valuenow={position} aria-valuetext={`${(position/speed).toFixed(1)} 秒`} aria-disabled={disabled} tabIndex={disabled?-1:0}
      onPointerDown={e=>{if(disabled)return;e.preventDefault();e.stopPropagation();e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);drag.current={edge,x:e.clientX,position,start,end:start+duration,width:track.current.getBoundingClientRect().width};}}
      onPointerMove={e=>{const d=drag.current;if(d?.edge===edge)onResize(resizeClip(d.start,d.end,edge,d.position+(e.clientX-d.x)/d.width*length,length));}}
      onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}
      onKeyDown={e=>{if(disabled)return;const delta=e.shiftKey?1:.1;let next;if(e.key==='ArrowLeft')next=position-delta;if(e.key==='ArrowRight')next=position+delta;if(e.key==='Home')next=edge==='start'?0:start+Math.min(.1,length);if(e.key==='End')next=edge==='start'?start+duration-Math.min(.1,length):length;if(next!==undefined){e.preventDefault();e.stopPropagation();resize(edge,next);}}}><i/><i/></div>;
  }
  return <div className="timeline-visual" ref={track}>
    <div className="timeline-bars" aria-hidden="true">{Array.from({length:42}, (_, i) => <i key={i} style={{height:18 + ((i * 17) % 31)}}/>)}</div>
    <div key={pulse} className={`timeline-selection ${custom?'custom-selection':''} ${pulse?'selection-pulse':''}`} style={{left:`${length ? start / length * 100 : 0}%`, width:`${width}%`}}>
      <div className="selection-mover" role="slider" aria-label="移动视频片段选框" aria-valuemin={0} aria-valuemax={Math.max(0, length-duration)} aria-valuenow={Number(start.toFixed(1))} aria-valuetext={`变速后从 ${(start/speed).toFixed(1)} 秒开始，长 ${(duration/speed).toFixed(1)} 秒`} aria-disabled={disabled} tabIndex={disabled ? -1 : 0}
      onPointerDown={e => {if(disabled || e.target.closest('input'))return; e.preventDefault(); e.currentTarget.focus(); e.currentTarget.setPointerCapture(e.pointerId); drag.current = {x:e.clientX, start, width:track.current.getBoundingClientRect().width};}}
      onPointerMove={move} onPointerUp={() => {drag.current=null;}} onPointerCancel={() => {drag.current=null;}}
      onKeyDown={e => {if(disabled || e.target !== e.currentTarget)return; let next; if(e.key==='ArrowLeft')next=start-(e.shiftKey?1:.1); if(e.key==='ArrowRight')next=start+(e.shiftKey?1:.1); if(e.key==='Home')next=0; if(e.key==='End')next=length-duration; if(next!==undefined){e.preventDefault();onMove(clipStart(next,length,duration));}}}>
      {!custom&&<><span className="selection-grip grip-left" aria-hidden="true"/><span className="selection-grip grip-right" aria-hidden="true"/></>}</div>
      {custom&&<>{handle('start')}{handle('end')}</>}
      <input type="range" aria-label="预览选中片段内的画面" aria-valuetext={`变速后 ${(cursor/speed).toFixed(1)} 秒`} min={start} max={start+duration} step="0.01" value={cursor} disabled={disabled} onChange={e=>onPreview(Number(e.target.value))} onPointerDown={e=>e.stopPropagation()}/>
    </div>
  </div>;
}
