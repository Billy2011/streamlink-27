import logging
import re

from streamlink.compat import urljoin
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.plugin.api import validate
from streamlink.stream import HLSStream, HTTPStream

log = logging.getLogger(__name__)


@pluginmatcher(re.compile(
    r"https?://(?:www\.)?booyah\.live/(?:(?P<type>channels|clips|vods)/)?(?P<id>[^?]+)"
))
class Booyah(Plugin):
    auth_api_url = 'https://booyah.live/api/v3/auths/sessions'
    vod_api_url = 'https://booyah.live/api/v3/playbacks/{0}'
    live_api_url = 'https://booyah.live/api/v3/channels/{0}'
    streams_api_url = 'https://booyah.live/api/v3/channels/{0}/streams'

    auth_schema = validate.Schema({
        'expiry_time': int,
        'uid': int,
    })

    vod_schema = validate.Schema({
        'user': {
            'nickname': validate.text,
        },
        'playback': {
            'name': validate.text,
            'endpoint_list': [{
                'stream_url': validate.url(),
                'resolution': validate.all(
                    int,
                    validate.transform(lambda x: '{}p'.format(x)),
                ),
            }],
        },
    })

    live_schema = validate.Schema({
        'user': {
            'nickname': validate.text,
        },
        'channel': {
            'channel_id': int,
            'name': validate.text,
            'is_streaming': bool,
            validate.optional('hostee'): {
                'channel_id': int,
                'nickname': validate.text,
            },
        },
    })

    streams_schema = validate.Schema({
        'stream_addr_list': [{
            'resolution': validate.text,
            'url_path': validate.text,
        }],
        'mirror_list': [{
            'url_domain': validate.url(),
        }],
    })

    author = None
    category = None
    title = None

    def get_author(self):
        return self.author

    def get_category(self):
        return self.category

    def get_title(self):
        return self.title

    def do_auth(self):
        res = self.session.http.post(self.auth_api_url)
        self.session.http.json(res, self.auth_schema)

    def get_vod(self, id):
        res = self.session.http.get(self.vod_api_url.format(id))
        user_data = self.session.http.json(res, schema=self.vod_schema)

        self.author = user_data['user']['nickname']
        self.category = 'VOD'
        self.title = user_data['playback']['name']

        for stream in user_data['playback']['endpoint_list']:
            if stream['stream_url'].endswith('.mp4'):
                yield stream['resolution'], HTTPStream(
                    self.session,
                    stream['stream_url'],
                )
            else:
                yield stream['resolution'], HLSStream(
                    self.session,
                    stream['stream_url'],
                )

    def get_live(self, id):
        res = self.session.http.get(self.live_api_url.format(id))
        user_data = self.session.http.json(res, schema=self.live_schema)

        if user_data['channel']['is_streaming']:
            self.category = 'Live'
            stream_id = user_data['channel']['channel_id']
        elif 'hostee' in user_data['channel']:
            self.category = 'Hosted by {}'.format(user_data["channel"]["hostee"]["nickname"])
            stream_id = user_data['channel']['hostee']['channel_id']
        else:
            log.info('User is offline')
            return

        self.author = user_data['user']['nickname']
        self.title = user_data['channel']['name']

        res = self.session.http.get(self.streams_api_url.format(stream_id))
        streams = self.session.http.json(res, schema=self.streams_schema)

        for stream in streams['stream_addr_list']:
            if stream['resolution'] != 'Auto':
                for mirror in streams['mirror_list']:
                    yield stream['resolution'], HLSStream(
                        self.session,
                        urljoin(mirror['url_domain'], stream['url_path']),
                    )

    def _get_streams(self):
        self.do_auth()

        url_data = self.match.groupdict()
        log.debug('ID={}'.format(url_data["id"]))

        if not url_data['type'] or url_data['type'] == 'channels':
            log.debug('Type=Live')
            return self.get_live(url_data['id'])
        else:
            log.debug('Type=VOD')
            return self.get_vod(url_data['id'])


__plugin__ = Booyah
