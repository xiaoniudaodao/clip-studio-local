import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowDown, ArrowRight, ArrowUpRight, CheckCircle, CircleNotch, FilmStrip, FolderOpen, LinkSimple, Play, WarningCircle, X} from '@phosphor-icons/react';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import './style.css';
import './lime-skin.css';
import GifOptions from './GifOptions.jsx';
import BrandMark from './BrandMark.jsx';
import FormatRadioList from './FormatRadioList.jsx';
import SectionNumber from './SectionNumber.jsx';
import DownloadButton from './DownloadButton.jsx';
import {validateFilename, formatOptionList, downloadOptions, previewTime, clipStart, customGifLimit, durationForPreset} from './export-utils.js';

const bytes = n => !n ? '大小未知' : n < 1024*1024 ? `${(n/1024).toFixed(0)} KB` : `${(n/1024/1024).toFixed(2)} MB`;
const clock = t => `${Math.floor((t||0)/60).toString().padStart(2,'0')}:${Math.floor((t||0)%60).toString().padStart(2,'0')}`;
function App(){
 const [token,setToken]=useState(''),[connection,setConnection]=useState('connecting');
 const [url,setUrl]=useState(''),[source,setSource]=useState(null),[format,setFormat]=useState('');
 const [tab,setTab]=useState('video'),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false);
 const [preview,setPreview]=useState(null),[previewLoading,setPreviewLoading]=useState(false),[previewError,setPreviewError]=useState('');
 const [error,setError]=useState(''),[saveSuccess,setSaveSuccess]=useState(null),[job,setJob]=useState(null),[result,setResult]=useState(null);
 const [duration,setDuration]=useState(5),[preset,setPreset]=useState(5),[pulse,setPulse]=useState(0),[speed,setSpeed]=useState(1),[start,setStart]=useState(0),[quality,setQuality]=useState('medium'),[customSize,setCustomSize]=useState('1'),[folder,setFolder]=useState(null),[folderInvalid,setFolderInvalid]=useState(false),[folderChoosing,setFolderChoosing]=useState(false);
 const [importing,setImporting]=useState(false);
 const [filename,setFilename]=useState(''),[clipPlay,setClipPlay]=useState(false),[cursor,setCursor]=useState(0);
 const video=useRef(null),generation=useRef(0),previewGeneration=useRef(0),folderPickerOpen=useRef(false),folderVersion=useRef(0),saveSequence=useRef(0);
 useEffect(()=>{fetch('/api/health').then(r=>r.json()).then(d=>{setToken(d.token);setConnection('ready')}).catch(()=>{setConnection('error');setError('无法连接本地服务，请从项目目录重新启动拾片。')})},[]);
 useEffect(()=>()=>{generation.current++;previewGeneration.current++},[]);
 useEffect(()=>{const block=e=>{if(!e.target.closest?.('#import-local'))e.preventDefault()};window.addEventListener('dragover',block);window.addEventListener('drop',block);return()=>{window.removeEventListener('dragover',block);window.removeEventListener('drop',block)}},[]);
 useEffect(()=>{if(!saveSuccess)return;const timer=setTimeout(()=>setSaveSuccess(null),2800);return()=>clearTimeout(timer)},[saveSuccess]);
 useEffect(()=>{if(video.current)video.current.playbackRate=tab==='gif'?speed:1},[speed,tab,preview]);
 useEffect(()=>{let active=true;const check=async()=>{if(folderPickerOpen.current)return;const version=folderVersion.current;try{const r=await fetch('/api/save-location');if(!r.ok)return;const d=await r.json();if(!active||folderPickerOpen.current||version!==folderVersion.current)return;setFolder(d.valid?d:null);setFolderInvalid(!!d.path&&!d.valid);if(d.path&&!d.valid)setError('找不到指定的位置，请重新设置保存文件夹。');}catch{}};check();window.addEventListener('focus',check);return()=>{active=false;window.removeEventListener('focus',check)}},[]);
 async function api(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Clip-Token':token},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Object.assign(Error(d.error||'操作失败'),{folderMissing:d.code==='folder_missing'});return d;}
 async function waitJob(id,onProgress,valid=()=>true){for(;;){if(!valid())return null;await new Promise(r=>setTimeout(r,700));const r=await fetch(`/api/jobs/${id}`);const d=await r.json();if(!r.ok)throw Error(d.error||'任务读取失败');if(!valid())return null;onProgress?.(d);if(d.status==='error')throw Error(d.message);if(d.status==='done')return d;}}
 async function resolve(value){
  const g=++generation.current;++previewGeneration.current;setLoading(true);setSource(null);setPreview(null);setResult(null);setError('');setSaveSuccess(null);setPreviewError('');setJob(null);setClipPlay(false);
  try{const s=await api('/api/resolve',{url:value});if(g!==generation.current)return;setSource(s);setFormat(downloadOptions(s.formats)[0].id);setFilename('');const initial=0;setStart(initial);setCursor(initial);setDuration(Math.min(5,s.duration||5));setPreset(5);setSpeed(1);loadPreview(s);}
  catch(e){setError(e.message)}finally{if(g===generation.current)setLoading(false)}
 }
 async function importDrop(file){
  if(importing||!file)return;setImporting(true);setError('');
  const g=++generation.current;++previewGeneration.current;setLoading(true);
  try{
   const r=await fetch('/api/import-upload',{method:'POST',headers:{'X-Clip-Token':token,'X-Clip-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'},body:file});
   const s=await r.json();if(!r.ok)throw Error(s.error||'导入失败');if(g!==generation.current)return;
   applySource(s);
  }catch(e){setError(e.message)}finally{setImporting(false);if(g===generation.current)setLoading(false)}
 }
 function applySource(s){setUrl('');setSource(s);setPreview(null);setResult(null);setSaveSuccess(null);setPreviewError('');setJob(null);setClipPlay(false);setFormat(downloadOptions(s.formats)[0].id);setFilename('');setStart(0);setCursor(0);setDuration(Math.min(5,s.duration||5));setPreset(5);setSpeed(1);loadPreview(s);}
 async function importLocal(){
  if(importing||folderPickerOpen.current)return;setImporting(true);setError('');
  const g=++generation.current;++previewGeneration.current;setLoading(true);
  try{const s=await api('/api/import-local',{});if(g!==generation.current)return;if(s.cancelled)return;applySource(s);}
  catch(e){setError(e.message)}finally{setImporting(false);if(g===generation.current)setLoading(false)}
 }
 async function loadPreview(s){const g=++previewGeneration.current;setPreviewLoading(true);setPreviewError('');try{const j=await api('/api/jobs',{sourceId:s.id,kind:'preview'});const d=await waitJob(j.id,null,()=>g===previewGeneration.current);if(!d)return;setPreview(d);setSource(old=>old?.id===s.id?{...old,duration:d.duration,width:d.width,height:d.height,formats:old.formats.map(f=>f.id===d.formatId?{...f,width:d.width,height:d.height,size:d.originalSize,approximate:false}:f)}:old);}catch(e){if(g===previewGeneration.current)setPreviewError(e.message)}finally{if(g===previewGeneration.current)setPreviewLoading(false)}}
 const length=source?.duration||0;
 function changeDuration(choice){const d=choice==='custom'?length:durationForPreset(choice,speed,length);setPreset(choice);setDuration(d);moveClip(0,d);setPulse(n=>n+1);setResult(null);}
 function changeSpeed(s){const d=preset==='custom'?duration:durationForPreset(preset,s,length);setSpeed(s);setDuration(d);moveClip(clipStart(start,length,d),d);setPulse(n=>n+1);setResult(null);}
 function resizeSelection(bounds){const d=bounds.end-bounds.start;setDuration(d);setStart(bounds.start);setCursor(bounds.start);setClipPlay(false);setResult(null);if(video.current){video.current.pause();video.current.currentTime=bounds.start;}}
 function moveClip(t,d=duration){const value=clipStart(t,length,d);setStart(value);setCursor(value);setClipPlay(false);if(video.current){video.current.pause();video.current.currentTime=value;}}
 function previewFrame(t){const value=previewTime(t,start,duration);setCursor(value);setClipPlay(false);if(video.current){video.current.pause();video.current.currentTime=value;}}
 function handleSaveError(e){if(e.folderMissing){setFolder(null);setFolderInvalid(true);}setError(e.message);}
 async function chooseFolder(){if(folderPickerOpen.current)return;folderPickerOpen.current=true;folderVersion.current++;setError('');setFolderChoosing(true);try{const location=await api('/api/save-location',{});if(location.cancelled)return;setFolder(location);setFolderInvalid(false);}catch(e){handleSaveError(e)}finally{folderPickerOpen.current=false;setFolderChoosing(false)}}
 async function saveFile(d){const saved=await api('/api/save',{jobId:d.id,filename});setFolder(saved.folder);setFolderInvalid(false);setSaveSuccess({id:++saveSequence.current,path:saved.path});}
 async function checkLocation(){const r=await fetch('/api/save-location');if(!r.ok)throw Error('无法读取保存位置，请检查本地服务。');const d=await r.json();if(!d.valid)throw Object.assign(Error(d.path?'找不到指定的位置，请重新设置保存文件夹。':'请先选择保存文件夹。'),{folderMissing:!!d.path});setFolder(d);}
 async function saveAgain(){if(busy||folderChoosing)return;setBusy(true);setSaveSuccess(null);setError('');try{await checkLocation();await saveFile(result);}catch(e){handleSaveError(e)}finally{setBusy(false)}}
 async function exportFile(){
  if(!source||busy)return;setBusy(true);setError('');setSaveSuccess(null);setResult(null);
  try{
   await checkLocation();validateFilename(filename);
   const j=await api('/api/jobs',{sourceId:source.id,formatId:format,kind:tab,start,duration,limit:tab==='gif'?customGifLimit(customSize,'MB'):null,speed,quality});
   const d=await waitJob(j.id,setJob);setResult({...d,clipDuration:d.gifDuration||duration});
   if(tab==='video')setSource(old=>({...old,formats:old.formats.map(f=>f.id===format?{...f,size:d.size,approximate:false}:f)}));
   setJob({...d,message:'正在保存到本地…'});await saveFile(d);setJob({...d,message:'文件已就绪'});
  }catch(e){handleSaveError(e)}finally{setBusy(false)}
 }
 const allowGif=duration>0&&length>=duration&&!!preview;
 useEffect(()=>{if(!length)return;const d=preset==='custom'?Math.min(duration,length):durationForPreset(preset,speed,length);if(d!==duration)setDuration(d);const next=clipStart(start,length,d);if(next!==start)setStart(next);setCursor(t=>previewTime(t,next,d));},[length,duration,preset,speed,start]);
 const locked=busy||loading||folderChoosing;
 return <div className="app-shell">
  <header className="topbar"><a className="brand" href="/" aria-label="拾片首页"><BrandMark/></a></header>
  <main>
   <div className="intro"><div className="intro-art" aria-hidden="true"><img src="/assets/images/film-ribbon-header.png" alt="" width="1536" height="1024"/></div><div className="intro-content"><div className="hero-heading"><h1>好片段，<span>随手<span className="hero-ending">留。<svg className="hero-swipe" viewBox="0 0 130 38" aria-hidden="true"><path d="M8 29 Q37 15 81 8 L51 28 Q83 14 120 10"/></svg></span></span></h1></div><ol className="workflow" aria-label="使用流程"><li><span className="step-number">1</span><span>粘贴视频链接</span></li><li><span className="step-number">2</span><span>点击获取，等待解析与预览</span></li><li className="workflow-export"><span className="step-number">3</span><span>选择下载方式：直接下载视频或视频转换 GIF</span></li></ol></div><div className="hero-side-note" aria-hidden="true">DOWNLOAD VIDEO<span>→</span>VIDEO TO GIF</div></div>
   <div className="workspace">
    <div className="source-column">
   <section className="link-panel" aria-label="获取视频"><form onSubmit={e=>{e.preventDefault();resolve(url)}}><label htmlFor="url"><SectionNumber value="01"/><span className="section-title">粘贴视频链接</span></label><div className="url-actions"><div className="url-row"><LinkSimple size={23}/><input id="url" type="text" placeholder="粘贴视频网页链接或视频直链" value={url} onChange={e=>setUrl(e.target.value)} required disabled={locked}/></div><button className="primary fetch-btn" disabled={locked||connection!=='ready'}>{loading?<CircleNotch className="spin" size={20}/>:<ArrowRight size={20}/>}<span>{loading?'正在获取':'获取视频'}</span></button></div></form><div className="link-help"><span>可解析：X、YouTube、哔哩哔哩、抖音、小红书 · 视频号暂未接入</span></div></section>
    <section className="preview-panel"><div className="section-heading"><h2><SectionNumber value="02"/>视频预览</h2><span className="tag">{source?'已获取':'等待链接'}</span></div>
     <div className={'video-stage '+(loading?'skeleton':'')}>
      {preview?<video ref={video} src={preview.url} controls playsInline preload="metadata" onPlay={()=>{if(tab==='gif'){if(video.current.currentTime<start||video.current.currentTime>=start+duration)video.current.currentTime=start;setClipPlay(true);}}} onLoadedMetadata={()=>{if(tab==='gif')video.current.currentTime=start;}} onTimeUpdate={()=>{if(tab==='gif'){const t=video.current.currentTime;setCursor(previewTime(t,start,duration));if(clipPlay&&t>=start+duration){video.current.pause();video.current.currentTime=start+duration;setClipPlay(false);}}}} onError={()=>setPreviewError('浏览器未能播放预览，请点击重试预览。')} onEnded={()=>setClipPlay(false)}/>:<div className="empty-stage">{previewLoading||loading?<><CircleNotch size={42} className="spin"/><strong>{loading?'正在识别视频…':'正在准备视频预览…'}</strong><span>获取文件与准备播放可能需要一点时间</span></>:<><div className="empty-graphic"><div className="frame frame-back"/><div className="frame frame-front"><Play weight="fill" size={28}/></div></div><strong>{previewError?'预览暂不可用':'你的下一段灵感，在这里'}</strong><span>{previewError?'可以重试预览，或选择格式下载视频':'获取视频后，即可播放和选取片段'}</span>{previewError&&<button className="secondary" onClick={()=>loadPreview(source)} disabled={locked}>重试预览</button>}</>}</div>}
     </div>
     <div className={'video-meta '+(!source?'is-empty':'')} aria-hidden={!source}><h3>已获取的视频</h3><span className="duration-badge">{length?clock(length):'时长待确认'}</span></div>

     {previewError&&<div className="inline-error">{previewError} {preview&&<button className="text-button" disabled={locked||previewLoading} onClick={()=>loadPreview(source)}>重试预览</button>}</div>}
    </section>
    </div>
    <section className="export-panel"><div className="section-heading"><h2><SectionNumber value="03"/>选择导出方式</h2></div><div className="tab-list" role="tablist" aria-label="导出方式"><button role="tab" aria-selected={tab==='video'} className={tab==='video'?'active':''} disabled={locked} onClick={()=>{setTab('video');setResult(null)}}><ArrowDown size={18}/> 下载视频</button><button role="tab" aria-selected={tab==='gif'} className={tab==='gif'?'active':''} disabled={locked} onClick={()=>{setTab('gif');setResult(null);previewFrame(start)}}><FilmStrip size={18}/> 转换 GIF</button></div>
     <fieldset disabled={locked} className={!source?'pending-source':''}>
      {tab==='video'?<div className="video-options"><div id="format-label" className="format-heading">视频格式</div><FormatRadioList labelledBy="format-label" disabled={!source||locked} value={format} onChange={setFormat} options={source?formatOptionList(source.formats,format):[]}/></div>:<GifOptions source={source} length={length} duration={duration} preset={preset} pulse={pulse} speed={speed} quality={quality} customSize={customSize} start={start} cursor={cursor} locked={locked} allowGif={allowGif} onDuration={changeDuration} onSpeed={changeSpeed} onQuality={setQuality} onSize={setCustomSize} onMove={moveClip} onResize={resizeSelection} onPreview={previewFrame} onImport={importLocal} onDrop={importDrop} importing={importing} connected={connection==='ready'}/>}
      <div className="save-options"><div className="filename-heading"><label htmlFor="filename">文件名<span className="optional-note">（选填）</span></label><p id="filename-hint" className="filename-hint">留空将自动命名为：{tab==='gif'?'拾片下载动图 01、拾片下载动图 02…':'拾片下载视频 01、拾片下载视频 02…'}</p></div><input id="filename" name="clip-export-name" autoComplete="off" spellCheck={false} disabled={!source||locked} value={filename} onChange={e=>setFilename(e.target.value)} placeholder={tab==='gif'?'输入自定义的 GIF 名称':'输入自定义的视频名称'} aria-describedby="filename-hint"/><div className="save-heading"><label>保存位置</label></div><button type="button" className={'folder-picker '+(folder?'has-folder':'')+(folderInvalid?' invalid':'')} onClick={chooseFolder} disabled={connection!=='ready'} title={folder?`保存位置：${folder.path}；点击更换文件夹`:'选择保存视频的文件夹'}><FolderOpen size={22}/><span>{folderChoosing?'等待选择文件夹…':folder?folder.path:folderInvalid?'找不到指定的位置，请重新设置':'选择保存视频的文件夹'}<small>{folder?'点击更换保存文件夹':'视频和 GIF 将存放在你指定的位置'}</small></span>{folder?<CheckCircle size={20}/>:<ArrowUpRight size={18}/>}</button></div>
     </fieldset>
     <DownloadButton kind={tab} busy={busy} success={saveSuccess} onClick={exportFile} disabled={!source||locked||!folder||(tab==='gif'&&!allowGif)}/>

    </section>
   </div>
   <div className="feedback" aria-live="polite">{job&&busy&&<div className="progress-panel"><div><CircleNotch className="spin" size={18}/><span>{job.message}</span><strong>{job.progress}%</strong></div><progress max="100" value={job.progress}/></div>}{error&&<div className="alert error"><WarningCircle size={21}/><span>{error}</span><button aria-label="关闭错误提示" onClick={()=>setError('')}><X size={17}/></button></div>}{result?.filename?.endsWith('.gif')&&!busy&&<div className="gif-result"><img src={result.url} alt="转换完成的 GIF"/><div><strong>你的 GIF 已生成</strong><p>{bytes(result.size)} · {result.fps} 帧/秒 · {Number(result.clipDuration.toFixed(1))} 秒</p><button className="text-button" onClick={saveAgain} disabled={!folder||locked}>再次保存 <ArrowDown size={14}/></button></div></div>}</div>
   <footer><span>拾片 <span className="footer-dot">/</span> 留住每一段好画面</span><span>@是品薇吖</span></footer>
  </main>
 </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
