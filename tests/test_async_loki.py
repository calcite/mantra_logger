import asyncio

import pytest
import json

from loggate import setup_logging, get_logger


def check_call(request: dict, labels, msg, headers=None, url='http://loki'):
    # check loki url address
    assert request['url'] == url, \
        f"Wrong loki url {request['url']} != {url}"
    data = request['json']
    # check labels
    assert 'streams' in data
    assert 'stream' in data['streams'][0]
    assert labels == data['streams'][0]['stream']
    # headers
    if not headers:
        headers = {'Content-Type': 'application/json; charset=utf-8'}
    for k, val in headers.items():
        request['headers'][k]
    # check message
    assert len(data['streams'][0]['values']) > 0
    _msg = data['streams'][0]['values'][0][1]
    if isinstance(msg, dict):
        _msg = json.loads(_msg)
    assert msg == _msg


@pytest.mark.asyncio
async def test_simple(make_profile, async_session):
    """
    This is a simple test without any metadata
    """
    profiles = make_profile({
        'default.handlers.loki.class': 'loggate.loki.LokiAsyncioHandler'
    })
    setup_logging(profiles=profiles)

    logger = get_logger('component')
    logger.debug('Debug')
    logger.warning('Warning')
    logger.error('Error')
    logger.critical('Critical')

    await asyncio.sleep(.1)
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'debug'},
               {"msg": "Debug"})
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'warning'},
               {"msg": "Warning"})
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'error'},
               {"msg": "Error"})
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"})


@pytest.mark.asyncio
async def test_metadata(make_profile, async_session):
    """
    This is a test with metadata and metadata overwriting
    """
    profiles = make_profile({
        'default.handlers.loki.class': 'loggate.loki.LokiAsyncioHandler',
        'default.handlers.loki.meta': {
            'handler_meta': '000',
            'overwriteH': 'Z'
        },
        'default.handlers.loki.loki_tags': ['logger', 'level', 'meta']
    })
    setup_logging(profiles=profiles)

    logger = get_logger('component',
                        meta={'logger_meta': 'ABC', 'overwriteL': 'X'})
    logger.debug('Debug',
                 meta={'meta': 'DEF',
                       'overwriteL': 'Y',
                       'overwriteH': '111'})
    logger.warning('Warning',
                   meta={'meta': 'GHI',
                         'overwriteL': 'Y',
                         'overwriteH': '111'})
    logger.error('Error',
                 meta={'meta': 'JKL',
                       'overwriteL': 'Y',
                       'overwriteH': '111'})
    logger.critical('Critical',
                    meta={'meta': 'MNO',
                          'overwriteL': 'Y',
                          'overwriteH': '111'})

    await asyncio.sleep(.1)
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'debug', 'meta': 'DEF'},
               {"msg": "Debug",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'})
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'warning', 'meta': 'GHI'},
               {"msg": "Warning",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'
                })
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'error', 'meta': 'JKL'},
               {"msg": "Error",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'
                })
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical', 'meta': 'MNO'},
               {"msg": "Critical",
                'handler_meta': '000',
                'logger_meta': 'ABC',
                'overwriteH': '111',
                'overwriteL': 'Y'
                })


@pytest.mark.asyncio
async def test_loki_all_strategy(make_profile, async_session):
    """
    Test strategy all. The log message is send to all servers.
    """
    servers = ['http://loki1', 'http://loki2', 'http://loki3']
    profiles = make_profile({
        'default.handlers.loki.class': 'loggate.loki.LokiAsyncioHandler',
        'default.handlers.loki.strategy': 'all',
        'default.handlers.loki.urls': servers
    })
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    await asyncio.sleep(.1)
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               url='http://loki1')
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               url='http://loki2')
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               url='http://loki3')


@pytest.mark.asyncio
async def test_loki_fallback_strategy(make_profile, async_session, capsys):
    """
    Test strategy fallback. The log message is send to first server,
    if it failed we try to send it to others.
    """
    servers = ['http://loki1', 'http://loki2', 'http://loki3']
    profiles = make_profile({
        'default.handlers.loki.class': 'loggate.loki.LokiAsyncioHandler',
        'default.handlers.loki.strategy': 'fallback',
        'default.handlers.loki.timeout': 3,
        'default.handlers.loki.urls': servers
    })
    async_session.response_code = [400, 400, 400]
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    await asyncio.sleep(.1)
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               url='http://loki1')
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               url='http://loki2')
    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"},
               url='http://loki3')
    captured = capsys.readouterr()
    assert '--- Logging error ---' in captured.err


@pytest.mark.asyncio
async def test_loki_with_auth(make_profile, async_session, capsys):
    """
    Test strategy fallback. The log message is send to first server,
    if it failed we try to send it to others.
    """
    profiles = make_profile({
        'default.handlers.loki.class': 'loggate.loki.LokiAsyncioHandler',
        'default.handlers.loki.auth': ['username', 'password']
    })
    setup_logging(profiles=profiles)
    logger = get_logger('component')
    logger.critical('Critical')

    await asyncio.sleep(.1)

    check_call(async_session.requests.pop(0),
               {'logger': 'component', 'level': 'critical'},
               {"msg": "Critical"})
