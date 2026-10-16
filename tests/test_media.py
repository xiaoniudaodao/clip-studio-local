import json, tempfile, unittest
from pathlib import Path
import server

class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = server.parse_source('demo')
        cls.path = server.ROOT / 'public/assets/videos/demo.mp4'
    def test_metadata_matches_actual_file(self):
        self.assertAlmostEqual(self.source['duration'],16,delta=.1)
        self.assertEqual(self.source['formats'][0]['size'],self.path.stat().st_size)
    def test_gif_five_seconds_below_500kb(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'test.gif'
            result=server.convert_gif(self.path,out,2,5,512000,{})
            self.assertLessEqual(out.stat().st_size,512000)
            self.assertGreater(out.stat().st_size,1000)
            self.assertAlmostEqual(server.probe(out)['duration'],5,delta=.3)
    def test_gif_ten_seconds_below_2mb(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'test.gif'
            result=server.convert_gif(self.path,out,3,10,2097152,{})
            self.assertLessEqual(out.stat().st_size,2097152)
            self.assertAlmostEqual(server.probe(out)['duration'],10,delta=.3)
    def test_invalid_range_and_duration_rejected(self):
        for start,duration in ((15,5),(0,20),(-1,5)):
            jid='invalid_'+str(start)+'_'+str(duration)
            server.JOBS[jid]={}
            server.execute_job(jid,{'sourceId':self.source['id'],'kind':'gif','start':start,'duration':duration})
            self.assertEqual(server.JOBS[jid]['status'],'error')
    def test_invalid_format_rejected(self):
        with self.assertRaises(server.UserError):
            server.download_source(server.SOURCES[self.source['id']],'unknown',{})
    def test_speed_changes_export_duration_and_keeps_size_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            for speed, expected in ((1,5),(1.5,5/1.5),(2,2.5),(3,5/3)):
                out=Path(temp)/f'speed-{speed}.gif'
                result=server.convert_gif(self.path,out,7,5,512000,{},speed)
                self.assertLessEqual(out.stat().st_size,512000)
                self.assertAlmostEqual(result['gifDuration'],expected,delta=.3)
                self.assertAlmostEqual(server.probe(out)['duration'],expected,delta=.3)
    def test_invalid_speed_rejected(self):
        for speed,duration in ((0,5),(4,5),(float('nan'),5),(.5,10)):
            jid=f'invalid_speed_{speed}_{duration}'
            server.JOBS[jid]={}
            server.execute_job(jid,{'sourceId':self.source['id'],'kind':'gif','speed':speed,'duration':duration})
            self.assertEqual(server.JOBS[jid]['status'],'error')
    def test_quality_levels_and_optional_size_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            widths=[]
            for quality in ('low','medium','high'):
                out=Path(temp)/f'{quality}.gif'
                result=server.convert_gif(self.path,out,2,5,None,{},3,quality)
                self.assertEqual(result['attempts'],1)
                self.assertEqual(result['quality'],quality)
                widths.append(server.probe(out)['width'])
            self.assertEqual(widths,sorted(set(widths)))
    def test_custom_size_is_strictly_below_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/'original.gif'
            server.convert_gif(self.path,original,2,5,None,{},1,'medium')
            limit=original.stat().st_size
            out=Path(temp)/'limited.gif'
            result=server.convert_gif(self.path,out,2,5,limit,{},1,'medium')
            self.assertGreater(result['attempts'],1)
            self.assertLess(out.stat().st_size,limit)
    def test_fifteen_and_twenty_second_source_clips(self):
        with tempfile.TemporaryDirectory() as temp:
            long_video=Path(temp)/'long.mp4'
            server.run([server.FFMPEG,'-v','error','-stream_loop','1','-i',str(self.path),'-t','24','-c','copy',str(long_video)])
            for duration,speed in ((15,1.5),(20,3)):
                out=Path(temp)/f'{duration}.gif'
                result=server.convert_gif(long_video,out,0,duration,400000,{},speed,'low')
                self.assertLess(result['size'],400000)
                self.assertAlmostEqual(result['gifDuration'],duration/speed,delta=.3)
    def test_invalid_quality_and_custom_limits_rejected(self):
        for limit,quality in ((0,'low'),(50000,'low'),(104857601,'low'),(float('nan'),'low'),(None,'ultra')):
            with self.assertRaises(server.UserError):
                server.validate_gif_settings(0,5,limit,1,quality)
    def test_custom_interval_exports_and_speed_covers_full_video(self):
        with tempfile.TemporaryDirectory() as temp:
            for start,duration,speed,expected in ((2.4,7.5,1.5,5),(0,15,3,5),(0,16,1,16)):
                out=Path(temp)/f'custom-{start}-{speed}.gif'
                result=server.convert_gif(self.path,out,start,duration,None,{},speed,'low')
                self.assertAlmostEqual(result['gifDuration'],expected,delta=.3)
    def test_zero_negative_and_nonfinite_custom_intervals_rejected(self):
        for start,duration in ((0,0),(0,-1),(0,float('nan')),(0,float('inf')),(float('nan'),5)):
            with self.assertRaises(server.UserError):
                server.validate_gif_settings(start,duration,None,1,'low')
    def test_local_and_file_urls_rejected(self):
        for url in ('file:///etc/passwd','http://127.0.0.1/test','http://localhost/test'):
            with self.assertRaises(server.UserError): server.parse_source(url)

    def test_local_file_registers_as_source_and_converts(self):
        local=server.register_local(self.path)
        self.assertTrue(local['local'])
        self.assertEqual(local['title'],'demo')
        self.assertAlmostEqual(local['duration'],16,delta=.1)
        self.assertEqual(local['formats'][0]['id'],'original')
        self.assertEqual(local['formats'][0]['size'],self.path.stat().st_size)
        self.assertEqual(server.download_source(server.SOURCES[local['id']],'original',{}),self.path)
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'local.gif'
            server.convert_gif(self.path,out,0,5,None,{},2,'low')
            self.assertAlmostEqual(server.probe(out)['duration'],2.5,delta=.3)
        with self.assertRaises(server.UserError): server.register_local(self.path.parent/'missing.mp4')
        with self.assertRaises(server.UserError): server.register_local(server.ROOT/'server.py')

if __name__=='__main__':unittest.main()
