# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 00:49:33 2015

@author: sunshine
"""

import re
from collections import defaultdict
import random as rnd

def get_next_word(model, word):
    return rnd.choice(model[word])

def get_first_word(model):
    return rnd.choice(model.keys())

def get_blocks(db, artist, block_type):
    blocks = dict()
    for name, song in db.viewitems():
        for block in song['pro']['blocks'][block_type]:
            if re.search(artist.lower(), block['artist'].lower()):
                blocks[block['text hash']] = block['text']
    return blocks

def block_words(blocks):
    #jury rig to differentiate the newlines between blocks and other newlines
    composite = '\n\n'.join(blocks.values())
    return re.sub(r'\n(?!\n)', r'\n ', composite).split(' ')

def build_model(blocks):
    words = block_words(blocks)
    model = defaultdict(list)
    for i, word in enumerate(words):
        if i < len(words) - 2:
            model[' '.join(words[i:i+1])].append(' '.join(words[i+2:i+3]))
    return model

if __name__ == '__main__':
    #db = scraper.run()
    blocks = get_blocks(db, 'gucci mane', 'verses')
    model = build_model(blocks)
    limit = 500
    lyrics = ''
    prev_word = get_first_word(model)
    
    while len(lyrics) < limit:
        try:
            #we use the last word of the returned chain entry of the specified order to lookup the next chain
            next_word = get_next_word(model, prev_word.split(' ')[-1])
        except IndexError:
            break
        if len(lyrics) + len(next_word + ' ') > limit:
            break
        else:
            lyrics += next_word + ' '
        prev_word = next_word
    
    print(lyrics)