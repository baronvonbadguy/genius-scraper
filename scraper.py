# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 13:23:46 2015

@author: sunshine
"""
from __future__ import print_function

import json
import Queue

from tools import *
from classes import *


def fetch_verified():
    '''Fetches verified artists from Genius, not exclusive to Rap.Genius'''
    q = Queue.Queue(maxsize=10)
    pool = thread_pool(q, 10, ThreadFetchVerifiedArtists)
    artists = list()
    page_limit = 222

    for page in range(page_limit):
        q.put((page, artists))
        print('added page: {}/{} into the queue'.format(page, page_limit),
              end='\r')    
    q.join()
    del pool
    
    return artists

def match_verified_rappers(write=False, verified=[]):
    
    if verified:
        verified_artists = verified
    else:
        with open('verified.json', 'r') as f:
            verified_artists = json.load(f)

    with open('wiki-list.json', 'r') as f:
        wiki_artists = json.load(f)

    v_set = {enc_str(v.lower()) for v in verified_artists}
    w_set = {enc_str(w.lower()) for w in wiki_artists}

    artists = set.intersection(v_set, w_set)

    if write:
        with open('rapper-list.json', 'r+') as f:
            json.dump(list(artists), f)

    return artists

def scrape(artist_names=['Gucci mane']):
    q_id = Queue.Queue()
    q_links = Queue.Queue(maxsize=10)
    q_lyrics = Queue.Queue()
    q_write = Queue.Queue()
    
    pool_id = thread_pool(q_id, 10, ThreadFetchArtistID, qo=q_links)
    pool_links = thread_pool(q_links, 10, ThreadPageNameScrape, qo=q_lyrics)
    pool_lyrics = thread_pool(q_lyrics, 10, ThreadLyrics, qo=q_write)
    pool_write = thread_pool(q_write, 1, ThreadWrite)
    
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

def scrape_rapper_list():
    path = ap('rapper-list.json')
    print(path)
    if osp.isfile(path):
        artists = json.load(open(path, 'r+'))
        is_file = lambda name: osp.isfile(ap('lyrics/' + str(name) + '.json'))
        artists = [x for x in artists if not is_file(enc_str(x))]
        scrape(artist_names=artists)
    
    
if __name__ == '__main__':
    if len(sys.argv) > 1:
        scrape(artist_names=[sys.argv[1]])
    else:
        scrape_rapper_list()
