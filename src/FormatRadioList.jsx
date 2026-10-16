export default function FormatRadioList({labelledBy, options, value, onChange, disabled}) {
  return <div className="format-list" role="radiogroup" aria-labelledby={labelledBy}>
    {options.length ? options.map(option => <label key={option.value} className={`format-radio ${value===option.value?'is-selected':''}`}>
      <span>{option.label}</span>
      <input type="radio" name="clip-video-format" value={option.value} checked={value===option.value} disabled={disabled} onChange={()=>onChange(option.value)}/>
    </label>) : <p className="format-empty">获取视频后显示可用格式</p>}
  </div>;
}
