# -*- coding: utf-8 -*-
"""
Created on Mon Feb  2 15:41:54 2015

@author: sunshine
"""
import re
import traceback
import json
from threading import Thread
from os import mkdir
from hashlib import md5
from tools import *

class ThreadFetchHotArtists(Thread):
    def __init__(self, queue_in):
        Thread.__init__(self)
        self.qi = queue_in
    
    def run(self):
        while True:
            base = 'http://www.hotnewhiphop.com/artists/all/'
            query = '//span[@itemprop="name"]/a/@title'
            page, artists = self.qi.get()
            try:
                results = xpath_query_url(base + str(page), query)
            except Exception as e:
                print(e)
            if results:
                artists[page] = results
            self.qi.task_done()
            
    
            
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
                    
                    base = 'http://genius.com'
                    url = ('{}/artists/songs?for_artist_page={}&page=1&pagination=true'
                           .format(base, artist_id))
                    headers = {'Content-Type': 'application/x-www-form-urlencoded',
                               'X-Requested-With': 'XMLHttpRequest'}
        
                    page_link_xpath = '//div[@class="pagination"]//a[not(@class)]/text()'
                    page_nums = xpath_query_url(url, page_link_xpath, payload=headers)
                    if page_nums:
                        page_last = max([int(pagenum) for pagenum in page_nums])
                        for page in range(page_last + 1):
                            url = ('{}/artists/songs?for_artist_page={}&page={}&pagination=true'
                                    .format(base, artist_id, page))
                            self.qo.put({'url': (url), 
                                         'name': artist_name_corrected})             
                    print('finished processing links for ' + artist_name_corrected)
            self.qi.task_done()

class ThreadPageNameScrape(Thread):
    '''
        Grabs the song titles from the paginating calls to the designated
        artist page.  The extra headers are so that the server only gives us 
        the searched artist's paginated differential, and no extraneous html.
        
        When you scroll down to the bottom of the songs page in a web browser, 
        it will send a AJAX request to the server to grab a tiny packet of 
        html to insert into the existing results.
        
        This emulates that so we can get a much faster response from the 
        server, as well as reduce data transfer overhead by about 
        75% per request.  It's not a huge deal, but I'll take optimizations
        where I can get them.
    '''
    def __init__(self, queue_in, queue_out, payload):
        Thread.__init__(self)
        self.qi = queue_in
        self.qo = queue_out
        self.skip_links = payload['skip_links']

    def run(self):
        while True:
            payload = self.qi.get()
            try:
                url = payload['url']
                name = payload['name']
            except KeyError as e:
                print(e)

            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                       'X-Requested-With': 'XMLHttpRequest'}

            song_link_xpath = '//a[@class="song_name work_in_progress   song_link"]/@href'
            song_links = xpath_query_url(url, song_link_xpath, payload=headers)

            if song_links:
                for song in song_links:
                    if song not in self.skip_links and re.search('lyrics$', song):
                        self.qo.put((song, name))

            self.qi.task_done()


class ThreadLyrics(Thread):
    '''
        This class is the heart of the script, and is responsible for all of
        the parsing and structuring of the lyrics.  
        
        The main steps are as follows.  Grab a lyric url from the queue and 
        make a GET request.  Find the lyric html block, and resolve all nested
        text elements.  Grab metadata like featured artists/producers, song 
        name from elsewhere in response.  Resolve lyrical "blocks", which are 
        like verses or hooks, using a regex search.  
        
        If no blocks are resolved, try a more liberal search.
        Tag and categorize the blocks based on type (verse/hook/intro etc.)
        using the regex_blocks function.  Pair the raw lyrical text with 
        the processed blocks and metadata.  Send composite dictionary object 
        to the write queue to be saved to disk.
    '''
    def __init__(self, queue_in, queue_out ):
        Thread.__init__(self)
        self.qi = queue_in
        self.qo = queue_out

    def regex_blocks(self, regex, blocks, song_artist, features):
        '''
            takes a list of 2-tuples, finds the blocks that match the regular
            expression, then returns those matching blocks as a dictionary,
            deleting the matching raw blocks from the block list
        '''
        artist = None
        formatted_blocks = list()
        del_indeces = list()
        #arbitrary threshold for the amount of words in the block text
        #until it's considered a match
        length_threshold = 10

        for i, block in enumerate(blocks):
            regex_match = ''
            #main regex match for specified match
            try:
                regex_match = re.search(regex, strip_punc(block[0]))
            except Exception as e:
                print(e)
                traceback.print_exc()
            #if primary match was successful and block text is a certain length
            if regex_match and len(block[1].split()) > length_threshold:
                #defaults the block artist as a song artist
                artist = song_artist
                #checks if any of the featured artists are in the header
                for feature in features:
                    if re.search(an(feature).lower(), an(block[0]).lower()):
                        artist = feature

                #using a hash to key text blocks
                text_hash = md5(enc_str(block[1])).hexdigest()

                block_dict = {'header': block[0], 'text': block[1],
                              'artist': artist, 'text hash': text_hash}

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
            link, name_raw = self.qi.get()
            attempts = 0
            while attempts < 3:
                try:            
                    response = rq.get(link)
                    break
                except Exception as e:
                    attempts += 1
                    print(e)
                    traceback.print_exc()

            if response.status_code == 200:
                tree = html.fromstring(response.text)
                xpath_query = '//div[@class="lyrics"]//text()'
                results = tree.xpath(xpath_query)
 
                #checks to see if the lyrics have more than 10 lines
                if len(results) > 10:
 
                    #raw lyrics text
                    lyrics = ''.join(results)

                    #grab the song name and artist name
                    xq = '//span[@class="text_title"]/text()'
                    try:
                        song_name = tree.xpath(xq)[0].strip()
                    except Exception as e:
                        print(e)
                        traceback.print_exc()

                    xq = '//span[@class="text_artist"]/a/text()'
                    try:
                        name = tree.xpath(xq)[0].strip()
                    except Exception as e:
                        print(e)
                        traceback.print_exc()
 
                    #search for group objects, then return all elements if found
                    ft_group = tree.xpath('//span[@class="featured_artists"]//a/text()')
                    pr_group = tree.xpath('//span[@class="producer_artists"]//a/text()')

                    features = [ft.strip() for ft in ft_group]
                    producers = [pr.strip() for pr in pr_group]
     
                    #dictionary to store all of out raw and processed lyrics data
                    block_dict = {'link': link, 'raw': lyrics, 'pro': dict()}
    
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
                    outro = artist_regex('[oO]utro')
                    hooks = artist_regex('[hH]ook|[cC]horus')
                    bridge = artist_regex('[bB]ridge')
                    verses = artist_regex('[vV]erse|' + names_regex)
    
                    #catch-all regex, just to format the raw remainder blocks
                    remainders = artist_regex('([\w\W\n]*?)')

                    #primary entries that we need to add even if empty
                    block_dict['pro']['order'] = block_order
                    block_dict['pro']['blocks'] = {'hooks': hooks, 'verses': verses}
                    block_dict['pro']['artist'] = name
                    
                    #these are non essential entries to add if they exist
                    if outro:
                        block_dict['pro']['blocks']['outro'] = outro
                    if intro:
                        block_dict['pro']['blocks']['intro'] = intro
                    if bridge:
                        block_dict['pro']['blocks']['bridge'] = bridge
                    if features:
                        block_dict['pro']['features'] = features
                    if producers:
                        block_dict['pro']['producers'] = producers
                    if remainders:
                        block_dict['pro']['blocks']['remainders'] = remainders
                    #print('processed lyrics: ' + song_name)
                    self.qo.put((block_dict, song_name, name))
            else:
                print(song_name + ' download failed or aborted')

            self.qi.task_done()

class ThreadWrite(Thread):
    def __init__(self, queue_in, payload):
        Thread.__init__(self)
        self.qi = queue_in
        self.updating = payload['updating']

    def run(self):
        while True:
            data, song_name, name = self.qi.get()
 
            if not osp.isdir(ap('lyrics')):
                mkdir(ap('lyrics'))
            name = name.split('/')[-1]
            path = ap('lyrics/' + name + '.json')
            if not osp.isfile(path):          
                with open(path, 'w+') as f:
                    lyrics_db = dict()
                    lyrics_db[song_name] = data
                    try:
                        json.dump(lyrics_db, f, indent=4)
                        print('first write to: ' + name + ' successful')
                    except Exception as e:
                        print(e)
                        traceback.print_exc()
            else:
                with open(path, 'r+') as f:
                    if self.updating:
                        try:
                            lyrics_db = json.load(f)
                            lyrics_db[song_name] = data
                            json.dump(f, indent=4)
                        except Exception as e:
                            print(e)
                            traceback.print_exc()
                    else:
                        try:
                            lyrics_db = dict()
                            lyrics_db[song_name] = data
                            jsondata = json.dumps(lyrics_db, indent=4)[2:-1]
                            f.seek(-2, 2)
                            f.write(',\n')
                            f.write(jsondata)
                            f.write('}')
                        except Exception as e:
                            print(e)
                            traceback.print_exc()

            self.qi.task_done()