# -*- coding: UTF-8 -*-
from fbchat import Client
from fbchat.models import *
import json

import paho.mqtt.client as mqtt

def send_msg(msg):
    client = Client('123composer@gmail.com', 'emplanted-wifi')
    client.send(Message(text=msg), thread_id='1042016150', thread_type=ThreadType.USER)
    client.logout()

def change_color(tc):
    client = Client('123composer@gmail.com', 'emplanted-wifi')
    changeThreadColor(tc, thread_id = '1042016150')
    client.logout()

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("esys/emplanted/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+ " " + str(msg.payload))
    payload_dict = json.loads(msg.payload)[0]
    if (payload_dict["name"] == "warning"):
    	change_color(ThreadColor.RADICAL_RED)
    	send_msg(payload_dict["text"])
    	print("Warning sent!")

change_color(ThreadColor.FREE_SPEECH_GREEN)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
