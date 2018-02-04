# -*- coding: UTF-8 -*-
from fbchat import Client
from fbchat.models import *
from getpass import getpass

import json
import threading

import urllib
from bs4 import BeautifulSoup
from urllib.request import urlopen

import paho.mqtt.client as mqtt
import time

def get_text(url):
    html = urlopen(url).read()
    soup = BeautifulSoup(html, "lxml")

    for non_text in soup(["script", "style"]):
        non_text.extract()

    text = soup.get_text()

    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

# Subclass fbchat.Client and override required methods
class Thefish(Client):
    def __init__(self, user, password):
        Client.__init__(self, user, password)
        self.fish_tank_thread_id = '1863119160367263'

        #initial tank statistics, needs to change at regular interval
        self.tank_stats = {"temp": [], "hum": []}

        #the name of the rich guy/girl
        self.username = ""
        #initially the tank is empty
        self.inside_tank = []

        #data from plantDict.json
        #accessed using: plant_data[<plant_name>][<parameter>]
        #e.g. minimum_temperature_for_basil = plant_data["basil"]["min-temp"]
        self.plant_data = json.load(open('plantDict.json'))

        #There are 2 steps to setting up the tank: specifying name and plants
        self.WelcomeDialog = 2

        self.set_color_to_plant_health(0);

        #So it doesn't reply to itself
        self.exclude_text = []

        #Startup greeting
        self.send_msg("Hi, I am your new fish tank :) ! What may I call you?")

    def send_msg(self, msg):
        #send a message
        if msg.lower() not in self.exclude_text:
            #ensure that it does not reply to itself
            self.exclude_text.append(msg.lower())
        self.send(Message(text=msg), thread_id= self.fish_tank_thread_id, thread_type=ThreadType.GROUP)
        #Give the user breathing time
        time.sleep(0.5)

    def change_color(self, tc):
        self.changeThreadColor(tc, thread_id = self.fish_tank_thread_id)

    def calculate_health(self):
        #Needs to look at tank_stats, plant_data and inside_tank
        #returns a rating from 1 to 10
        pass

    def set_color_to_plant_health(self, health_level):
        #health colours from low to high
        health_bar_colors = [
                                # Low HP/ no infos yet
                                ThreadColor.SHOCKING,
                                ThreadColor.RADICAL_RED,
                                ThreadColor.LIGHT_CORAL,
                                # Medium HP
                                ThreadColor.CAMEO,
                                ThreadColor.PUMPKIN,
                                ThreadColor.GOLDEN_POPPY,
                                # High HP
                                ThreadColor.FERN,
                                ThreadColor.FERN,
                                ThreadColor.FREE_SPEECH_GREEN,
                                ThreadColor.FREE_SPEECH_GREEN,
                                ThreadColor.FREE_SPEECH_GREEN
                            ]
        self.change_color(health_bar_colors[health_level])

    def inform_user(self, info_dict):
        if (info_dict["name"] == "warning"):
            set_color_to_plant_health(1)
            self.send_msg(payload_dict["text"])
            print("Warning sent!")
        # change tank_stats

    def acknowledge_plant(self):
        #Acknowledge that tank plants have changed
        print("Inside tank: ")
        print(self.inside_tank)
        self.send_msg("OK" + u'\U0001F44C')
        inside_tank_set = list(set(self.inside_tank))
        if (self.inside_tank):
            #Proper good grammer
            if len(inside_tank_set) > 1:
                self.send_msg("I now know you have " + ", ".join(inside_tank_set[:-1])
                                + " and " + inside_tank_set[-1] + " inside the tank")
            else:
                self.send_msg("I now know you have " + inside_tank_set[0] + " inside the tank")
        else:
            self.send_msg("Your tank is now empty!")

    def remove_species(self, species_name):
        for plant_name in self.inside_tank:
            if plant_name == species_name:
                self.inside_tank.remove(species_name)

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        #lowercase everything to reduce variations
        text = (message_object.text).lower()
        #list of a the words
        text_list = text.split(" ")
        #All the response stuff goes here
        if (thread_id == self.fish_tank_thread_id) and (text not in self.exclude_text):
            if "my name is " in text:
                #Get the last word
                self.username = text_list[-1]
                self.send_msg("Okay " + self.username + ", I'll make sure I call you that in future!")
            if "add" in text:
                #just in case the user says "add my basil"
                text_list.remove("my")
                #the word after "add" is the plant name
                plant_name_ind = text_list.index("add") + 1
                #make sure we don't get index error
                if plant_name_ind < len(text_list):
                    #only add it if we have heard of it
                    if text_list[plant_name_ind] in self.plant_data:
                        #Add it to the tank
                        self.inside_tank.append(text_list[plant_name_ind])
                        if "remove" not in text:
                            #Acknowledge each message only once
                            self.acknowledge_plant()
            if "remove" in text:
                #just in case the user says "remove my basil"
                text_list.remove("my")
                if "all" in text:
                    #either the user wants to remove all plants or all of one species
                    plant_name_ind = text_list.index("all") + 1
                    if plant_name_ind < len(text_list):
                        if text_list[plant_name_ind] not in self.inside_tank:
                            #remove all
                            self.inside_tank = []
                        else:
                            #remove all of one species
                            self.remove_species(text_list[plant_name_ind])
                    else:
                        #remove all
                        self.inside_tank = []
                    self.acknowledge_plant()
                #the word after "remove" is the plant name
                else:
                    #remove a single plant
                    text_list.remove("a")
                    text_list.remove("an")
                    plant_name_ind = text_list.index("remove") + 1
                    if plant_name_ind < len(text_list):
                        if text_list[plant_name_ind] in self.inside_tank:
                            self.inside_tank.remove(text_list[plant_name_ind])
                            self.acknowledge_plant()
            if self.WelcomeDialog:
                #We don't know what the name of the user is
                if not (self.username):
                    self.username = text.title()
                    self.send_msg(self.username + " it's nice to meet you :)")
                    self.send_msg("You can change your name any time by typing 'my name is ...'")
                    self.send_msg("What are you planting today?")
                    self.WelcomeDialog = self.WelcomeDialog - 1
                #The user is specifying what is in the tank and not correct their name
                elif (not (self.inside_tank)) and ("my name is " not in text):
                    if text not in self.plant_data:
                        #They've specified a list of plants
                        text.replace("and", "")
                        if "," in text:
                            text.replace(" ", "")
                            text_list = text.split(",")

                        for plant_name in text_list:
                            if plant_name in self.plant_data:
                                self.inside_tank.append(plant_name)
                    else:
                        #They've specified one plant
                        self.inside_tank.append(text)
                    self.acknowledge_plant()
                    self.send_msg("You can add and remove plants any time by typing 'add' or 'remove'")
                    self.WelcomeDialog = 0
            else:
                pass




#Start the client so that on_message can use fb_client
fb_client = Thefish(input("Username: "), getpass(prompt = "Password: "))
always_on_thread = threading.Thread(target = fb_client.listen)
always_on_thread.start()

# Getting info from board stuff:
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
    fb_client.inform_user(payload_dict)

#All the MQTT stuff - uncomment out when you have the board:

# client = mqtt.Client()
# client.on_connect = on_connect
# client.on_message = on_message

# client.connect("localhost", 1883, 60)

# # Blocking call that processes network traffic, dispatches callbacks and
# # handles reconnecting.
# # Other loop*() functions are available that give a threaded interface and a
# # manual interface.
# client.loop_forever()
