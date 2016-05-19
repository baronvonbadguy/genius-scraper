# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 13:23:46 2015

@author: sunshine
"""

import queue

from tools import *
from classes import *

    
def fetch_hot_artists():
    '''Fetches top artists from wikipedia'''
    base = 'https://en.wikipedia.org/wiki/List_of_hip_hop_musicians'
    query = '//li/a/@title'
    results = xpath_query_url(base, query)

    return results

def scrape(artist_names=['Gucci mane'], updating=False):
    q_id = queue.Queue()
    q_links = queue.Queue(maxsize=10)
    q_lyrics = queue.Queue()
    q_write = queue.Queue()
    
    pool_id = thread_pool(q_id, 10, ThreadFetchArtistID, qo=q_links)
    pool_links = thread_pool(q_links, 10, ThreadPageNameScrape, qo=q_lyrics, 
                             payload={'skip_links': already_downloaded()})
    pool_lyrics = thread_pool(q_lyrics, 10, ThreadLyrics, qo=q_write)
    pool_write = thread_pool(q_write, 1, ThreadWrite, 
                             payload={'updating': updating})
    
    for artist in artist_names:
        q_id.put(artist)

    q_id.join()
    del pool_id
    print('finished fetching artist IDs')

    q_links.join()
    del pool_links
    print('finished fetching song links')

    q_lyrics.join()
    del pool_lyrics
    print('finished fetching lyrics')

    q_write.join()
    del pool_write
    print('finished writing lyrics')

def already_downloaded():
    links = set()
    for fp in os.listdir(ap('lyrics/')):
        ab_fp = ap('lyrics/' + fp)
        if osp.isfile(ab_fp):
            with open(ab_fp, 'r') as f:
                artist = json.load(f)
                links = links.union(set(artist.keys()))
    return links
                    
if __name__ == '__main__':
    if len(sys.argv) > 3:
        if '-u' in sys.argv[2]:
            scrape(artist_names=fetch_hot_artists()[:50], updating=True)
    elif len(sys.argv) == 2:
        scrape(artist_names=[sys.argv[1]])
    else:
        scrape(artist_names=fetch_hot_artists()[:50])
