# -*- coding: UTF-8 -*-
from urllib.request import urlopen
import urllib.error

import sys

from fbchat import Client
from fbchat.models import *

import subprocess
from datetime import datetime
import re
import time

def get_infos():
    return matches_list

def send_msg(msg):
    client = Client('123composer@gmail.com', 'emplanted-wifi')
    client.send(Message(text=msg), thread_id='1042016150', thread_type=ThreadType.USER)
    client.logout()


class App():
    def __init__(self):
        #Stuff here

    def check(self):
        delay_until_check = 30
        new_status = get_infos()
        send_msg(new_status)
        time.sleep(10)

app = App()

while(True):
    app.check()