from elasticsearch import Elasticsearch

from .config import seafes_config

def es_get_conn():
    es = Elasticsearch(['{}:{}'.format(seafes_config.host, seafes_config.port)])
    return es
