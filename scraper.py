# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 13:23:46 2015

@author: sunshine
"""
from __future__ import print_function

import queue
from re import search
import os
import os.path as osp
import json

from tools import *
from classes import *

    
def fetch_hot_artists(page_limit=10):
    '''Fetches top artists from hotnewhiphop.com'''
    q = queue.Queue(maxsize=10)
    pool = thread_pool(q, 10, ThreadFetchHotArtists)
    artists = dict()

    for page in range(page_limit):
        q.put((page, artists))
        print('added page: {}/{} of hot artists into the queue for download'.format(page, page_limit),
              end='\r')    
    q.join()
    del pool
    
    cleaned = list()
    for page in range(len(artists)):
        cleaned += artists[page]
    cleaned = [artist for artist in cleaned if not search('&amp', artist)]
    return cleaned

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
