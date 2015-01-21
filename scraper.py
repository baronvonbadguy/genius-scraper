# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 13:23:46 2015

@author: sunshine
"""
from bs4 import BeautifulSoup as bs
import requests as rq
from lxml import html
from threading import Thread
from Queue import Queue
from tools import *
import json
from collections import defaultdict
import re


class ThreadLyrics(Thread):
    def __init__(self, queue, payload):
        self.q = queue
        self.db = payload['database']
        Thread.__init__(self)

    def run(self):
        while True:
            #grab some data from the queue
            link, name = self.q.get()
            song_name = link.split('/')[-1].split('-lyrics')[0]
            response = rq.get(link)

            if response.status_code == 200:
                print('success: ' + response.text[:50])
                print('adding ' + song_name + ' to db')

                soup = bs(response.text)
                soup_results = soup.find_all('div', class_='lyrics')
                lyrics = [element.text for element in soup_results][0]

                block_dict = {'raw': lyrics, 'pro': dict()}

                #regex to parse block header order, block headers look like 
                #'[ Verse 1: Gucci Mane ]' or '[Hook]'
                block_order = re.findall(r'(\[.{4,}(?!\?)\])\n', lyrics)

                #regex to parse all blocks, except for block references
                # (\[.{4,}(?!\?)\]) match verse headers, but not 
                #inline question blocks, e.g [???]
                    # (?!\n\n) lookahead to filter block references out
                # \n filters out the newline 'artist': name'artist': nametrailing block headers
                # ([\w\W\n]*?) matches all following chracters, not greedy
                    # (?=(\n\[|$)) lookahead to stop when we hit the next header
                    #or the end of the lyrics
                block_regex = r'(\[.{4,}(?!\?)\])(?!\n\n)\n([\w\W\n]*?)(?=(\n\[|$))'
                blocks = re.findall(block_regex, lyrics)
                
                #uses a regex search to match the blocks we want to return
                #then returns them as a dictionary instead of nested list
                regex_blocks = lambda regex: {block[0]: block[1] for block in blocks
                                              if re.search(regex, block[0])
                                              and len(block[1]) > 0}

                name = name.replace('-', ' ')
                names_regex = '|'.join((name.upper(), name,
                                        name.title(), name.lower()))

                verses = regex_blocks('[vV]erse|' + names_regex)
                hooks = regex_blocks('[hH]ook|[cC]horus')
                intro = regex_blocks('[iI]ntro')

                block_dict['pro']['order'] = block_order
                block_dict['pro']['blocks'] = {'hooks': hooks, 'verses': verses}

                if intro:
                    block_dict['pro']['blocks']['intro'] = intro

                self.db[song_name] = block_dict
            else:
                print(song_name + ' download failed')
            print(song_name + ' task completed')
            self.q.task_done()
1

def xpath_query_url(url, xpath_query):
    headers = {'User-Agent': 'Mozilla/5.0 Gecko/20100101 Firefox/35.0'}
    response = rq.get(url, headers=headers)

    #creates an html tree from the data
    tree = html.fromstring(response.text)

    #XPATH query to grab all of the artist urls, then we grab the first
    return tree.xpath(xpath_query)


def fetch_artist_id(artist):
    #lets grab some page data so we can get the official artist name
    url = 'http://genius.com/search/artists?q='
    artist_term = artist.replace(' ', '-')
    artist_link_xpath = '//li/a[@class="artist_link"]/@href'

    #gonna grab all of the links and take the first result
    artist_link = xpath_query_url(url + artist_term, artist_link_xpath)[0]

    #now that we have the artist link we're going to try to get the artist ID
    artist_id_xpath = '//meta[@property="twitter:app:url:iphone"]/@content'
    artist_id = xpath_query_url(artist_link, artist_id_xpath)[0]

    #grabs just the number from the returned link
    artist_id = artist_id.split('artists/')[1]
    return (artist_id, artist_link.split('/')[-1])


def fetch_artist_song_links(artist_id):
    current_page = 1
    base = 'http://genius.com/artists/songs'
    songs = list()

    while True:
        url = ('{0}?for_artist_page={1}&page={2}&pagination=true'
               .format(base, artist_id, current_page))
        song_link_xpath = '//a[@class="song_name work_in_progress   song_link"]/@href'
        song_links = xpath_query_url(url, song_link_xpath)

        if len(song_links):
            for link in song_links:
                print(link.split('/')[-1])
                songs.append(link)
            current_page += 1
        else:
            break

    return songs


def fetch_lyrics(song_links, name):
    '''
        initializes dictionary, populates the keys beforehand to make the 
        dictionary thread safe, as adding or deleting keys is not threadsafe
        in the default CPython implimentation
    '''
    lyrics_db = defaultdict(dict)

    for link in song_links:
        lyrics_db[link.split('/')[-1].split('-lyrics')[0]]

    q = Queue()
    data = {'database': lyrics_db, 'artist': name}
    thread_pool(q, 10, ThreadLyrics, payload=data)

    for link in song_links:
        print(link)
        q.put((link, name))

    q.join()

    with open(ap('lyrics/' + name + '.json'), 'wb') as fp:
        json.dump(lyrics_db, fp, indent=4)
    
    return lyrics_db


if __name__ == '__main__':
    name = 'woka flocka flame'
    artist_id, name = fetch_artist_id(name)
    song_links = fetch_artist_song_links(artist_id)
    fetch_lyrics(song_links, name)
