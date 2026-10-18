import sys,unittest,tempfile,threading
from pathlib import Path
from unittest.mock import patch
import server
class PreviewFallbackTest(unittest.TestCase):
 def test_preview_uses_another_real_format_when_first_is_rejected(self):
  source={'id':'fallback-test','formats':[{'id':'blocked','height':480,'ext':'mp4','audio':True},{'id':'available','height':640,'ext':'mkv','audio':True}],'info':{},'files':{},'file_lock':threading.Lock()}
  demo=server.ROOT/'public/assets/videos/demo.mp4';calls=[]
  def download(s,fid,job):
   calls.append(fid)
   if fid=='blocked':raise server.UserError('HTTP 403')
   return demo
  with tempfile.TemporaryDirectory() as temp,patch.object(server,'CACHE',Path(temp)),patch.dict(server.SOURCES,{'fallback-test':source}),patch.object(server,'download_source',side_effect=download),patch.object(server,'probe',return_value={'duration':16,'width':854,'height':480,'audio':True}),patch.object(server,'run',side_effect=lambda args,**kwargs:Path(args[-1]).write_bytes(b'preview')):
   server.JOBS['fallback-job']={};server.execute_job('fallback-job',{'sourceId':'fallback-test','kind':'preview'})
  self.assertEqual(server.JOBS['fallback-job']['status'],'done')
  self.assertEqual(server.JOBS['fallback-job']['formatId'],'available')
  self.assertIn('available',calls)

