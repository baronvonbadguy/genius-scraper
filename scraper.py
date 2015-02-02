# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 13:23:46 2015

@author: sunshine
"""
from __future__ import print_function

import requests as rq
import threading
import json
import re
import time

from os import mkdir
from hashlib import md5
from collections import defaultdict
from lxml import html
from threading import Thread
import Queue
from bs4 import BeautifulSoup as bs
from tqdm import tqdm

from tools import *

class ThreadLyrics(Thread):
    def __init__(self, queue_in, queue_out ):
        Thread.__init__(self)
        self.qi = queue_in
        self.qo = queue_out

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
            #main regex match for specified match
            try:
                regex_match = re.search(regex, block[0])
            except Exception as e:
                print(e)
            #if primary match was successful and block text is a certain length
            if regex_match and len(block[1]) > length_threshold:
                #defaults the block artist as a song artist
                artist = song_artist
                #checks if any of the featured artists are in the header
                for feature in features:
                    if re.search(an(feature).lower(), an(block[0]).lower()):
                        artist = feature

                #using a hash to compare text blocks
                text_hash = md5(enc_str(block[1])).hexdigest()

                block_dict = {'header': block[0],
                              'text': block[1],
                              'artist': artist,
                              'text hash': text_hash}

                #only adds block if there isn't already one with the same text
                if text_hash not in [block['text hash'] for block in formatted_blocks]:
                    formatted_blocks.append(block_dict)

                #marks block for deletion so futher searches don't get a false
                #positive with similar searches
                del_indeces.append(i)

        for i in del_indeces[::-1]:
            del blocks[i]

        return formatted_blocks

    def run(self):
        while True:
            #grab a lyrics page link and the unprocessed name of the artist
            link, name_raw, artist_id = self.qi.get()
            response = rq.get(link)

            if response.status_code == 200:
                #im using beautiful soup for this part because its much more
                #convenient to grab all of the text below the chain of a
                #specific object than lxml even if it's slower.
                soup = bs(response.text)
                soup_results = soup.find('div', class_='lyrics')

                if soup_results:
                    #raw lyrics text
                    lyrics = soup_results.text
                    #grab the song name and artist name
                    song_name = soup.find('span', class_='text_title').text.strip()
                    name = soup.find('span', class_='text_artist').a.text.strip()

                    #search for group objects, then return all elements if found
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
                    block_regex = r'''
                    (\[.{4,}(?!\?)\]) #match verse headers, but no
                                        #inline question blocks, e.g [???]
                    (?!\n\n)          #lookahead to filter block references out
                    \n*               #filters out the newline trailing block headers
                    ([\w\W\n]*?)      #matches all following chracters, not greedy
                        (?=\n+\[|$)   #lookahead to stop when we hit the next header
                                        #or the end of the lyrics
                    '''
                    blocks = re.findall(block_regex, lyrics, re.VERBOSE)

                    #if no blocks were distinguished, try this more liberal
                    #parenthesis based regex for header matching
                    if not blocks:
                        block_regex = r'''
                        \n{,2}        #leaves out preceeding newlines
                        ([\w\W]*?\(.{4,}(?!\?)\))   #matches headers with parenthesis
                        :?\n*         #leaves out any colons or newlines inbetween
                        ([\w\W\n]*?)  #grabs all the text until the lookahead
                            (?=\n\n|$|\()
                        '''
                        blocks = re.findall(block_regex, lyrics, re.VERBOSE)
                        block_order = re.findall(r'(\(.{4,}(?!\?)\))\n', lyrics)

                    #tries to find the name of the song artist in each header 
                    names_regex = '|'.join((name, name.upper(),
                                            name.title(), name.lower(),
                                            remove_last_word(name.title())))

                    #lambda to preconfigure regex calls
                    artist_regex = (lambda regex:
                                    self.regex_blocks(regex, blocks, name, features))
    
                    #grabs all of the blocks we need based on regex searches
                    #of each of the blocks' headers
                    intro = artist_regex('[iI]ntro')
                    hooks = artist_regex('[hH]ook|[cC]horus')
                    bridge = artist_regex('[bB]ridge')
                    verses = artist_regex('[vV]erse|' + names_regex)
    
                    #match all regex, just to format the raw remainders
                    remainders = artist_regex('([\w\W\n]*?)')

                    #primary entries we need to add even if empty
                    block_dict['pro']['order'] = block_order
                    block_dict['pro']['blocks'] = {'hooks': hooks, 'verses': verses}
                    block_dict['pro']['artist'] = name
                    
                    #these are non essential entries to add if they exist
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
                    print('processed lyrics: ' + song_name)
                    self.qo.put((block_dict, song_name, name))
            else:
                print(song_name + ' download failed')
            #print(song_name + ' task completed')
            self.qi.task_done()


class ThreadPageNameScrape(Thread):
    def __init__(self, queue_in, queue_out):
        Thread.__init__(self)
        self.qi = queue_in
        self.qo = queue_out

    def run(self):
        while True:
            payload = self.qi.get()
            try:
                scraping = payload['scraping']
                artist_id = payload['artist_id']
                page = payload['page']
                name = payload['name']
            except KeyError as e:
                print(e)

            base = 'http://genius.com/artists/songs'
            url = ('{0}?for_artist_page={1}&page={2}&pagination=true'
                   .format(base, artist_id, page))
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                       'X-Requested-With': 'XMLHttpRequest'}

            song_link_xpath = '//a[@class="song_name work_in_progress   song_link"]/@href'
            song_links = xpath_query_url(url, song_link_xpath, payload=headers)

            if song_links:
                for song in song_links:
                    self.qo.put((song, name, artist_id))            
            else:
                scraping[0] = False
            self.qi.task_done()


def xpath_query_url(url, xpath_query, payload=dict()):
    headers = {'User-Agent': 'Mozilla/5.0 Gecko/20100101 Firefox/35.0'}
    if payload:
        headers.update(payload)
    response = rq.get(url, headers=headers)

    #creates an html tree from the data
    tree = html.fromstring(response.text)

    #XPATH query to grab all of the artist urls, then we grab the first
    return tree.xpath(xpath_query)

class ThreadFetchArtistID(Thread):
    def __init__(self, queue_in, queue_out):
        Thread.__init__(self)
        self.qi = queue_in
        self.qo = queue_out
    def run(self):
        while True:
            artist = self.qi.get()
            #lets grab some page data so we can get the official artist name
            url = 'http://genius.com/search/artists?q='
            artist_term = artist.replace(' ', '-')
            artist_link_xpath = '//li/a[@class="artist_link"]/@href'
        
            #gonna grab all of the links and take the first result
            artist_links = xpath_query_url(url + artist_term, artist_link_xpath)
            if artist_links:
                #now that we have the artist link we're going to try to get the artist ID
                artist_id_xpath = '//meta[@property="twitter:app:url:iphone"]/@content'
                artist_id_list = xpath_query_url(artist_links[0], artist_id_xpath)
                artist_id_raw = ''
                if artist_id_list:
                    artist_id_raw = artist_id_list[0]
                    #grabs just the number from the returned link
                    artist_id = artist_id_raw.split('artists/')[1]
                    artist_name_corrected = artist_links[0].split('/')[-1]
                    
                    scraping = [True,]
                    page = 1
                
                    print('begin scraping links for ' +  artist_name_corrected + ' lyric pages')
                    begin = time.time()
                    while scraping[0]:
                        if self.qo.not_full:
                            self.qo.put({'artist_id': artist_id, 'scraping': scraping, 
                                    'page': page, 'name': artist_name_corrected})
                            page += 1
                            print('added page: ' + str(page))
                    print('finished scraping ' + artist_name_corrected + ' in: ' + str(time.time() - begin)[:5] + ' seconds')
            self.qi.task_done()

class ThreadWrite(Thread):
    def __init__(self, queue_in):
        Thread.__init__(self)
        self.qi = queue_in

    def run(self):
        while True:
            data, song_name, name = self.qi.get()
 
            if not osp.isdir(ap('lyrics')):
                mkdir(ap('lyrics'))

            path = ap('lyrics/' + name + '.json')
            if not osp.isfile(path):          
                with open(path, 'w+') as fp:
                    lyrics_db = dict()
                    lyrics_db[song_name] = data
                    json.dump(lyrics_db, fp, indent=4)
                    print('first write')
            else:
                with open(path, 'r+') as fp:
                    lyrics_db = dict()
                    lyrics_db[song_name] = data
                    jsondata = json.dumps(lyrics_db, indent=4)[2:-1]
                    fp.seek(-2, 2)
                    fp.write(',\n')
                    fp.write(jsondata)
                    fp.write('}')

            self.qi.task_done()


def fetch_artist_song_links(artist_id, name, qi):
    '''
        Grabs the song titles from the paginating calls to the designated
        artist page.  The extra headers are so that the server only gives us 
        the resultant song group and no extranious html.
        
        When you scroll down to the bottom of the songs page in a web browser, 
        it will send a AJAX request to the server to grab a tiny packet of 
        html to insert into the existing results. This emulates that so we 
        can get a much faster response from the server, and reduce data 
        transfer overhead by about 75% per request.
        
        Threading this process with a few added constraints makes this even
        faster, without having to process more than one empty response between
        all the threads.
        
        The reason I do it this way is because I don't know what page number
        will be the last, and I need all the threads know as soon as I get a
        blank result, so that no new tasks are added to the queue.
    '''
    


def fetch_lyrics(song_link, name, qi):
    '''
        None of the threads access the same entries at any point in time so
        there aren't any concurrency issues to deal with
    '''
    lyrics_db = defaultdict(defaultdict(dict))

    qi.put((link, name, artist_id))

    if not osp.isdir(ap('lyrics')):
        mkdir(ap('lyrics'))
    with open(ap('lyrics/' + name + '.json'), 'r+') as fp:
        json.dump(lyrics_db, fp, indent=4)

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
    if osp.isfile(path):
        artists = json.load(open(path, 'r+'))
        scrape(artist_names=artists)
    
    
if __name__ == '__main__':
    if len(sys.argv) > 1:
        scrape(artist_names=sys.argv[1])
    else:
        scrape_rapper_list()
