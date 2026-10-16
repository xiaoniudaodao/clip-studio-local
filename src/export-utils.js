export const folderMissingMessage = '找不到指定的位置，请重新设置保存文件夹。';
export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
export const clipStart = (value, length, duration) => clamp(value, 0, Math.max(0, length - duration));
export const previewTime = (value, start, duration) => clamp(value, start, start + duration);
export const gifSpeeds = [1, 1.5, 2, 3];
export const gifDurations = [5, 10, 15];
export const durationForPreset = (seconds, speed, length) => Math.min(seconds * speed, length);
export function resizeClip(start, end, edge, value, length) {
  const minimum = Math.min(.1, length);
  return edge === 'start'
    ? {start: clamp(value, 0, end - minimum), end}
    : {start, end: clamp(value, start + minimum, length)};
}
export function timeLabel(seconds) {
  const tenths = Math.round(Math.max(0, seconds || 0) * 10);
  const minutes = Math.floor(tenths / 600);
  const rest = Math.floor(tenths / 10) % 60;
  return `${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}${tenths % 10 ? '.' + tenths % 10 : ''}`;
}
export function customGifLimit(value, unit) {
  if (!String(value).trim()) return null;
  const number = Number(value);
  const bytes = Math.floor(number * (unit === 'KB' ? 1024 : 1048576));
  if (!Number.isFinite(number) || number <= 0 || bytes < 51200 || bytes > 104857600) {
    throw Error('自定义导出大小请填写 50 KB 到 100 MB 之间的数值。');
  }
  return bytes;
}
export const sizeText = n => n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 / 1024).toFixed(2)} MB`;
export function formatOption(f, {showSize = true} = {}) {
  const parts = [`${f.ext.toUpperCase()} 格式`];
  if (f.height) parts.push(`分辨率：${f.height}p`);
  if (showSize && Number.isFinite(f.size) && f.size > 0 && !f.approximate) parts.push(`文件大小：${sizeText(f.size)}`);
  return parts.join('｜');
}
export function downloadOptions(formats, preferredId = '') {
  const choices = new Map();
  const score = f => (f.id === preferredId ? 100 : 0)
    + (f.size > 0 && !f.approximate ? 8 : 0)
    + (f.audio === true ? 4 : 0)
    + (/^https?(?:[-_]|$)/i.test(f.id) ? 2 : 0);
  for (const f of formats) {
    const key = `${f.ext.toLowerCase()}|${f.height || ''}`;
    const previous = choices.get(key);
    if (!previous || score(f) > score(previous)) choices.set(key, f);
  }
  return [...choices.values()];
}
export function formatOptionList(formats, preferredId = '') {
  const options = downloadOptions(formats, preferredId);
  const showSize = options.length > 0 && options.every(f => Number.isFinite(f.size) && f.size > 0 && !f.approximate);
  return options.map(f => ({value: f.id, label: formatOption(f, {showSize})}));
}
export function validateFilename(value) {
  if (!value.trim()) return;
  if (/[\\/:*?"<>|\x00-\x1f]/.test(value) || /^\.+$/.test(value.trim()) || /[. ]$/.test(value) || value.length > 100) {
    throw Error('请使用有效的文件名，避免 / : 等特殊字符，长度不超过 100 个字。');
  }
}
