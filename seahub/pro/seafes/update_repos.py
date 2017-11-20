#!/usr/bin/env python
#coding: UTF-8

import os
import sys
import logging
import argparse

from seahub.pro.seafobj import commit_mgr, fs_mgr, block_mgr

from .file_index_updater import FileIndexUpdater
from .indexes import RepoStatusIndex, RepoFilesIndex
from .connection import es_get_conn
from .config import seafes_config

logger = logging.getLogger('seafes')

UPDATE_FILE_LOCK = os.path.join(os.path.dirname(__file__), 'update.lock')
lockfile = None

def init_logging(args):
    level = args.loglevel

    if level == 'debug':
        level = logging.DEBUG
    elif level == 'info':
        level = logging.INFO
    elif level == 'warning':
        level = logging.WARNING
    else:
        if seafes_config.debug:
            level = logging.DEBUG
        else:
            level = logging.INFO

    try:
        # set boto log level
        import boto
        boto.log.setLevel(logging.WARNING)
    except:
        pass

    # do_dict_config(level, args.logfile)

    kw = {
        'format': '[%(asctime)s] %(message)s',
        # 'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s',
        'datefmt': '%m/%d/%Y %H:%M:%S',
        'level': level,
        'stream': args.logfile
    }

    logging.basicConfig(**kw)
    logging.getLogger('oss_util').setLevel(logging.WARNING)
    logging.getLogger('elasticsearch').setLevel(logging.ERROR)
    logging.getLogger('elasticsearch.trace').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    if seafes_config.debug:
        logging.debug('debug flag turned on')

def update_repos():
    updater = FileIndexUpdater(es_get_conn())
    updater.run()

    logger.info('\n\nIndex updated, statistic report:\n')
    logger.info('[commit read] %s', commit_mgr.read_count())
    logger.info('[dir read]    %s', fs_mgr.dir_read_count())
    logger.info('[file read]   %s', fs_mgr.file_read_count())
    logger.info('[block read]  %s', block_mgr.read_count())

def delete_indices():
    es = es_get_conn()
    for idx in (RepoStatusIndex.INDEX_NAME, RepoFilesIndex.INDEX_NAME):
        if es.indices.exists(idx):
            logger.warning('deleting index %s', idx)
            es.indices.delete(idx)

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands', description='')

    parser.add_argument(
        '--logfile',
        default=sys.stdout,
        type=argparse.FileType('a'),
        help='log file')

    parser.add_argument(
        '--loglevel',
        default='info',
        help='log level')

    # update index of filename and text/markdown file content
    parser_update = subparsers.add_parser('update', help='update seafile index')
    parser_update.set_defaults(func=update_repos)

    # clear
    parser_clear = subparsers.add_parser('clear', help='clear all index')
    parser_clear.set_defaults(func=delete_indices)

    if len(sys.argv) == 1:
        print parser.format_help()
        return

    args = parser.parse_args()
    init_logging(args)

    logging.info('storage: using ' + commit_mgr.get_backend_name())
    logging.info('index office pdf: %s', seafes_config.index_office_pdf)

    if not check_concurrent_update():
        return

    args.func()

def do_lock(fn):
    if os.name == 'nt':
        return do_lock_win32(fn)
    else:
        return do_lock_linux(fn)

def do_lock_win32(fn):
    import ctypes
    import locale

    CreateFileW = ctypes.windll.kernel32.CreateFileW
    GENERIC_WRITE = 0x40000000
    OPEN_ALWAYS = 4

    encoding = locale.getdefaultlocale()[1]

    def lock_file(path):
        if isinstance(path, str):
            path = path.decode(encoding)
        lock_file_handle = CreateFileW (path,
                                        GENERIC_WRITE,
                                        0,
                                        None,
                                        OPEN_ALWAYS,
                                        0,
                                        None)

        return lock_file_handle

    global lockfile

    lockfile = lock_file(fn)

    return lockfile != -1

def do_lock_linux(fn):
    global lockfile
    lockfile = open(fn, 'w')
    try:
        import portalocker
        portalocker.lock(lockfile, portalocker.LOCK_NB | portalocker.LOCK_EX)
        return True
    except portalocker.LockException:
        return False

def check_concurrent_update():
    '''Use a lock file to ensure only one task can be running'''
    if not do_lock(UPDATE_FILE_LOCK):
        logger.error('another index task is running, quit now')
        return False

    return True

if __name__ == "__main__":
    main()
