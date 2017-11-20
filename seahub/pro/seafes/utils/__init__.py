#!coding: UTF_8

import os
import sys
import subprocess
from operator import methodcaller

def _expand(v):
    return v[0] if isinstance(v, list) else v

def get_result_set_hits(result):
    hits = result.__getattr__('hits')
    if isinstance(hits, dict):
        hits = hits['hits']

    # In ES 1.4.0 the returned fields values are like {field1: [value1], field2: [value2], ...}
    for entry in hits:
        fields = entry.get('fields', {})
        for k, v in fields.copy().iteritems():
            fields[k] = _expand(v)

    return hits

def run(argv, cwd=None, env=None, suppress_stdout=False, suppress_stderr=False):
    '''Run a program and wait it to finish, and return its exit code. The
    standard output of this program is supressed.

    '''
    with open(os.devnull, 'w') as devnull:
        if suppress_stdout:
            stdout = devnull
        else:
            stdout = sys.stdout

        if suppress_stderr:
            stderr = devnull
        else:
            stderr = sys.stderr

        proc = subprocess.Popen(argv,
                                cwd=cwd,
                                stdout=stdout,
                                stderr=stderr,
                                env=env)

        return proc.wait()

def utf8_encode(s):
    return _utf8_convert(s, True)

def utf8_decode(s):
    return _utf8_convert(s, False)

_decode_caller = methodcaller('decode', 'UTF-8')
_encode_caller = methodcaller('encode', 'UTF-8')

def _utf8_convert(s, to_utf8):
    """Convert a string between bytes and unicode. If the argument is an iterable
    (list/tuple/set), then each element of it would be converted instead. If the
    argument is a dict, each string-typed value would be converted instead.
    """
    if to_utf8:
        target_class = str
        convert_func = _encode_caller
    else:
        target_class = unicode
        convert_func = _decode_caller

    if isinstance(s, basestring):
        return convert_func(s) if not isinstance(s, target_class) else s
    elif isinstance(s, list):
        return [_utf8_convert(x, to_utf8) for x in s]
    elif isinstance(s, tuple):
        return tuple(_utf8_convert(x, to_utf8) for x in s)
    elif isinstance(s, set):
        return {_utf8_convert(x, to_utf8) for x in s}
    elif isinstance(s, dict):
        new = {}
        for k in s:
            v = s[k]
            if isinstance(v, basestring):
                v = _utf8_convert(v, to_utf8)
            new[k] = v
        return new

def do_dict_config(level, stream):
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'seafes': {
                'format': '[%(asctime)s] %(message)s',
            },
        },
        'handlers': {
            'seafes': {
                'level': level,
                'class':'logging.StreamHandler',
                'stream': stream,
                'formatter':'seafes',
            },
        },
        'loggers': {
            'seafes': {
                'handlers': ['seafes'],
                'level': level,
                'propagate': False
            },
        }
    }

    # Make sure that dictConfig is available
    # This was added in Python 2.7/3.2
    try:
        from logging.config import dictConfig
    except ImportError:
        from django.utils.dictconfig import dictConfig

    dictConfig(LOGGING)
