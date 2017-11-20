#coding: UTF-8
import atexit
import os
import subprocess

from .indexes import RepoFilesIndex
from .connection import es_get_conn

class Utils(object):
    '''Groups all helper functions here'''
    @staticmethod
    def highlight(content):
        '''Add ANSI color to content to get it highlighted on terminal'''
        return '\x1b[33m%s\x1b[m' % content

    @staticmethod
    def info(msg, newline=True):
        sys.stdout.write(msg)
        if newline:
            sys.stdout.write('\n')

    @staticmethod
    def error(msg):
        '''Print error and exit'''
        print
        print 'Error: ' + msg
        sys.exit(1)

    @staticmethod
    def run_argv(argv, cwd=None, env=None, suppress_stdout=False, suppress_stderr=False):
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
            atexit.register(proc.terminate)
            return proc

    @staticmethod
    def pkill(process):
        '''Kill the program with the given name'''
        argv = [
            'pkill', '-f', process
        ]

        Utils.run_argv(argv)

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
        Utils.run_argv(argv, suppress_stdout=True, suppress_stderr=True)
        self.running = True


    def stop(self):
        Utils.pkill('org.elasticsearch.bootstrap.ElasticSearch')

es = Elasticsearch()
es.start()

def es_search(repo_ids, keyword, suffixes, start, size):
    conn = es_get_conn()
    files_index = RepoFilesIndex(conn)
    return files_index.search_files(repo_ids, keyword, suffixes, start, size)
