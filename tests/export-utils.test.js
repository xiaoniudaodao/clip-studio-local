import test from 'node:test';
import assert from 'node:assert/strict';
import {validateFilename, formatOption, formatOptionList, downloadOptions, clipStart, previewTime} from '../src/export-utils.js';

test('格式标签去掉音轨和内部编号，隐藏估算值',()=>{
 assert.equal(formatOption({ext:'mp4',height:1080,size:2097152,approximate:false,audio:false,id:'http123'}),'MP4 格式｜分辨率：1080p｜文件大小：2.00 MB');
 assert.equal(formatOption({ext:'mp4',height:720,size:999999,approximate:true}),'MP4 格式｜分辨率：720p');
});
test('片段框移到边界时保持固定时长，框内预览不改变起点',()=>{
 const start=clipStart(15,16,5);assert.equal(start,11);assert.equal(start+5,16);
 assert.equal(clipStart(-2,16,10),0);assert.equal(previewTime(20,start,5),16);assert.equal(previewTime(3,start,5),11);assert.equal(previewTime(12.5,start,5),12.5);assert.equal(start,11);
});
test('文件名允许留空，拒绝路径、控制字符与点文件名',()=>{
 validateFilename('');validateFilename('一个片段');for(const n of ['../xx','..','abc\u0000','name.'])assert.throws(()=>validateFilename(n));
});

test('相同格式分辨率的不同下载通道合并为一项，优先完整信息',()=>{
 const formats=[{id:'hls-720',ext:'mp4',height:720,audio:true,approximate:true}, {id:'http-720',ext:'mp4',height:720,audio:true,size:1234567,approximate:false}, {id:'hls-360',ext:'mp4',height:360,audio:true}, {id:'http-360',ext:'mp4',height:360,audio:true}, {id:'webm-720',ext:'webm',height:720}];
 const options=downloadOptions(formats);
 assert.deepEqual(options.map(f=>f.id),['http-720','http-360','webm-720']);
 assert.equal(new Set(options.map(formatOption)).size,options.length);
});
test('预览更新大小时仍保留用户已选的下载通道',()=>{
 const formats=[{id:'hls-720',ext:'mp4',height:720}, {id:'http-720',ext:'mp4',height:720,size:2097152,approximate:false}];
 assert.equal(downloadOptions(formats,'hls-720')[0].id,'hls-720');
 assert.equal(formatOption({ext:'mp4',size:null}),'MP4 格式');
});

test('四档变速对应缩短后的时间轴与片段时长', async () => {
  const {gifSpeeds, gifDurations, timeLabel} = await import('../src/export-utils.js');
  assert.deepEqual(gifSpeeds,[1,1.5,2,3]);
  assert.deepEqual(gifDurations,[5,10,15]);
  assert.equal(timeLabel(20/2),'00:10');
  assert.equal(timeLabel(20/3),'00:06.7');
  assert.equal(timeLabel(90/1.5),'01:00');
  assert.equal(clipStart(15,24,20),4);
});
test('自定义大小支持 KB 和 MB，留空不限定大小', async () => {
  const {customGifLimit} = await import('../src/export-utils.js');
  assert.equal(customGifLimit('','MB'),null);
  assert.equal(customGifLimit('0.25','MB'),262144);
  assert.equal(customGifLimit('256','KB'),262144);
  for(const input of ['0','-1','oops','Infinity','101'])assert.throws(()=>customGifLimit(input,'MB'));
});


test('预设是导出时长，3 倍速 5 秒覆盖 15 秒原视频', async()=>{
 const {durationForPreset}=await import('../src/export-utils.js');
 assert.equal(durationForPreset(5,3,15),15);
 assert.equal(durationForPreset(5,1.5,30),7.5);
 assert.equal(durationForPreset(10,2,16),16);
 assert.equal(clipStart(9,15,durationForPreset(5,3,15)),0);
});
test('自定义两端不能交叉、越界，内部预览限定在新选区', async()=>{
 const {resizeClip}=await import('../src/export-utils.js');
 assert.deepEqual(resizeClip(0,16,'start',4,16),{start:4,end:16});
 assert.deepEqual(resizeClip(4,16,'end',11.3,16),{start:4,end:11.3});
 assert.deepEqual(resizeClip(4,11.3,'start',-5,16),{start:0,end:11.3});
 assert.deepEqual(resizeClip(4,11.3,'end',100,16),{start:4,end:16});
 assert.equal(resizeClip(4,11.3,'end',0,16).end,4.1);
 assert.ok(Math.abs(resizeClip(4,11.3,'start',20,16).start-11.2)<1e-9);
 assert.equal(previewTime(15,4,7.3),11.3);
});


test('同组格式仅在每个可选项都有确定大小时展示全部大小',()=>{
 const known={id:'720',ext:'mp4',height:720,size:2097152};
 const other={id:'360',ext:'mp4',height:360,size:1048576};
 assert.ok(formatOptionList([known,other]).every(f=>f.label.includes('文件大小')));
 for(const size of [undefined,null,0,Infinity]){
  assert.ok(formatOptionList([known,{...other,size}]).every(f=>!f.label.includes('文件大小')));
 }
 assert.ok(formatOptionList([known,{...other,approximate:true}]).every(f=>!f.label.includes('文件大小')));
 assert.deepEqual(formatOptionList([]),[]);
 const duplicates=[known,{...known,id:'hls',size:undefined},other];
 assert.equal(formatOptionList(duplicates).length,2);
 assert.ok(formatOptionList(duplicates).every(f=>f.label.includes('文件大小')));
 assert.ok(formatOptionList(duplicates,'hls').every(f=>!f.label.includes('文件大小')));
});
