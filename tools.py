# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:05:40 2015

@author: sunshine
"""
import sys
import re
import queue
import ujson as json
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
    if isinstance(utf, str):
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
