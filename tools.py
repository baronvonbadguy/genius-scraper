# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:05:40 2015

@author: sunshine
"""
from os import path as osp
import sys
from unicodedata import normalize


def remove_last_word(line):
    return ' '.join(line.split()[:-1])


def ap(path):
    """
        Gets the absolute path of the directory and appends the path to it.
    """
    return osp.join(osp.dirname(osp.abspath(sys.argv[0])), path)


def group_data(data, group_size):
    return [data[x:x+group_size] for x in range(0, len(data), group_size)]


def thread_pool(q, maxthreads, ThreadClass, payload=None):
    '''
        Populates a threadpool in the given queue with the passed class.

        q
            Queue instance to populate with threads
        maxthreads
            Maximum number of threads that will be allowed in the queue
        ThreadClass
            Class that extends Thread class to be run
    '''
    for x in range(maxthreads):
        if isinstance(payload, dict):
            t = ThreadClass(q, payload)
        else:
            t = ThreadClass(q)
        t.setDaemon(True)
        t.start()


def enc_str(utf):
    '''
        Converts utf-8 strings to ascii by dropping invalid characters.
    '''
    if isinstance(utf, unicode):
        return normalize('NFKD', utf).encode('ascii', 'ignore')
    else:
        return str(utf)
