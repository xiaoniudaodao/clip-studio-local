import React, {useEffect, useRef, useState} from 'react';
import {CheckCircle, CircleNotch} from '@phosphor-icons/react';

export default function DownloadButton({kind, busy, disabled, success, onClick}) {
  const [pressing,setPressing]=useState(false);
  const pressTimer=useRef(null);
  useEffect(()=>()=>clearTimeout(pressTimer.current),[]);
  function point(event) {
    const rect=event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty('--glow-x',`${event.clientX-rect.left}px`);
    event.currentTarget.style.setProperty('--glow-y',`${event.clientY-rect.top}px`);
  }
  function hover(event) {
    if(disabled||event.pointerType==='touch')return;
    point(event);event.currentTarget.dataset.glowing='true';
  }
  function pulse() {
    clearTimeout(pressTimer.current);setPressing(true);
    pressTimer.current=setTimeout(()=>setPressing(false),220);
  }
  function press(event) {if(!disabled){point(event);pulse();}}
  function activate(event) {
    if(event.detail===0){event.currentTarget.style.setProperty('--glow-x','50%');event.currentTarget.style.setProperty('--glow-y','50%');}
    pulse();onClick?.(event);
  }
  return <button type="button" className={`primary export-button ${success&&!busy?'save-complete':''} ${pressing?'is-pressing':''}`} onPointerEnter={hover} onPointerMove={hover} onPointerLeave={event=>{delete event.currentTarget.dataset.glowing;}} onPointerCancel={event=>{delete event.currentTarget.dataset.glowing;clearTimeout(pressTimer.current);setPressing(false);}} onPointerDown={press} onClick={activate} disabled={disabled} title={success?`已保存：${success.path}`:undefined} aria-busy={busy}>
    <span className="download-button-label" role="status" aria-live="polite" aria-atomic="true">
      {busy?<CircleNotch size={20} className="spin"/>:success?<CheckCircle size={18}/>:null}
      {busy?'正在处理…':success?'已保存至指定文件夹。':kind==='gif'?'转换 GIF 并下载':'下载视频'}
    </span>
  </button>;
}
