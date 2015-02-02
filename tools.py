# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:05:40 2015

@author: sunshine
"""
from os import path as osp
import sys
from unicodedata import normalize
import re
import Queue

def remove_last_word(line):
    return ' '.join(line.split()[:-1])


def ap(path):
    """
        Gets the absolute path of the directory and appends the path to it.
    """
    return osp.join(osp.dirname(osp.abspath(sys.argv[0])), path)

def an(string):
    '''
        returns just alphanumeric characters from a string
    '''
    pattern = re.compile('[\W_]+')
    return pattern.sub('', string)

def group_data(data, group_size):
    return [data[x:x+group_size] for x in range(0, len(data), group_size)]


def thread_pool(q, maxthreads, ThreadClass, qo=None):
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
        if isinstance(qo, Queue.Queue):
            t = ThreadClass(q, qo)
        else:
            t = ThreadClass(q)
        try:
            t.setDaemon(True)
            t.start()
            pool.append(t)
        except AttributeError as e:
            print(e)
    return pool

def enc_str(utf):
    '''
        Converts utf-8 strings to ascii by dropping invalid characters.
    '''
    if isinstance(utf, unicode):
        return normalize('NFKD', utf).encode('ascii', 'ignore')
    else:
        return str(utf)
