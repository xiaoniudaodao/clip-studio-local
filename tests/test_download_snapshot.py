import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
import server
class ReextractTest(unittest.TestCase):
 def test_resolved_metadata_is_reused_for_download(self):
  import threading
  source={'id':'test','formats':[{'id':'x','ext':'mp4'}],'files':{},'file_lock':threading.Lock(),'info':{'id':'test','title':'test','formats':[{'format_id':'x','url':'https://cdn.example/video.mp4','ext':'mp4','vcodec':'h264','acodec':'aac'}],'_selections':{'x':'x'},'_source_url':'https://example.com/watch'}}
  fake=MagicMock()
  def process(info,download):
   self.assertTrue(download);self.assertEqual(info['id'],'test')
   dest=next(Path(temp).glob('test/*'));(dest/'video.mp4').write_bytes(b'resolved video')
  fake.__enter__.return_value.process_ie_result.side_effect=process
  with tempfile.TemporaryDirectory() as temp,patch.object(server,'CACHE',Path(temp)),patch.object(server.yt_dlp,'YoutubeDL',return_value=fake):
   self.assertEqual(server.download_source(source,'x',{}).read_bytes(),b'resolved video')
  fake.__enter__.return_value.download.assert_not_called()

