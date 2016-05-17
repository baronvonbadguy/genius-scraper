# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:05:40 2015

@author: sunshine
"""
import sys
import re
import queue
import json
from os import listdir
from os import path as osp
import os
from unicodedata import normalize
from collections import defaultdict

import requests as rq
from lxml import html


def remove_last_word(line):
    return ' '.join(line.split()[:-1])

def enc_str(utf):
    '''
        Converts utf-8 strings to ascii by dropping invalid characters.
    '''
    if isinstance(utf, unicode):
        return normalize('NFKD', utf).encode('ascii', 'ignore')
    else:
        return str(utf)

def ap(path):
    """
        Gets the absolute path of the directory and appends the path to it.
    """
    return osp.join(osp.abspath(os.getcwd()), path)

def an(string):
    '''
        returns just alphanumeric characters from a string
    '''
    pattern = re.compile('[\W_]+')
    return pattern.sub('', string)

def strip_punc(string):
    '''
        strips common punctuation, leaving spaces in
    '''
    pattern = re.compile(r'[\(\)\[\]\*\$\\]+')
    return pattern.sub('', string)

def group_data(data, group_size):
    return [data[x:x+group_size] for x in range(0, len(data), group_size)]


def thread_pool(q, maxthreads, ThreadClass, qo=None, payload=None):
    '''
        Populates a threadpool in the given queue with the passed class.

        q
            Queue instance to populate with threads
        maxthreads
            Maximum number of threads that will be allowed in the queue
        ThreadClass
            Class that extends Thread class to be run
    '''
    pool = list()
    for x in range(maxthreads):
        if isinstance(qo, queue.Queue):
            if payload:
                t = ThreadClass(q, qo, payload=payload)
            else:
                t = ThreadClass(q, qo)
        else:
            if payload:
                t = ThreadClass(q, payload=payload)
            else:
                t = ThreadClass(q)
        try:
            t.setDaemon(True)
            t.start()
            pool.append(t)
        except AttributeError as e:
            print(e)
    return pool

def xpath_query_url(url, xpath_query, payload=dict()):
    '''Gets urls and performing an XPath Query'''
    headers = {'User-Agent': 'Mozilla/5.0 Gecko/20100101 Firefox/35.0'}
    if payload:
        headers.update(payload)
    try:
        response = rq.get(url, headers=headers)
        #creates an html tree from the data
        tree = html.fromstring(response.text)
        #XPATH query to grab all of the artist urls, then we grab the first
        return tree.xpath(xpath_query)
    except Exception as e:
        print(e)
        return ''

def load_all_artists():
    db = defaultdict()
    for fp in listdir(ap('lyrics/')):
        ab_fp = ap('lyrics/' + fp)
        if osp.isfile(ab_fp):
            name = fp.replace('.json', '')
            with open(ab_fp, 'r') as f:
                db[name] = json.load(f)
    return db


def load_all_blocks(block_type=None):
    db = dict()
    for fp in listdir(ap('lyrics/')):
        ab_fp = ap('lyrics/' + fp)
        if osp.isfile(ab_fp):
            with open(ab_fp, 'r') as f:
                artist = json.load(f)
                for song in artist.keys():
                    for bg_key in artist[song]['pro']['blocks'].keys():
                        if not block_type or bg_key in block_type:
                            for b in artist[song]['pro']['blocks'][bg_key]:
                                db[b['text hash']] = {'artist': b['artist'],'text': b['text']}
    return db