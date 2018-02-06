# -*- coding: UTF-8 -*-
from fbchat import Client
from fbchat.models import *
from getpass import getpass

import json
import threading

import urllib
from bs4 import BeautifulSoup
from urllib.request import urlopen

import re

import paho.mqtt.client as mqtt
import time
from datetime import datetime

def get_text(url):
    html = urlopen(url).read()
    soup = BeautifulSoup(html, "lxml")

    for non_text in soup(["script", "style"]):
        non_text.extract()

    text = soup.get_text()

    lines = (line.strip() for line in text.splitlines())
    return list(lines)

def after_sub_list_finder(big_list, sub_list):
    current_sub_list_ind = 0
    big_list_ind = 0;
    for element in big_list:
        if element == sub_list[current_sub_list_ind] or (sub_list[current_sub_list_ind] and re.compile(sub_list[current_sub_list_ind]).match(element)):
            current_sub_list_ind = current_sub_list_ind + 1
            if current_sub_list_ind == len(sub_list):
                return big_list_ind + 1
        else:
            current_sub_list_ind = 0
        big_list_ind = big_list_ind + 1

# Subclass fbchat.Client and override required methods
class Thefish(Client):
    def __init__(self, user, password):
        Client.__init__(self, user, password)
        self.fish_tank_thread_id = '1863119160367263'

        #initial tank statistics, needs to change at regular interval
        self.tank_stats = {"temp": [], "hum": []}
        self.daily_stats = {"temp": [], "hum": []}

        #log the current day and month to check for new day
        self.old_dt = datetime.now()

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
        dev = 0;
        for plant in self.inside_tank:
            maxTemp = self.plant_data[plant]["max-temp"]
            minTemp = self.plant_data[plant]["min-temp"]
            maxHum = self.plant_data[plant]["max-hum"]
            minHum = self.plant_data[plant]["min-hum"]
            currentTemp = self.tank_stats["temp"][-1]
            currentHum = self.tank_stats["hum"][-1]
            if currentTemp > maxTemp:
                dev += currentTemp - maxTemp
            else if currentTemp < minTemp:
                dev += minTemp - currentTemp
            if currentHum > maxHum:
                dev += currentHum - maxHum
            else if currentHum < minHum:
                dev += minHum - currentHum
        avgDev = dev/len(self.inside_tank)
        self.set_color_to_plant_health(int(round(avgDev)))

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
        pass


    def log_readings(self, info_dict):
        #TODO needs to store the current reading inside the self.tank_stats
        # Check if it is a new day using python datetime
        # If it is a new day append the average of the tank_stats list into the daily_stats
        # tank_stats = []
        # If daily_stats is greater than length 30, delete the first in the listen
        # If the current reading is outside the range of one of the plants, send a message to the user saying which plants are unhappy and why

        current_date_time = datetime.now()
        if self.old_dt.hour != current_date_time.hour:
            self.tank_stats["temp"] = info_dict["temp"]
            self.tank_stats["hum"] = info_dict["hum"]
            self.oldt_dt = current_date_time
        if self


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
        print("Inside tank: ")
        print(self.inside_tank)
        print("Removing all of the " + species_name)
        self.inside_tank = [plant for plant in self.inside_tank if plant != species_name]

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        #lowercase everything to reduce variations
        text = (message_object.text).lower()
        if "?" in text:
            text = text.replace("?", "")
        #list of the words
        text_list = text.split(" ")
        if "the" in text_list:
            text_list.remove("the")
        if "of" in text_list:
            text_list.remove("of")

        #All the response stuff goes here
        if (thread_id == self.fish_tank_thread_id) and ((message_object.text).lower() not in self.exclude_text):
            if "my name is " in text:
                #Get the last word
                self.username = text_list[-1]
                self.send_msg("Okay " + self.username + ", I'll make sure I call you that in future!")
            if "add" in text:
                #just in case the user says "add my basil"
                if "my" in text_list:
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
                if "my" in text_list:
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
                    if "a" in text_list:
                        text_list.remove("a")
                    if "an" in text_list:
                        text_list.remove("an")
                    plant_name_ind = text_list.index("remove") + 1
                    if plant_name_ind < len(text_list):
                        if text_list[plant_name_ind] in self.inside_tank:
                            self.inside_tank.remove(text_list[plant_name_ind])
                            self.acknowledge_plant()
            elif "tell me about " in text or "how " in text:
                plant_name = ""
                for name in text_list:
                    if name in self.plant_data:
                        plant_name = name

                if plant_name:
                    if "grow" in text or "care" in text or "requirements" in text:
                        self.get_care_instr(plant_name)
                    elif "harvest" in text:
                        self.get_harvest(plant_name)
                    elif "use" in text:
                        self.get_uses(plant_name)
                    elif "seed" in text or "spread" in text:
                        self.get_seeding(plant_name)
                    else:
                        self.get_description(plant_name)

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
    def get_description(self, plant_name):
        info_list = get_text(self.plant_data[plant_name]["url"])
        desc_ind = after_sub_list_finder(info_list, ['Description', ''])
        if desc_ind:
            self.send_msg(info_list[desc_ind])

    def get_uses(self, plant_name):
        info_list = get_text(self.plant_data[plant_name]["url"])
        uses_ind = after_sub_list_finder(info_list, ['Uses', ''])
        if uses_ind:
            self.send_msg(info_list[uses_ind])

    def get_care_instr(self, plant_name):
        info_list = get_text(self.plant_data[plant_name]["url"])
        propagation_ind = after_sub_list_finder(info_list, ['', 'Propagation'])
        if propagation_ind:
            for line in info_list[propagation_ind:]:
                if line.lower() == "common pests and diseases" or line.lower() == "references":
                    break
                elif len(line) > 40:
                    self.send_msg(line)

    def get_seeding(self, plant_name):
        info_list = get_text(self.plant_data[plant_name]["url"])
        seeding_ind = after_sub_list_finder(info_list, ['', 'Propagation'])
        if seeding_ind:
            for line in info_list[seeding_ind:]:
                if line.lower() == "common pests and diseases" or line.lower() == "references":
                    break
                elif "seed" in line and len(line) > 40:
                    self.send_msg(line)

    def get_harvest(self, plant_name):
        info_list = get_text(self.plant_data[plant_name]["url"])
        harvesting_ind = after_sub_list_finder(info_list, ['', 'Harvest[a-z]*'])
        if harvesting_ind:
            self.send_msg(info_list[harvesting_ind])

    def get_disease(self, plant_name, keywords):
        #Do some fancy regex stuff here!
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
