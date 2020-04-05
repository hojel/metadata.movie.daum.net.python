# -*- coding: utf-8 -*-
# Daum Movie Python Scraper
import json
import requests
from six.moves import urllib
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON_SETTINGS = xbmcaddon.Addon()
ID = ADDON_SETTINGS.getAddonInfo('id')

DAUM_MOVIE_SRCH   = "https://suggest-bar.daum.net/suggest?id=movie&cate=%s&multiple=1&mod=json&code=utf_in_out&q=%s"
DAUM_MOVIE_DETAIL = "http://movie.daum.net/data/movie/movie_info/detail.json?movieId=%s"
DAUM_MOVIE_CAST   = "http://movie.daum.net/data/movie/movie_info/cast_crew.json?pageNo=1&pageSize=100&movieId=%s"
DAUM_MOVIE_PHOTO  = "http://movie.daum.net/data/movie/photo/movie/list.json?pageNo=1&pageSize=100&id=%s"

def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(msg='[{addon}]: {msg}'.format(addon=ID, msg=msg), level=level)

def get_daum_movie_thumb(url):
    return "https://search1.daumcdn.net/thumb/C146x211.q70/?fname="+urllib.parse.quote(url)

def search_for_movie(title, year, handle, settings):
    log("Find movie with title '{title}' from year '{year}'".format(title=title, year=year), xbmc.LOGINFO)
    r = requests.get(DAUM_MOVIE_SRCH % ('movie', title))
    jobj = r.json()
    for istr in jobj['items']['movie']:
        data = istr.split('|')
        movie_year = data[3]
        movie_title = data[0].strip()
        movie_score = int(float(data[4])*100)
        if movie_year != year:
            movie_score = movie_score//2

        listitem = xbmcgui.ListItem(movie_title, offscreen=True)
        if movie_year:
            listitem.setInfo('video', {'year': movie_year})
        if data[2]:
            listitem.setArt({'thumb': data[2]})
        uniqueids = {'daum': data[1]}
        xbmcplugin.addDirectoryItem(handle=handle, url=build_lookup_string(uniqueids),
            listitem=listitem, isFolder=True)

def get_daum_movie_cast(movie_id):
    r = requests.get(DAUM_MOVIE_CAST % movie_id)
    jobj = r.json()
    cast_info = []
    order = 1
    for data in jobj['data']:
        cast = data['castcrew']
        if cast['castcrewCastName'] in [u'주연', u'조연']:
            item = {'role':cast['castcrewTitleKo']}
        elif cast['castcrewCastName'] in [u'감독', u'연출']:
            item = {'role':cast['castcrewCastName']}
        else:
            continue
        item['name'] = data['nameKo'] if data['nameKo'] else data['nameEn']
        if data['photo']['fullname']:
            item['thumbnail'] = data['photo']['fullname']
        item['order'] = order
        order += 1
        cast_info.append( item )
    return cast_info

def add_daum_movie_photo(listitem, movie_id, settings):
    max_poster = settings.getSettingInt('max_poster')
    max_fanart = settings.getSettingInt('max_fanart')
    r = requests.get(DAUM_MOVIE_PHOTO % movie_id)
    jobj = r.json()
    idx_poster = 0
    idx_fanart = 0
    fanart_l = []
    for data in jobj['data']:
        if data['photoCategory'] == '1' and idx_poster < max_poster:
            listitem.addAvailableArtwork(data['fullname'], "poster", data['thumbnail'])
            idx_poster += 1
        if data['photoCategory'] in ['2', '50'] and len(fanart_l) < max_fanart:
            fanart_l.append( {'image':data['fullname'], 'preview':data['thumbnail']} )
    if fanart_l:
        listitem.setAvailableFanart( fanart_l )

def get_details(input_uniqueids, handle, settings):
    movie_id = input_uniqueids['daum']
    r = requests.get(DAUM_MOVIE_DETAIL % movie_id)
    data = r.json()['data']

    title = data['titleKo']
    listitem = xbmcgui.ListItem(title, offscreen=True)
    movie_info = {
        'genre': [ item['genreName'] for item in data['genres'] ],
        'country': [ item['countryKo'] for item in data['countries'] ],
        'title': data['titleKo'],
        'originaltitle': data['titleEn'],
        'year':int(data['prodYear']),
        #'rating':float(data['moviePoint']['inspectPointAvg']),
        'mpaa':data['admissionDesc'],
        'plot':data['plot'].replace("<br>","\n").replace("<b>","").replace("</b>","").strip(),
        'premiered':data['releaseDate'],
        'duration':int(data['showtime'])*60,
        }
    listitem.setInfo('video', movie_info)
    listitem.setCast(get_daum_movie_cast(movie_id))
    listitem.setUniqueIDs(input_uniqueids, 'daum')

    poster_url = data['photo']['fullname']
    listitem.addAvailableArtwork(poster_url, "poster", get_daum_movie_thumb(poster_url))
    add_daum_movie_photo(listitem, movie_id, settings)

    listitem.setRating('daum', data['moviePoint']['inspectPointAvg'], data['moviePoint']['inspectPointCnt'], defaultt=True)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=listitem)
    return True

def find_uniqueids_in_nfo(nfo, handle):
    uniqueids = find_uniqueids_in_text(nfo)
    if uniqueids:
        listitem = xbmcgui.ListItem(offscreen=True)
        xbmcplugin.addDirectoryItem(
            handle=handle, url=build_lookup_string(uniqueids), listitem=listitem, isFolder=True)

def build_lookup_string(uniqueids):
    return json.dumps(uniqueids)

def parse_lookup_string(uniqueids):
    return json.loads(uniqueids)

def get_params(argv):
    result = {'handle': int(argv[0])}
    if len(argv) < 2 or not argv[1]:
        return result

    result.update(urllib.parse.parse_qsl(argv[1].lstrip('?')))
    return result

def run():
    params = get_params(sys.argv[1:])
    enddir = True
    if 'action' in params:
        settings = ADDON_SETTINGS
        action = params["action"]
        if action == 'find' and 'title' in params:
            search_for_movie(params["title"], params.get("year"), params['handle'], settings)
        elif action == 'getdetails' and 'url' in params:
            enddir = not get_details(parse_lookup_string(params["url"]), params['handle'], settings)
        elif action == 'NfoUrl' and 'nfo' in params:
            find_uniqueids_in_nfo(params["nfo"], params['handle'])
        else:
            log("unhandled action: " + action, xbmc.LOGWARNING)
    else:
        log("No action in 'params' to act on", xbmc.LOGWARNING)
    if enddir:
        xbmcplugin.endOfDirectory(params['handle'])

if __name__ == '__main__':
    run()
