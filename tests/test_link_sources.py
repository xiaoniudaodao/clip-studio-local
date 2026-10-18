import unittest
from unittest.mock import MagicMock, patch
import server
from link_sources import normalize_video_url, bilibili_source, source_error_message, SourceError

class LinkSourcesTests(unittest.TestCase):
    def test_clipboard_wrappers_and_escapes(self):
        expected='https://www.bilibili.com/video/BV1dVYB6XESR/?share_source=copy_web'
        for value in [expected,expected+'\u00a0',r'https\://www\.bilibili.com/video/BV1dVYB6XESR/?share_source=copy_web',f'分享视频 {expected} 看看吧',f'[{expected}]({expected})']:
            self.assertEqual(normalize_video_url(value),expected)
        self.assertEqual(normalize_video_url('BV1dVYB6XESR'),'https://www.bilibili.com/video/BV1dVYB6XESR/')
    def test_deduplication_preserves_embedded_urls_and_tokens(self):
        url='https://openai.com/zh-Hans-CN/business/?video=1224965570'
        self.assertEqual(normalize_video_url(url+url),url)
        url='https://example.com/video?next=https://other.example/x&token=a%2Fb%3D'
        self.assertEqual(normalize_video_url(url),url)
        self.assertEqual(normalize_video_url('https://example.com/x?a=1&amp;b=2'),'https://example.com/x?a=1&b=2')
        self.assertEqual(normalize_video_url('demo'),'demo')
        for url in ['你好','ftp://example.com/x','https://user:pass@example.com/video']:
            with self.assertRaises(SourceError):normalize_video_url(url)
    def test_normalization_reaches_real_parse_source_boundary(self):
        fake=MagicMock();fake.__enter__.return_value.extract_info.return_value={'id':'x','title':'x','duration':1,'formats':[{'format_id':'x','ext':'mp4','url':'https://cdn.example/video.mp4','vcodec':'h264','acodec':'aac'}]}
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]),patch.object(server,'bilibili_source',return_value=None),patch.object(server.yt_dlp,'YoutubeDL',return_value=fake):
            result=server.parse_source(r'这是分享 https\://www\.bilibili.com/video/BV1dVYB6XESR/ 完整链接')
        self.assertEqual(result['sourceUrl'],'https://www.bilibili.com/video/BV1dVYB6XESR/')
        self.assertEqual(fake.__enter__.return_value.extract_info.call_args.args[0],result['sourceUrl'])
    def test_bilibili_uses_actual_anonymous_quality_and_selected_page(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if '/view?' in url:return {'code':0,'data':{'title':'test','pages':[{'cid':11,'duration':3},{'cid':22,'duration':4}]}}
            return {'code':0,'data':{'quality':16,'timelength':4000,'durl':[{'url':'https://cdn.example/a.mp4','size':1234}]}}
        info=bilibili_source('https://www.bilibili.com/video/BV1dVYB6XESR/?p=2',fetch)
        self.assertIn('cid=22',calls[-1]);self.assertEqual(info['formats'][0]['height'],360)
        self.assertEqual(info['formats'][0]['filesize'],1234)
        self.assertIn('Referer',info['formats'][0]['http_headers'])
        self.assertTrue(info['_direct_source'])
        self.assertIsNone(bilibili_source('https://www.youtube.com/shorts/test',fetch))
    def test_restricted_bilibili_is_not_claimed_downloadable(self):
        def fetch(url):
            if '/view?' in url:return {'code':0,'data':{'pages':[{'cid':11}]}}
            return {'code':-10403,'data':{}}
        with self.assertRaises(SourceError):bilibili_source('https://www.bilibili.com/video/BV1dVYB6XESR/',fetch)
    def test_domestic_failures_are_actionable_without_leaking_tokens(self):
        text=source_error_message(Exception('Fresh cookies (not necessarily logged in) are needed'),'https://v.douyin.com/x')
        self.assertIn('小号',text)
        self.assertIn('小红书',source_error_message(Exception('No video formats found!'),'https://www.xiaohongshu.com/explore/x'))
        self.assertNotIn('sensitive',source_error_message(Exception('https://example.com/?token=sensitive')))
