import React, {useState} from 'react';
import {ArrowUpRight, Check, CircleNotch, FileVideo, Shuffle} from '@phosphor-icons/react';
import ClipTimeline from './ClipTimeline.jsx';
import SelectMenu from './SelectMenu.jsx';
import {gifSpeeds, gifDurations, timeLabel} from './export-utils.js';

export default function GifOptions({source, length, duration, preset, speed, quality, customSize, start, cursor, pulse, locked, allowGif, onDuration, onSpeed, onQuality, onSize, onMove, onResize, onPreview, onImport, onDrop, importing, connected}) {
  const speedIndex = gifSpeeds.indexOf(speed);
  const [dragging, setDragging] = useState(false);
  const canImport = connected && !locked && !importing;
  const dragProps = {
    onDragOver: e => { if (!canImport) return; e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setDragging(true); },
    onDragLeave: () => setDragging(false),
    onDrop: e => { e.preventDefault(); setDragging(false); if (!canImport) return; const file = e.dataTransfer.files?.[0]; if (file) onDrop(file); },
  };
  return <div className="gif-options">
    <div className="gif-topline">
    <div className="import-settings">
      <div className="control-heading"><label htmlFor="import-local">导入本地文件</label></div>
      <button id="import-local" type="button" className={'folder-picker import-local '+(source?.local?'has-folder':'')+(dragging?' dragging':'')} onClick={onImport} disabled={!connected||locked} title="点击选择或直接拖入视频文件，直接截取 GIF" {...dragProps}><FileVideo size={22}/><span>{dragging?'松开即导入':importing?'正在导入…':source?.local?source.title:'选择或拖入本地视频'}<small>已有视频导入后直接截取 GIF</small></span>{importing?<CircleNotch className="spin" size={18}/>:<ArrowUpRight size={18}/>}</button>
    </div>
    <div className="speed-settings">
      <div className="control-heading"><label htmlFor="speed">视频变速</label><span className="control-hint" aria-live="polite">片段时长 {Number((duration/speed).toFixed(1))} 秒</span></div>
      <div className="speed-track" style={{'--speed-progress':`${speedIndex/3*100}%`}}><div className="speed-ticks" aria-hidden="true">{gifSpeeds.map(s=><i key={s}/>)}</div><input id="speed" type="range" min="0" max="3" step="1" value={speedIndex} aria-valuetext={speed===1?'原速':`${speed} 倍`} disabled={!source||locked} onChange={e=>onSpeed(gifSpeeds[Number(e.target.value)])}/></div>
      <div className="speed-labels">{gifSpeeds.map((s,i)=><button type="button" key={s} className={i===speedIndex?'selected':''} disabled={!source||locked} onClick={()=>onSpeed(s)}>{s===1?'原速':`${s} 倍`}</button>)}</div>
    </div>
    </div>
    <div className="duration-heading"><label>片段导出时长</label><button type="button" className="text-button shuffle" disabled={!allowGif || locked} onClick={()=>onMove(Math.random()*Math.max(0,length-duration))}><Shuffle size={14}/>随机片段</button></div>
    <div className="duration-options">{gifDurations.map(d=><button type="button" key={d} className={preset===d?'selected':''} disabled={!source || locked || length/speed<d&&preset!==d} onClick={()=>onDuration(d)}>{d} 秒{preset===d&&<Check size={14}/>}</button>)}<button type="button" className={preset==='custom'?'selected':''} disabled={!source||length<=0||locked} onClick={()=>onDuration('custom')}>自定义选取{preset==='custom'&&<Check size={14}/>}</button></div>
    <div className="clip-selection-settings">
    <div className="control-heading timeline-heading"><label>选取视频片段</label><span className="control-hint">{preset==='custom'?'拖动两端调整范围，框内滑条预览':'拖动外框选片段，框内滑条预览'}</span></div>
    <ClipTimeline length={length} duration={duration} speed={speed} custom={preset==='custom'} pulse={pulse} onResize={onResize} start={start} cursor={cursor} disabled={!allowGif||locked} onMove={onMove} onPreview={onPreview}/>
    <div className="time-labels"><span>00:00</span><span>{timeLabel(length/speed)}</span></div>
    {preset==='custom'&&<p className="custom-selection-note" aria-live="polite">自定义选取：可自由拖动左右两端。</p>}
    </div>
    <div className="gif-output-settings">
      <div><label htmlFor="quality">选择导出 GIF 精度</label><SelectMenu id="quality" label="选择导出 GIF 精度" value={quality} disabled={locked} onChange={onQuality} options={[['low','低'],['medium','中'],['high','高']].map(([value,label])=>({value,label}))}/></div>
      <div><label htmlFor="custom-size">自定义导出大小</label><div className="size-input"><input id="custom-size" type="number" min="0.05" max="100" step="any" inputMode="decimal" disabled={locked} value={customSize} placeholder="输入大小" aria-describedby="size-unit" onChange={e=>onSize(e.target.value)}/><span id="size-unit" className="size-unit">MB</span></div></div>
    </div>
  </div>;
}
