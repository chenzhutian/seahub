#coding: UTF-8

import os
import ConfigParser
import logging

from seahub.settings import ES_INDEX_OFFICE_PDF, EXTERNAL_ES_SERVER, \
ES_HOST, ES_PORT, ES_LANG, ES_INDEX_WORKERS, ES_OFFICE_FILE_SIZE_LIMIT, ES_DEBUG

logger = logging.getLogger('seafes')

SUPPORTED_LANGS = (
    "arabic",
    "armenian",
    "basque",
    "brazilian",
    "bulgarian",
    "catalan",
    "chinese",
    "cjk",
    "czech",
    "danish",
    "dutch",
    "english",
    "finnish",
    "french",
    "galician",
    "german",
    "greek",
    "hindi",
    "hungarian",
    "indonesian",
    "italian",
    "norwegian",
    "persian",
    "portuguese",
    "romanian",
    "russian",
    "spanish",
    "swedish",
    "turkish",
    "thai"
)



class SeafesConfig(object):
    def __init__(self):
        if 'SEAFILE_CENTRAL_CONF_DIR' in os.environ:
            confdir = os.environ['SEAFILE_CENTRAL_CONF_DIR']
        else:
            confdir = os.environ['SEAFILE_CONF_DIR']
        self.seafile_conf = os.path.join(confdir, 'seafile.conf')
        self.seafile_dir = os.environ['SEAFILE_CONF_DIR']

        self.host = '127.0.0.1'
        self.port = 9200
        self.index_office_pdf = False
        self.text_size_limit = 100 * 1024 # 100 KB
        self.debug = False
        self.lang = ''

        # events_conf = os.environ.get('EVENTS_CONFIG_FILE', None)
        # if not events_conf:
        #     raise Exception('EVENTS_CONFIG_FILE not set in os.environ')

        self.load_seafevents_conf()

    def print_config(self):
        logger.info('index text of office and pdf files: %s',
                    'yes' if self.index_office_pdf else 'no')

    def load_seafevents_conf(self):
        # defaults = {
        #     'index_office_pdf': 'false',
        #     'external_es_server': 'false',
        #     'es_host': '127.0.0.1',
        #     'es_port': '9200',
        #     'debug': 'false',
        #     'lang': '',
        #     'office_file_size_limit': '10', # 10 MB
        #     'index_workers': '2'
        # }

        # cp = ConfigParser.ConfigParser(defaults)
        # cp.read(events_conf)

        # section_name = 'INDEX FILES'

        index_office_pdf = ES_INDEX_OFFICE_PDF # cp.getboolean(section_name, 'index_office_pdf')

        external_es_server = EXTERNAL_ES_SERVER # cp.getboolean(section_name, 'external_es_server')
        host = '127.0.0.1'
        port = 9200
        if external_es_server:
            host = ES_HOST # cp.get(section_name, 'es_host')
            port =  ES_PORT # cp.getint(section_name, 'es_port')
            if port == 9500:
                # Seafile pro server earlier than 6.1.0 uses elasticsearch
                # thrift api. In Seafile Pro 6.1.0 we upgrade ES to 2.x, which
                # no longer supports thirft, thus we have to use elasticsearch
                # http api.
                port = 9200


        lang = ES_LANG # cp.get(section_name, 'lang').lower()

        if lang:
            if lang not in SUPPORTED_LANGS:
                logger.warning('[seafes] invalid language ' + lang)
                lang = ''
            else:
                logger.info('[seafes] use language ' + lang)

        index_workers = ES_INDEX_WORKERS  # cp.getint(section_name, 'index_workers')

        if index_workers <= 0:
            logger.warning("index workers can't less than zero.")
            index_workers = 2

        self.index_office_pdf = index_office_pdf
        self.host = host
        self.port = port
        self.office_file_size_limit = ES_OFFICE_FILE_SIZE_LIMIT * 1024 * 1024

        self.debug = ES_DEBUG # cp.getboolean(section_name, 'debug')
        self.lang = lang
        self.index_workers = index_workers

seafes_config = SeafesConfig()
