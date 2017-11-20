#coding: UTF-8

import os
import subprocess

from .index_updater import index_update
from .indexes import RepoFilesIndex
from .connection import es_get_conn
from .utils import run

class Elasticsearch(object):
    def __init__(self):
        pro_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.es_executable = os.path.join(pro_dir, 'elasticsearch', 'bin', 'elasticsearch')
        print self.es_executable

        top_dir = os.path.dirname(os.path.dirname(os.path.dirname(pro_dir))) # os.environ['SdataEAFILE_CONF_DIR']
        self.es_logs_dir = os.path.join(top_dir, 'logs')
        self.es_data_dir = os.path.join(top_dir, 'seafile-data', 'search')

        self.running = False
        print self.es_logs_dir
        print self.es_data_dir

    def start(self):
        '''Start Elasticsearch. We use -D command line args to specify the
        location of logs and data

        '''
        if self.running:
            return

        argv = [
            self.es_executable,
            '-E', 'path.logs=%s' % self.es_logs_dir,
            '-E', 'path.data=%s' % self.es_data_dir,
        ]
        run(argv, suppress_stdout=True, suppress_stderr=True, wait=False)
        self.running = True

es = None
if not es:
    es = Elasticsearch()
    es.start()

updater = None
if not updater:
    print 'init the updater'
    updater = index_update()
print 'finish updater'

def es_search(repo_ids, keyword, suffixes, start, size):
    conn = es_get_conn()
    files_index = RepoFilesIndex(conn)
    return files_index.search_files(repo_ids, keyword, suffixes, start, size)
