# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 13:23:46 2015

@author: sunshine
"""

import queue

from tools import *
from classes import *
from random import sample
import ujson as json
    
def fetch_artist_names(random_sample=None):
    '''Fetches top artists from wikipedia'''
    base = 'https://en.wikipedia.org/wiki/List_of_hip_hop_musicians'
    query = '//li/a/@title'
    results = xpath_query_url(base, query)

    if random_sample and random_sample < len(results):
        results = sample(results, random_sample)

    return results

def scrape(artist_names=['Gucci mane']):
    q_id = queue.Queue()
    q_links = queue.Queue(maxsize=10)
    q_lyrics = queue.Queue()
    q_write = queue.Queue()
    
    pool_id = thread_pool(q_id, 10, ThreadFetchArtistID, qo=q_links)
    pool_links = thread_pool(q_links, 10, ThreadPageNameScrape, qo=q_lyrics, 
                             payload={'skip_links': already_downloaded()})
    pool_lyrics = thread_pool(q_lyrics, 10, ThreadLyrics, qo=q_write)
    pool_write = thread_pool(q_write, 10, ThreadWrite)
    
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
    for root, dirs, _ in os.walk(ap('lyrics/')):
        for dir in dirs:
            for _, _, files in os.walk(ap('lyrics/{}'.format(dir))):
                for file in files:
                    song_name = file.split('.')[0]
                    link = 'http://genius.com/{}'.format(song_name)
                    links.add(link)
    return links
                    
if __name__ == '__main__':
    artists = fetch_artist_names()
    if len(sys.argv) > 3:
        if '-u' in sys.argv[2]:
            scrape(artist_names=artists)
    elif len(sys.argv) == 2:
        scrape(artist_names=[sys.argv[1]])
    else:
        scrape(artist_names=artists)
