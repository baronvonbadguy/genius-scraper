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

    def regex_blocks(self, regex, blocks, song_artist, features):
        '''
            takes a list of 2-tuples, finds the blocks that match the regular
            expression, then returns those matching blocks as a dictionary
        '''
        artist = None
        formatted_blocks = list()
        del_indeces = list()
        #arbitrary threshold for the amount of characters in the block text
        #until it's considered a match
        length_threshold = 8

        for i, block in enumerate(blocks):
            regex_match = ''
            try:
                regex_match = re.search(regex, block[0])
            except Exception as e:
                print(e)
            if regex_match and len(block[1]) > length_threshold:
                artist = song_artist
                for feature in features:
                    if re.search(feature.lower(), block[0].lower()):
                        artist = feature
                block_dict = {'header': block[0],
                              'text': block[1],
                              'artist': artist}
                formatted_blocks.append(block_dict)
                del_indeces.append(i)

        for i in del_indeces[::-1]:
            del blocks[i]

        return formatted_blocks

    def run(self):
        while True:
            #grab a lyrics page link and the unprocessed name of the artist
            link, name_raw = self.q.get()
            response = rq.get(link)

            if response.status_code == 200:
                soup = bs(response.text)
                soup_results = soup.find('div', class_='lyrics')
                if len(soup_results) > 0:
                    lyrics = soup_results.text
                    song_name = soup.find('span', class_='text_title').text.strip()
                    name = soup.find('span', class_='text_artist').a.text.strip()
     
                    ft_group = soup.find('span', class_='featured_artists')
                    features, producers = [], []
                    if ft_group:
                        features = [ft.text.strip() for ft in ft_group.find_all('a')]
                    pr_group = soup.find('span', class_='producer_artists')
                    if pr_group:
                        producers = [pr.text.strip() for pr in pr_group.find_all('a')]
     
                   #dictionary to store all of out raw and processed lyrics data
                    block_dict = {'raw': lyrics, 'pro': dict()}
    
                    #regex to parse block header order, block headers look like 
                    #'[ Verse 1: Gucci Mane ]' or '[Hook]'
                    block_order = re.findall(r'(\[.{4,}(?!\?)\])\n', lyrics)
    
                    #regex to parse all blocks, except for block references
                    # (\[.{4,}(?!\?)\]) match verse headers, but no
                    #inline question blocks, e.g [???]
                        # (?!\n\n) lookahead to filter block references out
                    # \n* filters out the newline trailing block headers
                    # ([\w\W\n]*?) matches all following chracters, not greedy
                        # (?=(\n\[|$)) lookahead to stop when we hit the next header
                        #or the end of the lyrics
                    block_regex = r'(\[.{4,}(?!\?)\])(?!\n\n)\n*([\w\W\n]*?)(?=\n+\[|$)'
                    blocks = re.findall(block_regex, lyrics)
    
                    names_regex = '|'.join((name, name.upper(),
                                            name.title(), name.lower(),
                                            remove_last_word(name.title())))
      
                    artist_regex = (lambda regex:
                                    self.regex_blocks(regex, blocks, name, features))
    
                    #grabs all of the blocks we need based on regex searches
                    #through block headers
                    intro = artist_regex('[iI]ntro')
                    hooks = artist_regex('[hH]ook|[cC]horus')
                    bridge = artist_regex('[bB]ridge')
                    verses = artist_regex('[vV]erse|' + names_regex)
    
                    #match all regex, just to format the raw remainders
                    remainders = artist_regex('([\w\W\n]*?)')
    
                    block_dict['pro']['order'] = block_order
                    block_dict['pro']['blocks'] = {'hooks': hooks, 'verses': verses}
                    block_dict['pro']['artist'] = name
                    
                    if intro:
                        block_dict['pro']['blocks']['intro'] = intro
                    if remainders:
                        block_dict['pro']['blocks']['remainders'] = remainders
                    if bridge:
                        block_dict['pro']['blocks']['bridge'] = bridge
                    if features:
                        block_dict['pro']['features'] = features
                    if producers:
                        block_dict['pro']['producers'] = producers
                        
                    self.db[song_name] = block_dict
            else:
                print(song_name + ' download failed')
            #print(song_name + ' task completed')
            self.q.task_done()


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

    while current_page < 10:
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
        q.put((link, name))

    q.join()

    with open(ap('lyrics/' + name + '.json'), 'wb') as fp:
        json.dump(lyrics_db, fp, indent=4)
    
    return lyrics_db


if __name__ == '__main__':
    name = 'gucci mane'
    artist_id, name = fetch_artist_id(name)
    song_links = fetch_artist_song_links(artist_id)
    fetch_lyrics(song_links, name)
