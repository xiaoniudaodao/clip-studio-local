"""Optional integration check against a public CC0 sample video."""
import json,os,time,urllib.request,urllib.error
base='http://127.0.0.1:'+os.environ.get('CLIP_PORT','8766')
def get(path):
    with urllib.request.urlopen(base+path) as r:return json.load(r)
token=get('/api/health')['token']
def post(path,data):
    req=urllib.request.Request(base+path,json.dumps(data).encode(),{'Content-Type':'application/json','X-Clip-Token':token})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(e.read().decode()) from e
source=post('/api/resolve',{'url':'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'})
print('Resolved:', source['title'], source['formats'],flush=True)
for kind in ['preview','video','gif']:
    job=post('/api/jobs',{'sourceId':source['id'],'kind':kind,'formatId':source['formats'][0]['id'],'start':0,'duration':5,'limit':512000})
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        data=get('/api/jobs/'+job['id'])
        if data['status'] in ('done','error'):break
        time.sleep(.5)
    assert data['status']=='done',data
    request=urllib.request.Request(base+data['url'],headers={'Range':'bytes=0-99'})
    with urllib.request.urlopen(request) as r:
        assert r.status==206
        assert len(r.read())==100
    if kind=='gif':assert data['size']<=512000
    print(kind, data['size'], data.get('duration'),flush=True)
print('Public URL → metadata → preview → video → bounded GIF → HTTP range: PASS')
