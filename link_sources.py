"""Clipboard URL cleanup and anonymous public Bilibili playback metadata."""
import html
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


class SourceError(Exception):
    pass


def normalize_video_url(value):
    text = html.unescape(str(value)).strip()
    text = re.sub(r'\\([:/\.])', r'\1', text)
    text = re.sub('[\u200b-\u200d\ufeff]', '', text)
    if text == 'demo':
        return text
    match = re.search(r'https?://[^\s<>\[\]"\']+', text, re.I)
    if not match:
        bare = re.fullmatch(r'BV[a-zA-Z0-9]{10}', text)
        if bare:
            return 'https://www.bilibili.com/video/' + text + '/'
        raise SourceError('没有找到视频网址，请复制包含 http:// 或 https:// 的分享链接。')
    url = match.group().split('](')[0].rstrip('，。；）)」』》>')
    # Only collapse identical concatenated URLs; preserve URL-valued query parameters.
    parts = re.split(r'(?=https?://)', url, flags=re.I)[1:]
    if len(parts) > 1 and all(part == parts[0] for part in parts):
        url = parts[0]
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise SourceError('视频网址格式不正确。')
    return url


PUBLIC_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
}


def public_json(url):
    with urlopen(Request(url, headers=PUBLIC_HEADERS), timeout=20) as response:
        return json.load(response)


def bilibili_source(url, fetch=public_json):
    parsed = urlsplit(url)
    if parsed.hostname not in ('www.bilibili.com', 'bilibili.com', 'm.bilibili.com'):
        return None
    match = re.search(r'/video/(BV[a-zA-Z0-9]{10}|av\d+)', parsed.path)
    if not match:
        raise SourceError('请复制 B 站单个视频的分享链接，暂不支持个人主页或合集。')
    identity = match.group(1)
    key, value = ('bvid', identity) if identity.startswith('BV') else ('aid', identity[2:])
    response = fetch('https://api.bilibili.com/x/web-interface/view?' + urlencode({key: value}))
    if response.get('code') != 0:
        raise SourceError('B 站未提供视频资料，视频可能已失效或需要登录。')
    data = response['data']
    try:
        page_index = int(parse_qs(parsed.query).get('p', ['1'])[0]) - 1
    except (ValueError, TypeError):
        raise SourceError('B 站分 P 页码无效。') from None
    pages = data.get('pages', [])
    if not 0 <= page_index < len(pages):
        raise SourceError('没有找到这条 B 站视频的对应分 P。')
    page = pages[page_index]
    # Anonymous playback returns the quality actually allowed by the site.
    playback = fetch('https://api.bilibili.com/x/player/playurl?' + urlencode({key: value, 'cid': page['cid'], 'qn': 64, 'fnval': 0, 'fourk': 0}))
    payload = playback.get('data') or {}
    segments = payload.get('durl') or []
    if playback.get('code') != 0 or len(segments) != 1 or not segments[0].get('url'):
        raise SourceError('B 站没有提供可直接下载的公开视频流；需要登录或会员的视频暂不支持。')
    media = segments[0]
    quality = payload.get('quality', 16)
    height = {16: 360, 32: 480, 64: 720, 80: 1080, 112: 1080, 116: 1080}.get(quality)
    return {
        'id': identity, 'title': data.get('title') or page.get('part') or identity,
        'duration': payload.get('timelength', 0) / 1000 or page.get('duration', 0),
        'width': None, 'height': height, '_direct_source': True,
        'formats': [{'format_id': str(quality), 'ext': 'mp4', 'height': height,
                     'url': media['url'], 'filesize': media.get('size'),
                     'vcodec': 'h264', 'acodec': 'aac', 'http_headers': PUBLIC_HEADERS.copy()}],
    }


def source_error_message(error, url=''):
    raw = re.sub(r'\x1b\[[0-9;]*m', '', str(error))
    lower = raw.lower()
    host = urlsplit(url).hostname or ''
    if isinstance(error, SourceError):
        return str(error)
    if 'douyin' in host and ('cookies' in lower or 'no video formats' in lower):
        return '抖音要求有效的访问会话，当前未连接抖音小号登录态，暂时无法解析这条链接。'
    if 'xiaohongshu' in host and ('no video formats' in lower or 'initial state' in lower):
        return '小红书没有返回可下载的视频。这条分享链接可能已失效或需要登录，请重新复制完整分享链接后重试。'
    if '412' in lower and 'bilibili' in host:
        return 'B 站暂时拒绝了视频请求（412），请稍后重试。'
    if '403' in lower or 'cloudflare' in lower:
        return '视频来源拒绝了请求或要求网站验证，当前无法直接获取；请尝试公开的视频播放页或视频直链。'
    if 'sign in' in lower or 'login' in lower or 'cookies' in lower:
        return '视频来源要求有效登录或访问会话，当前无法匿名下载这条链接。'
    if 'no video formats' in lower:
        return '没有找到可下载的视频，链接可能已失效、需要登录，或内容不是视频。'
    if 'timed out' in lower or 'timeout' in lower:
        return '连接视频来源超时，请检查网络后重试。'
    return '获取视频失败，请确认链接可公开播放后重试。'
