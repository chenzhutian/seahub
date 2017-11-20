# Copyright (c) 2012-2016 Seafile Ltd.

import logging
import os

#from seahub.settings import EVENTS_CONFIG_FILE
from seahub.utils import get_user_repos, is_org_context

from seaserv import seafile_api
from pysearpc import SearpcError

# os.environ['EVENTS_CONFIG_FILE'] = EVENTS_CONFIG_FILE
from seahub.pro.seafes import es_search


# Get an instance of a logger
logger = logging.getLogger(__name__)

def search_file_by_name(request, keyword, suffixes, start, size):
    username = request.user.username
    org_id = request.user.org.org_id if is_org_context(request) else None
    owned_repos, shared_repos, groups_repos, pub_repo_list = get_user_repos(
        username, org_id=org_id)
    # unify the repo.owner property
    for repo in owned_repos:
        repo.owner = username
    for repo in shared_repos:
        repo.owner = repo.user
    for repo in pub_repo_list:
        repo.owner = repo.user

    pubrepo_id_map = {}
    for repo in pub_repo_list:
        # fix pub repo obj attr name mismatch in seafile/lib/repo.vala
        repo.id = repo.repo_id
        repo.name = repo.repo_name
        pubrepo_id_map[repo.id] = repo

    # remove duplicates from repos
    repo_list = []
    for repo in owned_repos + shared_repos + groups_repos + pub_repo_list:
        if repo.id not in repo_list:
            repo_list.append(repo)

    nonpub_repo_ids = [repo.id for repo in repo_list]

    files_found, total = es_search(nonpub_repo_ids, keyword, suffixes, start, size)

    if len(files_found) > 0:
        # construt a (id, repo) hash table for fast lookup
        repo_id_map = {}
        for repo in repo_list:
            repo_id_map[repo.id] = repo

        repo_id_map.update(pubrepo_id_map)

        for f in files_found:
            repo = repo_id_map.get(f['repo_id'].encode('UTF-8'), None)
            if not repo:
                f['exists'] = False
                continue

            try:
                dirent = seafile_api.get_dirent_by_path(f['repo_id'], f['fullpath'])
                if dirent:
                    f['last_modified_by'], f['last_modified'] = dirent.modifier, dirent.mtime
                    f['repo'] = repo
                    f['exists'] = True
                    f['size'] = dirent.size
                else:
                    f['exists'] = False
            except SearpcError as e:  # no file/dir found
                logger.error(e)
                f['exists'] = False

        files_found = filter(lambda f: f['exists'], files_found)

    return files_found, total


def search_repo_file_by_name(request, repo, keyword, suffixes, start, size):
    files_found, total = es_search([repo.id], keyword, suffixes, start, size)

    for f in files_found:
        f['repo'] = repo
        try:
            dirent = seafile_api.get_dirent_by_path(f['repo_id'], f['fullpath'])
            if dirent:
                f['last_modified_by'], f['last_modified'] = dirent.modifier, dirent.mtime
                f['exists'] = True
                f['size'] = dirent.size
            else:
                f['exists'] = False
        except SearpcError as e:  # no file/dir found
            logger.error(e)
            f['exists'] = False

    files_found = filter(lambda f: f['exists'], files_found)

    return files_found, total
