import React, {useEffect, useId, useLayoutEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {CaretDown, Check} from '@phosphor-icons/react';

// One dropdown for formats, GIF precision and size units.
export default function SelectMenu({id, label, value, options, onChange, disabled=false, className=''}) {
  const menuId=useId(), trigger=useRef(null), menu=useRef(null), search=useRef({text:'',time:0});
  const [open,setOpen]=useState(false), [active,setActive]=useState(0), [position,setPosition]=useState(null);
  const selected=Math.max(0,options.findIndex(o=>o.value===value));
  function reveal(index=selected){setActive(index);setOpen(true);}
  function choose(index){if(!options[index])return;onChange(options[index].value);setOpen(false);trigger.current?.focus();}
  useEffect(()=>{if(disabled)setOpen(false)},[disabled]);
  useLayoutEffect(()=>{
    if(!open)return;
    function place(){const r=trigger.current.getBoundingClientRect(), margin=8, width=Math.min(Math.max(r.width,92),window.innerWidth-16);const below=window.innerHeight-r.bottom-margin, above=r.top-margin, flip=below<Math.min(240,options.length*40+12)&&above>below;setPosition({left:Math.min(Math.max(margin,r.left),window.innerWidth-width-margin),width,maxHeight:Math.max(40,Math.min(280,flip?above:below)),...(flip?{bottom:window.innerHeight-r.top+5}:{top:r.bottom+5})});}
    function outside(e){if(!trigger.current?.contains(e.target)&&!menu.current?.contains(e.target))setOpen(false);}
    place();window.addEventListener('resize',place);window.addEventListener('scroll',place,true);document.addEventListener('pointerdown',outside);
    return()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);document.removeEventListener('pointerdown',outside)};
  },[open,options.length]);
  useEffect(()=>{if(open)menu.current?.children[active]?.scrollIntoView({block:'nearest'})},[open,active]);
  function key(e){
    if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?options.length-1:Math.max(0,Math.min(options.length-1,(open?active:selected)+(e.key==='ArrowDown'?1:-1)));if(open)setActive(next);else reveal(e.key==='ArrowUp'?options.length-1:selected);}
    else if(e.key==='Enter'||e.key===' '){e.preventDefault();if(open)choose(active);else reveal();}
    else if(e.key==='Escape'){e.preventDefault();setOpen(false);}
    else if(e.key==='Tab'){setOpen(false);}
    else if(e.key.length===1&&!e.metaKey&&!e.ctrlKey&&!e.altKey){const now=Date.now();search.current={text:(now-search.current.time<700?search.current.text:'')+e.key.toLowerCase(),time:now};const found=options.findIndex(o=>o.label.toLowerCase().startsWith(search.current.text));if(found>=0){if(open)setActive(found);else{reveal(found)}}}
  }
  return <>
    <button id={id} ref={trigger} type="button" role="combobox" aria-label={label} aria-haspopup="listbox" aria-expanded={open} aria-controls={open?menuId:undefined} aria-activedescendant={open?`${menuId}-${active}`:undefined} disabled={disabled} className={`select-trigger ${className}`} onClick={()=>open?setOpen(false):reveal()} onKeyDown={key}><span>{options[selected]?.label||'请选择'}</span><CaretDown size={13}/></button>
    {open&&position&&createPortal(<div ref={menu} id={menuId} role="listbox" aria-label={label} className="select-menu" style={position}>{options.map((o,i)=><div key={o.value} id={`${menuId}-${i}`} role="option" aria-selected={i===selected} className={`select-option ${i===active?'active':''} ${i===selected?'selected':''}`} onPointerDown={e=>e.preventDefault()} onMouseMove={()=>setActive(i)} onClick={()=>choose(i)}><span>{o.label}</span>{i===selected&&<Check size={15}/>}</div>)}</div>,document.body)}
  </>;
}
