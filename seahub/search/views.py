# Copyright (c) 2012-2016 Seafile Ltd.
import os
import logging

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response
from django.template import RequestContext

from seaserv import seafile_api, ccnet_api

from seahub.auth.decorators import login_required
from seahub.contacts.models import Contact
from seahub.profile.models import Profile
from seahub.utils import PREVIEW_FILEEXT, is_org_context
from seahub.settings import ENABLE_THUMBNAIL, THUMBNAIL_SIZE_FOR_GRID
from seahub.search.utils import search_file_by_name, search_repo_file_by_name

logger = logging.getLogger(__name__)

@login_required
def search(request):
    template = 'search_results.html'
    error = False

    keyword = request.GET.get('q', None)
    if not keyword:
        return render_to_response(template, {
            'error': True,
            }, context_instance=RequestContext(request))

    # advanced search
    search_repo = request.GET.get('search_repo', None) # val: 'all' or 'search_repo_id'
    search_ftypes = request.GET.get('search_ftypes', None) # val: 'all' or 'custom'
    custom_ftypes =  request.GET.getlist('ftype') # types like 'Image', 'Video'... same in utils/file_types.py
    input_fileexts = request.GET.get('input_fexts', '') # file extension input by the user

    suffixes = None
    if search_ftypes == 'custom':
        suffixes = []
        if len(custom_ftypes) > 0:
            for ftp in custom_ftypes:
                if PREVIEW_FILEEXT.has_key(ftp):
                    for ext in PREVIEW_FILEEXT[ftp]:
                        suffixes.append(ext)

        if input_fileexts:
            input_fexts = input_fileexts.split(',')
            for i_ext in input_fexts:
                i_ext = i_ext.strip()
                if i_ext:
                    suffixes.append(i_ext)

    current_page = int(request.GET.get('page', '1'))
    per_page = int(request.GET.get('per_page', '25'))

    start = (current_page - 1) * per_page
    size = per_page

    repo = None
    username = request.user.username
    if search_repo and search_repo != 'all':
        repo_id = search_repo

        try:
            repo = seafile_api.get_repo(search_repo)
        except Exception as e:
            logger.error(e)
            error_msg = 'Internal Server Error'
            return render_to_response(template, {
                'error': True,
                'error_msg': error_msg,
                }, context_instance=RequestContext(request))

        if not repo:
            error_msg = 'Library %s not found.' % search_repo
            return render_to_response(template, {
                'error': True,
                'error_msg': error_msg,
                }, context_instance=RequestContext(request))

        perm = seafile_api.check_permission_by_path(repo_id, '/', username)
        if not perm:
            raise Http404

        repo = seafile_api.get_repo(repo_id)
        if repo:
            results, total = search_repo_file_by_name(request, repo, keyword, suffixes, start, size)
        else:
            results, total = [], 0
    else:
        results, total = search_file_by_name(request, keyword, suffixes, start, size)

    if total > current_page * per_page:
        has_more = True
    else:
        has_more = False

    for r in results:
        parent_dir = os.path.dirname(r['fullpath'].rstrip('/'))
        r['parent_dir'] = '' if parent_dir == '/' else parent_dir.strip('/')

    return render_to_response(template, {
            'repo': repo,
            'keyword': keyword,
            'results': results,
            'total': total,
            'has_more': has_more,
            'current_page': current_page,
            'prev_page': current_page - 1,
            'next_page': current_page + 1,
            'per_page': per_page,
            'search_repo': search_repo,
            'search_ftypes': search_ftypes,
            'custom_ftypes': custom_ftypes,
            'input_fileexts': input_fileexts,
            'error': error,
            'enable_thumbnail': ENABLE_THUMBNAIL,
            'thumbnail_size': THUMBNAIL_SIZE_FOR_GRID,
            }, context_instance=RequestContext(request))


def search_keyword(request, keyword):

    # advanced search
    search_repo = request.GET.get('search_repo', None) # val: 'all' or 'search_repo_id'
    search_ftypes = request.GET.get('search_ftypes', None) # val: 'all' or 'custom'
    custom_ftypes =  request.GET.getlist('ftype') # types like 'Image', 'Video'... same in utils/file_types.py
    input_fileexts = request.GET.get('input_fexts', '') # file extension input by the user

    suffixes = None
    if search_ftypes == 'custom':
        suffixes = []
        if len(custom_ftypes) > 0:
            for ftp in custom_ftypes:
                if PREVIEW_FILEEXT.has_key(ftp):
                    for ext in PREVIEW_FILEEXT[ftp]:
                        suffixes.append(ext)

        if input_fileexts:
            input_fexts = input_fileexts.split(',')
            for i_ext in input_fexts:
                i_ext = i_ext.strip()
                if i_ext:
                    suffixes.append(i_ext)

    current_page = int(request.GET.get('page', '1'))
    per_page= int(request.GET.get('per_page', '25'))

    start = (current_page - 1) * per_page
    size = per_page

    repo = None
    if search_repo and search_repo != 'all':
        repo_id = search_repo
        repo = seafile_api.get_repo(repo_id)
        if repo:
            results, total = search_repo_file_by_name(request, repo, keyword, suffixes, start, size)
        else:
            results, total = [], 0
    else:
        results, total = search_file_by_name(request, keyword, suffixes, start, size)

    if total > current_page * per_page:
        has_more = True
    else:
        has_more = False

    return results, total, has_more

def get_pub_user_profiles(request, users):
    """Get users' all profiles.

    Arguments:
    - `request`:
    - `users`:
    """
    if is_org_context(request):
        return Profile.objects.filter(user__in=[u.email for u in users])
    elif request.cloud_mode:
        return []
    else:                       # return all profiles
        return Profile.objects.all().values('user', 'nickname')

@login_required
def pubuser_search(request):
    can_search = False
    if is_org_context(request):
        can_search = True
    elif request.cloud_mode:
        # Users are not allowed to search public user when in cloud mode.
        can_search = False
    else:
        can_search = True

    if can_search is False:
        raise Http404

    email_or_nickname = request.GET.get('search', '')
    if not email_or_nickname:
        return HttpResponseRedirect(reverse('pubuser'))

    # Get user's contacts, used in show "add to contacts" button.
    username = request.user.username
    contacts = Contact.objects.get_contacts_by_user(username)
    contact_emails = [request.user.username]
    for c in contacts:
        contact_emails.append(c.contact_email)

    search_result = []
    # search by username
    if is_org_context(request):
        url_prefix = request.user.org.url_prefix
        org_users = ccnet_api.get_org_users_by_url_prefix(url_prefix, -1, -1)
        users = []
        for u in org_users:
            if email_or_nickname in u.email:
                users.append(u)
    else:
        users = ccnet_api.search_emailusers(email_or_nickname, -1, -1)
    for u in users:
        can_be_contact = True if u.email not in contact_emails else False
        search_result.append({'email': u.email,
                              'can_be_contact': can_be_contact})

    # search by nickname
    if is_org_context(request):
        url_prefix = request.user.org.url_prefix
        org_users = ccnet_api.get_org_users_by_url_prefix(url_prefix, -1, -1)
        profile_all = Profile.objects.filter(user__in=[u.email for u in org_users]).values('user', 'nickname')
    else:
        profile_all = Profile.objects.all().values('user', 'nickname')
    for p in profile_all:
        if email_or_nickname in p['nickname']:
            can_be_contact = True if p['user'] not in contact_emails else False
            search_result.append({'email': p['user'],
                                  'can_be_contact': can_be_contact})

    uniq_usernames = []
    for res in search_result:
        if res['email'] not in uniq_usernames:
            uniq_usernames.append(res['email'])
        else:
            search_result.remove(res)

    return render_to_response('pubuser.html', {
            'search': email_or_nickname,
            'users': search_result,
            }, context_instance=RequestContext(request))
