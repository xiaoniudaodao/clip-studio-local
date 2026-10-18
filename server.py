"""Local-only video workbench. No browser cookies or account access."""
import copy, json, math, os, re, secrets, shutil, subprocess, threading, time, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
import yt_dlp
from link_sources import SourceError, normalize_video_url, bilibili_source, source_error_message
from export_storage import ExportStore, SaveError, native_file_picker, VIDEO_EXTENSIONS

ROOT = Path(__file__).resolve().parent

def load_env_file(path):
    # 本机配置写在 .env（不进仓库），格式见 .env.example；已设置的环境变量优先
    if not path.is_file(): return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), os.path.expanduser(value.strip().strip('"').strip("'")))

load_env_file(ROOT / '.env')
CACHE = ROOT / '.cache'
CACHE.mkdir(exist_ok=True)
EXPORTS = ExportStore(CACHE / 'save-settings.json')
TOKEN = secrets.token_urlsafe(32)
SOURCES, JOBS = {}, {}
LOCK = threading.Lock()
IMPORT_LOCK = threading.Lock()
WORKERS = threading.BoundedSemaphore(2)
PORT = int(os.environ.get('CLIP_PORT', '8766'))

def find_binary(name):
    candidates = [os.environ.get('CLIP_'+name.upper()),
                  shutil.which(name),
                  '/opt/homebrew/bin/'+name,
                  '/usr/local/bin/'+name]
    for candidate in candidates:
        if not candidate: continue
        try:
            check = subprocess.run([candidate,'-version'],capture_output=True,timeout=10)
            if check.returncode==0 and name.encode()+b' version' in check.stdout: return candidate
        except (OSError,subprocess.TimeoutExpired): pass
    raise RuntimeError(name+' 不可用，请安装适配本机的 FFmpeg 或设置 CLIP_'+name.upper())

FFMPEG, FFPROBE = find_binary('ffmpeg'), find_binary('ffprobe')

class UserError(Exception): pass

def run(args, timeout=180):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise UserError('视频处理失败。请尝试其他格式或片段。' + result.stderr[-300:])
    return result.stdout

def probe(path):
    data = json.loads(run([FFPROBE,'-v','error','-show_format','-show_streams','-of','json',str(path)]))
    stream = next((s for s in data['streams'] if s['codec_type']=='video'), None)
    if not stream: raise UserError('这个链接没有可处理的视频。')
    return {'duration':float(data['format'].get('duration',0)), 'width':stream['width'],'height':stream['height'],
            'audio':any(s['codec_type']=='audio' for s in data['streams'])}

def options():
    return {'quiet':True,'no_warnings':True,'noplaylist':True,'socket_timeout':25,'retries':2,
            'cachedir':False,'restrictfilenames':True,'ffmpeg_location':str(Path(FFMPEG).parent)}

def parse_source(value):
    try:
        url = normalize_video_url(value)
    except SourceError as error:
        raise UserError(str(error)) from None
    if url == 'demo':
        path = ROOT / 'public/assets/videos/demo.mp4'
        metadata = probe(path)
        formats = [{'id':'original','ext':'mp4','width':metadata['width'],'height':metadata['height'],
                    'size':path.stat().st_size,'approximate':False,'label':'MP4 · 原始视频','audio':True}]
        title, info = '流动的色彩 · 本地测试片', {'demo':True,'path':path}
    else:
        parsed = urlsplit(url)
        if not parsed.hostname or parsed.username or parsed.password: raise UserError('视频网址格式不正确。')
        import socket, ipaddress
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme=='https' else 80))
            proxy_active = bool(os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('ALL_PROXY') or os.environ.get('all_proxy'))
            fake_dns = ipaddress.ip_network('198.18.0.0/15')
            if any(not ipaddress.ip_address(a[4][0]).is_global and not (proxy_active and ipaddress.ip_address(a[4][0]).version==4 and ipaddress.ip_address(a[4][0]) in fake_dns) for a in addresses):
                raise UserError('请输入公开网站的视频链接。')
        except socket.gaierror: raise UserError('无法连接这个网站，请检查链接和网络。')
        try:
            info = bilibili_source(url)
            if info is None:
                with yt_dlp.YoutubeDL(options()) as ydl: info = ydl.extract_info(url, download=False)
        except Exception as error:
            raise UserError(source_error_message(error, url)) from None
        if not info or info.get('_type') in ('playlist','multi_video') or info.get('is_live'):
            raise UserError('请提供单条非直播视频链接。')
        raw = [f for f in info.get('formats', [info]) if f.get('vcodec') != 'none' and (f.get('vcodec') or f.get('ext') in ('mp4','webm','mkv','mov','flv','avi','m4v')) and f.get('url') and not f.get('has_drm')]
        audio = sorted([f for f in info.get('formats',[]) if f.get('vcodec')=='none' and f.get('acodec') not in ('none',None)],key=lambda f:f.get('abr') or 0,reverse=True)
        formats, selections = [], {}
        for f in raw:
            fid = str(f.get('format_id','original'))
            has_audio = f.get('acodec') not in ('none',None)
            selection = fid
            size = f.get('filesize') or f.get('filesize_approx')
            approx = not bool(f.get('filesize'))
            ext = f.get('ext','mp4')
            if not has_audio and audio:
                a = next((a for a in audio if a.get('ext')=='m4a'),audio[0])
                selection += '+' + str(a['format_id'])
                asize = a.get('filesize') or a.get('filesize_approx')
                size = size + asize if size and asize else None
                approx = True  # Final merged container size is only known after download.
                ext = 'mkv' # preserves video/audio codecs without claiming MP4 compatibility
            selections[fid] = selection
            formats.append({'id':fid,'ext':ext,'width':f.get('width'),'height':f.get('height'),'size':size,
                            'approximate':approx,'label':f.get('format_note') or fid,'audio':has_audio or bool(audio) if f.get('acodec') is not None else None})
        if not formats: raise UserError('未找到可下载的视频格式。网站可能需要登录，或暂不支持。')
        formats.sort(key=lambda f:(f.get('height') or 0, f.get('size') or 0),reverse=True)
        metadata = {'duration':info.get('duration') or 0,'width':info.get('width'),'height':info.get('height')}
        title = info.get('title') or '视频'
        info['_selections'] = selections
        info['_source_url'] = url
    sid = uuid.uuid4().hex
    source = {'id':sid,'title':title,'formats':formats,'sourceUrl':url,**metadata,'created':time.time()}
    with LOCK: SOURCES[sid] = {**source,'info':info,'files':{},'file_lock':threading.Lock()}
    return source

def register_local(path):
    """Register a video chosen through the OS file dialog as a source, like the demo clip."""
    path = Path(path)
    if not path.is_file(): raise UserError('找不到所选的视频文件。')
    if path.suffix.lower().lstrip('.') not in VIDEO_EXTENSIONS: raise UserError('请选择常见格式的视频文件。')
    try: metadata = probe(path)
    except UserError: raise UserError('这个文件不是可处理的视频。')
    if metadata['duration'] <= 0: raise UserError('无法读取视频时长，请换一个文件。')
    ext = path.suffix.lower().lstrip('.') or 'mp4'
    formats = [{'id':'original','ext':ext,'width':metadata['width'],'height':metadata['height'],
                'size':path.stat().st_size,'approximate':False,'label':ext.upper()+' · 本地视频','audio':metadata['audio']}]
    sid = uuid.uuid4().hex
    source = {'id':sid,'title':path.stem,'formats':formats,'local':True,**metadata,'created':time.time()}
    with LOCK: SOURCES[sid] = {**source,'info':{'local':True,'path':path},'files':{},'file_lock':threading.Lock()}
    return source

UPLOAD_LIMIT = 4 * 1024 * 1024 * 1024

def import_upload(stream, length, filename):
    """Store a file dropped onto the page under .cache/uploads and register it like a local file."""
    if length <= 0: raise UserError('没有收到文件内容。')
    if length > UPLOAD_LIMIT: raise UserError('文件超过 4 GB，请选择更小的视频。')
    original = Path(filename or 'video').name
    suffix = Path(original).suffix.lower().lstrip('.')
    if suffix not in VIDEO_EXTENSIONS: raise UserError('请拖入常见格式的视频文件（mp4、mov、webm、mkv 等）。')
    name = (safe_name(Path(original).stem) or 'video') + '.' + suffix
    dest = CACHE/'uploads'/uuid.uuid4().hex
    dest.mkdir(parents=True,exist_ok=True)
    path = dest/name
    try:
        with path.open('wb') as out:
            remaining = length
            while remaining:
                chunk = stream.read(min(1024*1024,remaining))
                if not chunk: raise UserError('文件传输中断，请重新拖入。')
                out.write(chunk); remaining -= len(chunk)
        return register_local(path)
    except Exception:
        shutil.rmtree(dest,ignore_errors=True); raise

def import_local():
    if not IMPORT_LOCK.acquire(blocking=False): raise UserError('文件选择窗口已打开，请先完成选择。')
    try:
        movies = Path.home()/'Movies'
        chosen = native_file_picker(str(movies) if movies.is_dir() else '')
        if not chosen: return {'cancelled':True}
        return register_local(chosen)
    finally: IMPORT_LOCK.release()

def download_source(source, fid, job):
    fmt = next((f for f in source['formats'] if f['id']==fid),None)
    if not fmt: raise UserError('请选择一个有效的视频格式。')
    with source['file_lock']:
        if fid in source['files']: return source['files'][fid]
        if source['info'].get('demo') or source['info'].get('local'): return source['info']['path']
        dest = CACHE / source['id'] / secrets.token_hex(5)
        dest.mkdir(parents=True,exist_ok=True)
        def progress(data):
            if data['status']=='downloading':
                total = data.get('total_bytes') or data.get('total_bytes_estimate')
                job.update(message='正在获取视频文件…',progress=min(70, int(data.get('downloaded_bytes',0)/total*70)) if total else 5)
        opts = {**options(),'format':source['info']['_selections'][fid], 'outtmpl':str(dest/'video.%(ext)s'),
                'merge_output_format':fmt['ext'],'progress_hooks':[progress]}
        # Reuse the resolved snapshot: a second webpage extraction can be rejected
        # even while its already-issued media URLs are valid. Each worker gets a copy.
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.process_ie_result(copy.deepcopy(source['info']), download=True)
        files = [p for p in dest.glob('video.*') if p.suffix not in ('.part','.ytdl')]
        if not files: raise UserError('未能完成下载，请重试。')
        path = max(files,key=lambda p:p.stat().st_size)
        source['files'][fid] = path
        return path

def safe_name(title):
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', title)[:90].strip('. ') or '视频'

GIF_QUALITY = {'low':(320,8,64), 'medium':(540,12,128), 'high':(854,20,256)}

def validate_gif_settings(start, duration, limit, speed, quality):
    if not math.isfinite(start) or start < 0 or not math.isfinite(duration) or duration <= 0:
        raise UserError('请选取有效的视频片段。')
    if speed not in (1,1.5,2,3) or quality not in GIF_QUALITY:
        raise UserError('请选择提供的变速档位和 GIF 精度。')
    if limit is not None and (not isinstance(limit,int) or isinstance(limit,bool) or not 51200 <= limit <= 104857600):
        raise UserError('自定义导出大小请填写 50 KB 到 100 MB 之间的数值。')

def convert_gif(path, output, start, duration, limit, job, speed=1, quality='medium'):
    validate_gif_settings(start,duration,limit,speed,quality)
    initial = GIF_QUALITY[quality]
    fallback = [(640,15,128),(540,12,96),(480,10,80),(400,10,64),(360,8,64),(300,8,48),(240,6,32),(180,5,24),(128,4,16),(96,3,8)]
    attempts = [initial]
    if limit is not None:
        attempts += [p for p in fallback if all(a<=b for a,b in zip(p,initial)) and p!=initial]
    for i,(width,fps,colors) in enumerate(attempts):
        job.update(message=f'正在转换 GIF · 第 {i+1} 次调整',progress=72+int(i/len(attempts)*25))
        graph = f'setpts=(PTS-STARTPTS)/{speed},fps={fps},scale=min({width}\\,iw):-1:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3'
        run([FFMPEG,'-y','-v','error','-ss',str(start),'-t',str(duration),'-i',str(path),'-t',str(duration/speed),'-filter_complex',graph,'-loop','0',str(output)])
        size = output.stat().st_size
        if limit is None or size < limit: return {'size':size,'width':probe(output)['width'],'fps':fps,'colors':colors,'attempts':i+1,'gifDuration':probe(output)['duration'],'speed':speed,'quality':quality}
    output.unlink(missing_ok=True)
    raise UserError('无法转换成所选文件大小，请选择更大的文件大小或改选 5 秒。')

def execute_job(jid, data):
    job = JOBS[jid]
    with WORKERS:
        try:
            source = SOURCES.get(data.get('sourceId'))
            if not source: raise UserError('视频已失效，请重新获取。')
            kind = data.get('kind')
            if kind not in ('preview','video','gif'): raise UserError('操作无效。')
            fid = data.get('formatId')
            if kind in ('preview','gif'):
                choices = sorted(source['formats'],key=lambda f:abs((f.get('height') or 480)-480))
                fid = next((f['id'] for f in choices if f['audio'] and f['ext']=='mp4'),choices[0]['id'])
            job.update(status='running',message='正在获取视频文件…')
            if kind=='gif':
                start, duration = float(data.get('start',0)), float(data.get('duration',5))
                limit = data.get('limit')
                speed = float(data.get('speed',1))
                quality = data.get('quality','medium')
                validate_gif_settings(start,duration,limit,speed,quality)
            if kind in ('preview','gif'):
                # Some sites advertise a combined stream but reject its media URL.
                # Preview/GIF may use another public stream; video keeps the exact user's selection.
                alternatives = sorted(source['formats'], key=lambda f: (
                    f['id'] not in source['files'], not bool(f.get('audio')),
                    abs((f.get('height') or 480)-480)))
                candidates = [fid] + [f['id'] for f in alternatives if f['id'] != fid]
                for attempt, candidate in enumerate(candidates[:3]):
                    try:
                        path = download_source(source,candidate,job)
                        fid = candidate
                        break
                    except Exception:
                        if attempt == min(3,len(candidates))-1:
                            raise
                        job.update(message='正在尝试其他可播放格式…')
            else:
                path = download_source(source,fid,job)
            result = {}
            if kind in ('preview','gif'):
                actual = probe(path)
                if kind=='gif':
                    if start >= actual['duration'] or start+duration > actual['duration']+.15:
                        raise UserError('片段超出了视频时长，请缩短或调整起点。')
                    path_out = CACHE/f'{jid}.gif'
                    result = convert_gif(path,path_out,start,duration,limit,job,speed,quality)
                    path = path_out
                else:
                    # Standardize playback for browsers; keep selected original formats for downloads.
                    output = CACHE/f'{jid}.mp4'
                    job.update(message='正在准备可播放的预览…',progress=75)
                    run([FFMPEG,'-y','-v','error','-i',str(path),'-vf','scale=min(854\\,iw):-2','-c:v','libx264','-preset','ultrafast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(output)],timeout=600)
                    path = output
                    result.update(actual)
                    result.update(formatId=fid, originalSize=download_source(source,fid,job).stat().st_size)
            job.update(status='done',message='处理完成',progress=100,path=str(path),url=f'/media/{jid}',
                       filename=('动图_' if kind=='gif' else '视频_')+jid[:8]+path.suffix,size=path.stat().st_size,**{k:v for k,v in result.items() if k!='size'})
        except Exception as error:
            msg = str(error)
            if not isinstance(error,(UserError, SourceError)):
                msg = source_error_message(error, source.get('info', {}).get('_source_url', '') if source else '')
            job.update(status='error',message=msg)

def new_job(data):
    jid = uuid.uuid4().hex
    with LOCK: JOBS[jid] = {'id':jid,'kind':data.get('kind'),'status':'queued','progress':0,'message':'等待处理…'}
    threading.Thread(target=execute_job,args=(jid,data),daemon=True).start()
    return {'id':jid}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_json(self,data,status=200):
        raw = json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def valid_host(self):
        return self.headers.get('Host','').split(':')[0] in ('127.0.0.1','localhost')
    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or self.headers.get('X-Clip-Token') != TOKEN or (origin and urlsplit(origin).hostname not in ('localhost','127.0.0.1')):
            return self.send_json({'error':'请从本地工具页面发起操作。'},403)
        try:
            length = int(self.headers.get('Content-Length',0))
            if self.path=='/api/import-upload':
                return self.send_json(import_upload(self.rfile,length,unquote(self.headers.get('X-Clip-Filename',''))))
            if length > 16000: raise UserError('链接过长。')
            data = json.loads(self.rfile.read(length))
            if self.path=='/api/save-location': return self.send_json(EXPORTS.choose())
            if self.path=='/api/save':
                job = JOBS.get(str(data.get('jobId','')))
                if not job or job.get('status')!='done' or job.get('kind') not in ('video','gif'):
                    raise UserError('文件尚未生成，请先获取并下载视频。')
                return self.send_json(EXPORTS.save(job['path'],str(data.get('filename','')),job['kind']))
            if self.path=='/api/resolve': return self.send_json(parse_source(str(data.get('url',''))))
            if self.path=='/api/import-local': return self.send_json(import_local())
            if self.path=='/api/jobs': return self.send_json(new_job(data),202)
            return self.send_json({'error':'接口不存在'},404)
        except SaveError as e:
            self.send_json({'error':str(e),'code':e.code},400)
        except Exception as e:
            self.send_json({'error':re.sub(r'\x1b\[[0-9;]*m','',str(e))[-600:]},400)
    def do_GET(self):
        if not self.valid_host(): return self.send_json({'error':'仅支持本机访问'},403)
        parsed = urlsplit(self.path); route = parsed.path
        if route=='/api/health': return self.send_json({'ok':True,'token':TOKEN,'ffmpeg':True})
        if route=='/api/save-location': return self.send_json(EXPORTS.location())
        if route.startswith('/api/jobs/'):
            job = JOBS.get(route.split('/')[-1])
            return self.send_json({k:v for k,v in job.items() if k!='path'}) if job else self.send_json({'error':'任务不存在'},404)
        if route.startswith('/media/'):
            job = JOBS.get(route.split('/')[-1])
            if not job or job.get('status')!='done': return self.send_json({'error':'文件尚未生成'},404)
            return self.serve_file(Path(job['path']),job['filename'] if parsed.query=='download' else None)
        path = (ROOT/'dist'/unquote(route).lstrip('/')).resolve()
        if not path.is_relative_to(ROOT/'dist'): return self.send_json({'error':'路径无效'},403)
        if not path.is_file():
            if Path(route).suffix: return self.send_json({'error':'文件不存在'},404)
            path = ROOT/'dist/index.html'
        if path.exists(): return self.serve_file(path)
        return self.send_json({'error':'请先执行 npm run build'},503)
    def serve_file(self,path,download=None):
        import mimetypes
        size = path.stat().st_size; start,end = 0,size-1; status = 200
        range_header = self.headers.get('Range')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            if not match or not any(match.groups()): return self.send_json({'error':'无效的范围'},416)
            a,b = match.groups()
            if not a: start = max(0,size-int(b))
            else: start,end = int(a),min(int(b),size-1) if b else size-1
            if start> end or start>=size:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
            status = 206
        self.send_response(status)
        self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
        self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(end-start+1)); self.send_header('Accept-Ranges','bytes')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if download:
            from urllib.parse import quote
            self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(download))
        self.end_headers()
        try:
            with path.open('rb') as file:
                file.seek(start); remaining=end-start+1
                while remaining:
                    chunk=file.read(min(1024*1024,remaining))
                    if not chunk:break
                    self.wfile.write(chunk); remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):pass

if __name__=='__main__':
    try:
        local_server = ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError as error:
        raise SystemExit(f'无法启动：端口 {PORT} 可能已被占用。请用 CLIP_PORT 指定其他端口。({error})')
    print(f'拾片已启动，请在 Microsoft Edge 打开：http://127.0.0.1:{PORT}',flush=True)
    local_server.serve_forever()
