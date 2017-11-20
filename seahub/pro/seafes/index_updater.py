#coding: UTF-8

import os
import logging

from seahub.settings import ES_INTERVAL

from .utils import run, set_interval

def parse_interval(interval, default = 60 * 30):
    if isinstance(interval, (int, long)):
        return interval

    interval = interval.lower()

    unit = 1
    if interval.endswith('s'):
        pass
    elif interval.endswith('m'):
        unit *= 60
    elif interval.endswith('h'):
        unit *= 60 * 60
    elif interval.endswith('d'):
        unit *= 60 * 60 * 24
    else:
        pass

    val = int(interval.rstrip('smhd')) * unit
    if val < 10:
        logging.warning('insane interval %s', val)
        return default
    else:
        return val

interval = parse_interval(ES_INTERVAL)
pro_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
top_dir = os.path.dirname(os.path.dirname(os.path.dirname(pro_dir))) # os.environ['SdataEAFILE_CONF_DIR']
logfile = os.path.join(top_dir, 'logs', 'index.log')
print 'interval', interval

def _update_index_files():
    logging.info('starts to index files')
    try:
        cmd = [
            'python',
            '-m', 'seahub.pro.seafes.update_repos',
            '--logfile', logfile,
            'update',
        ]
        print 'updater', cmd
        run(cmd, suppress_stdout=True, suppress_stderr=True, wait=False)
    except Exception:
        logging.exception('error when index files:')

def index_update():
    return set_interval(_update_index_files, interval)