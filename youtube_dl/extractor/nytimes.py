# coding: utf-8
from __future__ import unicode_literals

import hmac
import hashlib
import base64

from .common import InfoExtractor
from ..utils import (
    float_or_none,
    int_or_none,
    js_to_json,
    parse_iso8601,
    mimetype2ext,
    determine_ext,
)


class NYTimesBaseIE(InfoExtractor):
    _SECRET = b'pX(2MbU2);4N{7J8)>YwKRJ+/pQ3JkiU2Q^V>mFYv6g6gYvt6v'

    def _extract_video_from_id(self, video_id):
        # Authorization generation algorithm is reverse engineered from `signer` in
        # http://graphics8.nytimes.com/video/vhs/vhs-2.x.min.js
        path = '/svc/video/api/v3/video/' + video_id
        hm = hmac.new(self._SECRET, (path + ':vhs').encode(), hashlib.sha512).hexdigest()
        video_data = self._download_json('http://www.nytimes.com' + path, video_id, 'Downloading video JSON', headers={
            'Authorization': 'NYTV ' + base64.b64encode(hm.encode()).decode(),
            'X-NYTV': 'vhs',
        }, fatal=False)
        if not video_data:
            video_data = self._download_json(
                'http://www.nytimes.com/svc/video/api/v2/video/' + video_id,
                video_id, 'Downloading video JSON')

        title = video_data['headline']

        def get_file_size(file_size):
            if isinstance(file_size, int):
                return file_size
            elif isinstance(file_size, dict):
                return int(file_size.get('value', 0))
            else:
                return None

        urls = []
        formats = []
        for video in video_data.get('renditions', []):
            video_url = video.get('url')
            format_id = video.get('type')
            if not video_url or format_id == 'thumbs' or video_url in urls:
                continue
            urls.append(video_url)
            ext = mimetype2ext(video.get('mimetype')) or determine_ext(video_url)
            if ext == 'm3u8':
                formats.extend(self._extract_m3u8_formats(
                    video_url, video_id, 'mp4', 'm3u8_native',
                    m3u8_id=format_id or 'hls', fatal=False))
            elif ext == 'mpd':
                continue
            #     formats.extend(self._extract_mpd_formats(
            #         video_url, video_id, format_id or 'dash', fatal=False))
            else:
                formats.append({
                    'url': video_url,
                    'format_id': format_id,
                    'vcodec': video.get('videoencoding') or video.get('video_codec'),
                    'width': int_or_none(video.get('width')),
                    'height': int_or_none(video.get('height')),
                    'filesize': get_file_size(video.get('file_size') or video.get('fileSize')),
                    'tbr': int_or_none(video.get('bitrate'), 1000),
                    'ext': ext,
                })
        self._sort_formats(formats)

        thumbnails = []
        for image in video_data.get('images', []):
            image_url = image.get('url')
            if not image_url:
                continue
            thumbnails.append({
                'url': 'http://www.nytimes.com/' + image_url,
                'width': int_or_none(image.get('width')),
                'height': int_or_none(image.get('height')),
            })

        publication_date = video_data.get('publication_date')
        timestamp = parse_iso8601(publication_date[:-8]) if publication_date else None

        return {
            'id': video_id,
            'title': title,
            'description': video_data.get('summary'),
            'timestamp': timestamp,
            'uploader': video_data.get('byline'),
            'duration': float_or_none(video_data.get('duration'), 1000),
            'formats': formats,
            'thumbnails': thumbnails,
        }

    def _extract_podcast_from_json(self, json, page_id, webpage):
        audio_data = self._parse_json(json, page_id, transform_source=js_to_json)['data']
        
        description = audio_data['track']['description']
        if not description:
            description = self._html_search_meta(['og:description', 'twitter:description'], webpage)

        episode_title = audio_data['track']['title'].strip("‘’") # strip curlyquotes
        episode_number = None
        episode = audio_data['podcast']['episode'].split()
        if episode:
            episode_number = int_or_none(episode[-1])
            video_id = episode[-1]
        else:
            video_id = page_id

        podcast_title = audio_data['podcast']['title']
        title = None
        if podcast_title:
            title = "%s: %s" % (podcast_title, episode_title)
        else:
            title = episode_title
        
        info_dict = {
            'id': video_id,
            'title': title,
            'creator': audio_data['track'].get('credit'),
            'series': podcast_title,
            'episode': episode_title,
            'episode_number': episode_number,
            'url': audio_data['track']['source'],
            'duration': audio_data['track'].get('duration'),
            'description': description,
        }
        
        return info_dict


class NYTimesIE(NYTimesBaseIE):
    _VALID_URL = r'https?://(?:(?:www\.)?nytimes\.com/video/(?:[^/]+/)+?|graphics8\.nytimes\.com/bcvideo/\d+(?:\.\d+)?/iframe/embed\.html\?videoId=)(?P<id>\d+)'

    _TESTS = [{
        'url': 'http://www.nytimes.com/video/opinion/100000002847155/verbatim-what-is-a-photocopier.html?playlistId=100000001150263',
        'md5': 'd665342765db043f7e225cff19df0f2d',
        'info_dict': {
            'id': '100000002847155',
            'ext': 'mov',
            'title': 'Verbatim: What Is a Photocopier?',
            'description': 'md5:93603dada88ddbda9395632fdc5da260',
            'timestamp': 1398631707,
            'upload_date': '20140427',
            'uploader': 'Brett Weiner',
            'duration': 419,
        }
    }, {
        'url': 'http://www.nytimes.com/video/travel/100000003550828/36-hours-in-dubai.html',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)

        return self._extract_video_from_id(video_id)


class NYTimesArticleIE(NYTimesBaseIE):
    _VALID_URL = r'https?://(?:www\.)?nytimes\.com/(.(?<!video))*?/(?:[^/]+/)*(?P<id>[^.]+)(?:\.html)?'
    _TESTS = [{
        'url': 'http://www.nytimes.com/2015/04/14/business/owner-of-gravity-payments-a-credit-card-processor-is-setting-a-new-minimum-wage-70000-a-year.html?_r=0',
        'md5': 'e2076d58b4da18e6a001d53fd56db3c9',
        'info_dict': {
            'id': '100000003628438',
            'ext': 'mov',
            'title': 'New Minimum Wage: $70,000 a Year',
            'description': 'Dan Price, C.E.O. of Gravity Payments, surprised his 120-person staff by announcing that he planned over the next three years to raise the salary of every employee to $70,000 a year.',
            'timestamp': 1429033037,
            'upload_date': '20150414',
            'uploader': 'Matthew Williams',
        }
    }, {
        'url': 'http://www.nytimes.com/2016/10/14/podcasts/revelations-from-the-final-weeks.html',
        'md5': 'e0d52040cafb07662acf3c9132db3575',
        'info_dict': {
            'id': '20',
            'title': "The Run-Up: He Was Like an Octopus",
            'ext': 'mp3',
            'description': 'We go behind the story of the two women who told us that Donald Trump touched them inappropriately (which he denies) and check in on Hillary Clinton’s campaign.',
        }
    }, {
        'url': 'http://www.nytimes.com/2016/10/16/books/review/inside-the-new-york-times-book-review-the-rise-of-hitler.html',
        'md5': '66fb5471d7ef15da98af176dc1af4cb9',
        'info_dict': {
            'id': 'inside-the-new-york-times-book-review-the-rise-of-hitler',
            'title': "The Rise of Hitler",
            'ext': 'mp3',
            'description': 'Adam Kirsch discusses Volker Ullrich\'s new biography of Hitler; Billy Collins talks about his latest collection of poems; and iO Tillett Wright on his new memoir, "Darling Days."',
            }
    }, {
        'url': 'http://www.nytimes.com/news/minute/2014/03/17/times-minute-whats-next-in-crimea/?_php=true&_type=blogs&_php=true&_type=blogs&_r=1',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        page_id = self._match_id(url)

        webpage = self._download_webpage(url, page_id)

        video_id = self._html_search_regex(r'data-videoid="(\d+)"', webpage, 'video id', None, False)
        if video_id is not None:
            return self._extract_video_from_id(video_id)
        
        data_json = self._html_search_regex(r'NYTD.FlexTypes.push\(({[^)]*)\)', webpage, 'json data', None, False);
        if data_json is not None:
            return self._extract_podcast_from_json(data_json, page_id, webpage)
        else:
            raise UnsupportedError(url)
