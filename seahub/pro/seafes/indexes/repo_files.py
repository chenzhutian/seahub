#coding: UTF-8

import os
import logging
import hashlib

from elasticsearch.exceptions import NotFoundError
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Q, Search

from .base import SeafileIndexBase

from ..utils import get_result_set_hits, utf8_decode
from ..extract import get_file_suffix, ExtractorFactory
from ..config import seafes_config

logger = logging.getLogger('seafes')

class RepoFilesIndex(SeafileIndexBase):
    INDEX_NAME = 'repofiles'
    MAPPING_TYPE = 'file'
    MAPPING = {
        '_source': {
            'enabled': True
        },
        'properties': {
            'repo': {
                'type': 'keyword',
                'index': 'true',
            },
            'path': {
                'type': 'keyword',
                'index': 'true',
            },
            'filename': {
                'type': 'text',
                'index': 'true',
                'fields': {
                    'ngram': {
                        'type': 'text',
                        'index': 'true',
                        'analyzer': 'seafile_file_name_ngram_analyzer',
                    },
                },
            },
            'suffix': {
                'type': 'keyword',
                'index': 'true',
            },
            'content': {
                'type': 'text',
                'index': 'true',
            },
            'is_dir': {
                'type': 'boolean',
                'index': 'true',
            }
        },
    }

    index_settings = {
        'analysis': {
            'analyzer': {
                'seafile_file_name_ngram_analyzer': {
                    'type': 'custom',
                    'tokenizer': 'seafile_file_name_ngram_tokenizer',
                    'filter': [
                        'lowercase',
                    ],
                }
            },
            'tokenizer': {
                'seafile_file_name_ngram_tokenizer': {
                    'type': 'nGram',
                    'min_gram': '3',
                    'max_gram': '4',
                    'token_chars': ['letter', 'digit'],
                }
            }
        }
    }

    def __init__(self, es):
        """
        Init function.

        :type es: elasticsearch.Elasticsearch
        """
        super(RepoFilesIndex, self).__init__(es)
        self.language_index_optimization()
        self.create_index_if_missing(index_settings=self.index_settings)

    def language_index_optimization(self):
        if seafes_config.lang:
            # Use ngram for europe languages
            if seafes_config.lang != 'chinese':
                self.MAPPING['properties']['filename']['analyzer'] = seafes_config.lang
                self.MAPPING['properties']['content']['analyzer'] = seafes_config.lang
            else:
                # For chinese we don't need the ngram analyzer for file name.
                self.MAPPING['properties']['filename'].pop('fields', None)
                self.index_settings = {}

                # Use the ik_smart analyzer to do coarse-grained chinese
                # tokenization for search keywords.
                self.MAPPING['properties']['filename']['analyzer'] = 'ik'
                self.MAPPING['properties']['filename']['search_analyzer'] = 'ik_smart'
                self.MAPPING['properties']['content']['analyzer'] = 'ik'
                self.MAPPING['properties']['content']['search_analyzer'] = 'ik_smart'

    def is_chinese(self):
        return seafes_config.lang == 'chinese'

    def add_files(self, repo_id, version, files):
        '''Index newly added files. For text files, also index their content.'''
        for path, obj_id in files:
            self.add_file_to_index(repo_id, version, path, obj_id)

    def add_dirs(self, repo_id, version, dirs):
        """Index newly added dirs.
        """
        for path, obj_id in dirs:
            self.add_dir_to_index(repo_id, version, path, obj_id)

    def add_file_to_index(self, repo_id, version, path, obj_id):
        """Add/update a file to/in index.
        """
        if not is_valid_utf8(path):
            return

        extractor = ExtractorFactory.get_extractor(os.path.basename(path))
        content = extractor.extract(repo_id, version, obj_id, path) if extractor else None
        filename = os.path.basename(path)

        try:
            eid = self.find_file_eid(repo_id, path)
        except:
            logging.warning('failed to find_file_eid, %s(%s), %s(%s)',
                            repo_id, type(repo_id),
                            path, type(path))
            raise
        if eid:
            # This file already exists in index, we update it
            self.partial_update_file_content(eid, content)
        else:
            # This file does not exist in index
            suffix = get_file_suffix(filename)

            data = utf8_decode({
                'repo': repo_id,
                'path': path,
                'filename': filename,
                'suffix': suffix,
                'content': content,
                'is_dir': False,
                # 'tags': get_repo_file_tags(repo_id, path)
            })
            self.es.index(index=self.INDEX_NAME,
                          doc_type=self.MAPPING_TYPE,
                          body=data,
                          id=_doc_id(repo_id, path))

    def add_dir_to_index(self, repo_id, version, path, obj_id): # pylint: disable=unused-argument
        """Add a dir to index.
        """
        if not is_valid_utf8(path):
            return

        filename = os.path.basename(path)

        path = path + '/' if path != '/' else path
        eid = _doc_id(repo_id, path)

        data = utf8_decode({
            'repo': repo_id,
            'path': path,
            'filename': filename,
            'suffix': None,
            'content': None,
            'is_dir': True,
        })
        self.es.index(
            index=self.INDEX_NAME,
            doc_type=self.MAPPING_TYPE,
            body=data,
            id=eid
        )

    def find_file_eid(self, repo_id, path):
        eid = _doc_id(repo_id, path)
        try:
            self.es.get(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=eid, stored_fields=[])
            return eid
        except NotFoundError:
            return None

    def partial_update_file_content(self, eid, content):
        doc = {
            'content': content,
        }

        self.es.update(index=self.INDEX_NAME, doc_type=self.MAPPING_TYPE, id=eid, body=dict(doc=doc))

    def delete_files(self, repo_id, files):
        actions = []
        for path in files:
            eid = _doc_id(repo_id, path)
            actions.append({
                '_op_type': 'delete',
                '_index': self.INDEX_NAME,
                '_type': self.MAPPING_TYPE,
                '_id': eid
            })
            self.bulk(actions, ignore_not_found=True)
        self.refresh()

    def delete_dirs(self, repo_id, dirs):
        for path in dirs:
            path = path + '/' if path != '/' else path
            self.delete_by_id_prefix(_doc_id(repo_id, path))
        self.refresh()

    def delete_by_id_prefix(self, prefix):
        s = Search(using=self.es, index=self.INDEX_NAME).query('prefix', _id=prefix)
        self.delete_by_query(s.to_dict())

    def update_files(self, repo_id, version, files):
        self.add_files(repo_id, version, files)

    def delete_repo(self, repo_id):
        if len(repo_id) != 36:
            return

        self.delete_by_id_prefix(repo_id)
        self.refresh()

    def search_files(self, repo_ids, keyword, suffixes=None, start=0, size=10):
        result = self.do_search(repo_ids, keyword, suffixes, start, size)
        
        def get_entries(result):
            def _expand(v):
                return v[0] if isinstance(v, list) else v

            hits = result.hits.hits
            ret = []
            for e in hits:
                fields = e.get('fields', {})
                for k, v in fields.copy().iteritems():
                    fields[k] = _expand(v)
                e['fields'] = fields
                ret.append(e)
            return ret

        total = result.hits.total
        ret = []

        for entry in get_entries(result):
            highlight = entry.get('highlight', {})
            if 'filename' in highlight:
                filename_highlight = highlight['filename'][0]
            elif 'filename.ngram' in highlight:
                filename_highlight = highlight['filename.ngram'][0]
            else:
                filename_highlight = ''

            content_highlight = '...'.join(highlight.get('content', []))
            d = entry['_source']
            try:
                is_dir = d['is_dir']
            except KeyError:
                # Compatible with existing entry that has not `is_dir` field in
                # index.
                is_dir = False
            r = {
                'repo_id': d['repo'],
                'fullpath': d['path'],
                'name': d['filename'],
                'score': entry['_score'],
                'name_highlight': filename_highlight,
                'content_highlight': content_highlight,
                'is_dir': is_dir,
            }
            ret.append(r)
        return ret, total

    def _make_keyword_query(self, keyword):
        keyword = utf8_decode(keyword)
        match_query_kwargs = {'minimum_should_match': '-25%'}
        if self.is_chinese():
            match_query_kwargs['analyzer'] = 'ik_smart'

        def _make_match_query(field, keyword, **kw):
            q = {'query': keyword}
            q.update(kw)
            return Q({"match": {field: q}})

        search_in_file_name = _make_match_query('filename', keyword, **match_query_kwargs)
        search_in_file_content = _make_match_query('content', keyword, **match_query_kwargs)

        searches = [search_in_file_name, search_in_file_content]
        if not self.is_chinese():
            # See https://www.elastic.co/guide/en/elasticsearch/guide/2.x/ngrams-compound-words.html
            # for how to specify the ngram minimum_should_match in a match query.
            search_in_file_name_ngram = Q({
                "match": {
                    "filename.ngram": {
                        "query":  keyword,
                        "minimum_should_match": "80%",
                    }
                }
            })
            searches.append(search_in_file_name_ngram)

        return Q('bool', should=searches)

    def _add_repos_and_suffix_filter(self, search, repo_ids, suffixes):
        # filters for repo ids
        if isinstance(repo_ids, list):
            search = search.filter('terms', repo=[utf8_decode(x) for x in repo_ids])
        else:
            search = search.filter('term', repo=utf8_decode(repo_ids))

        # filters for file suffixes
        if suffixes:
            if isinstance(suffixes, list):
                suffixes = [utf8_decode(x.lower()) for x in suffixes]
                search = search.filter('terms', suffix=suffixes)
            else:
                search = search.filter('term', suffix=suffixes.lower())
        return search

    def do_search(self, repo_ids, keyword, suffixes, start, size):
        """Search files with providing ``keyword``.

        Arguments:
        - `self`:
        - `repo_ids`: A list of repos need to be searched.
        - `keyword`: A search keyword provided by user.
        - `suffixes`: A list of file suffixes need to be searched.
        - `start`: How many initial results should be skipped.
        - `size`:  How many results should be returned.
        """
        search = Search(using=self.es, index=self.INDEX_NAME)
        search = self._add_repos_and_suffix_filter(search, repo_ids, suffixes)

        keyword_query = self._make_keyword_query(keyword)
        search = search.query(keyword_query).source(['repo', 'path', 'filename', 'is_dir'])[start:start+size]

        search = search.highlight('filename', 'filename.ngram', 'content').highlight_options(
            pre_tags=['<b>'],
            post_tags=['</b>'],
            encoder='html',
            require_field_match=True
        )
        resp = search.execute()

        return resp

def is_valid_utf8(path):
    if isinstance(path, unicode):
        return True
    try:
        path.decode('utf8')
    except UnicodeDecodeError:
        return False
    else:
        return True

def _doc_id(repo_id, path):
    return utf8_decode(repo_id) + utf8_decode(path)
