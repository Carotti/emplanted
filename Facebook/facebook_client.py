# -*- coding: UTF-8 -*-
from fbchat import Client
from fbchat.models import *
from getpass import getpass

import json
import threading

import urllib
from bs4 import BeautifulSoup
from urllib.request import urlopen

import random

import re

import paho.mqtt.client as mqtt
import time
import datetime

DEBUG = False
# DEMO is used so that the daily stats is initially not empty so the "Recommend me a plant"
# feature can be demoed
DEMO = True

# Used to get the text from the URL with info on a specific plant
# URLs are found in plant_dict
def get_text(url):
    html = urlopen(url).read()
    #parse the html
    soup = BeautifulSoup(html, "lxml")
    #remove non-text elements
    for non_text in soup(["script", "style"]):
        non_text.extract()

    text = soup.get_text()
    # return the lines as a list
    lines = (line.strip() for line in text.splitlines())
    return list(lines)

#searches for a sublist in a list and returns the big_list index of the element after the sub_list.
def after_sub_list_finder(big_list, sub_list):
    current_sub_list_ind = 0
    big_list_ind = 0
    for element in big_list:
        if element == sub_list[current_sub_list_ind] or (sub_list[current_sub_list_ind] and re.compile(sub_list[current_sub_list_ind]).match(element)):
            current_sub_list_ind = current_sub_list_ind + 1
            if current_sub_list_ind == len(sub_list):
                return big_list_ind + 1
        else:
            current_sub_list_ind = 0
        big_list_ind = big_list_ind + 1

# Initialise the MQTT client
client = mqtt.Client()

# global variable for commonly sent message
request_payload = json.dumps(["temp", "hum"])

def send_request():
    client.publish('esys/emplanted/request', bytes(request_payload, 'utf-8'))

# Subclass fbchat.Client and override required methods
class Thefish(Client):
    def __init__(self, user, password):
        Client.__init__(self, user, password)
        # The thread id for our group chat.
        # If the product were to be sold in the real world, the thread id would be assigned
        # to each user
        self.fish_tank_thread_id = '1863119160367263'

        # Sets the time when the lights must be turned on or off
        # Used for "one-off" light controls
        self.lights_off_time = None
        self.lights_on_time = None

        # Used to determine if the humidifier it increasing humidity
        # or if the water tank needs refilling
        self.hum_dev_history = [];

        # On time, off time for daily light controls
        self.lights_schedule = [None, None]

        # initial tank statistics, needs to change at regular interval
        # daily_stats is used to store the average daily temps/humidity for the past year
        if DEMO:
            self.daily_stats = {"temp": [10, 20, 15, 18, 21, 25, 25],"hum": [75, 70, 76, 75, 78, 77, 74]}
        else:
            self.daily_stats = {"temp": [], "hum": []}

        # Stats for every minute
        self.tank_stats = {"temp": [], "hum": []}

        # Used to send updates to the user when a plant becomes happy/unhappy
        self.unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}

        #log the current day and month to check for new day
        self.old_dt = datetime.datetime.now()

        #the name of the user
        self.username = ""
        #initially the tank is empty
        self.inside_tank = []

        #data from plantDict.json
        #accessed using: plant_data[<plant_name>][<parameter>]
        #e.g. minimum_temperature_for_basil = plant_data["basil"]["min-temp"]
        self.plant_data = json.load(open('plantDict.json'))

        #There are 2 steps to setting up the tank: specifying name and plants
        self.WelcomeDialog = 2*(int(not DEBUG))

        self.set_color_to_plant_health(0)

        #So it doesn't reply to itself
        self.exclude_text = []

        # Used to determine if the user needs to know the target settings
        self.display_status = False

        # Used to determine if the user only wants to know about one plant
        self.plant_of_interest = ""

        # Used to stop the client from constantly telling the user to refill
        # the water tank when it needs refilling
        self.send_refill_msg = True

        # Used to inform user so that they know the temperature and humidity is off auto
        self.manual_hum = None
        self.manual_temp = None

        # Used to inform the user that there is no target and that control is off
        # example use case: the fan is too noisy, so turn it off, even if it is too humid
        self.always_off = False

        #Startup greeting
        if not DEBUG:
            self.send_msg("Hi, I am your new smart planter :) ! What may I call you?")

    def send_msg(self, msg):
        #send a message
        if msg.lower() not in self.exclude_text:
            #ensure that it does not reply to itself
            self.exclude_text.append(msg.lower())
        self.send(Message(text=msg), thread_id= self.fish_tank_thread_id, thread_type=ThreadType.GROUP)
        #Give the user breathing time
        time.sleep(0.5)

    # Used to change the chat thread colour in Facebook messenger
    def change_color(self, tc):
        self.changeThreadColor(tc, thread_id = self.fish_tank_thread_id)

    # determine which plants are happy and which are not
    def calculate_health(self, curr_temp, curr_hum, specific_plant = None):
        # Initially assume everything is okay
        hum_dev = 0
        temp_dev = 0
        unhappy_plants = 0
        # Used to compare with class attribute equivalents to see if things have changed
        new_unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}
        new_happy_plants = []

        for plant in self.inside_tank:
            max_temp = self.plant_data[plant]["max-temp"]
            min_temp = self.plant_data[plant]["min-temp"]
            max_hum = self.plant_data[plant]["max-hum"]
            min_hum = self.plant_data[plant]["min-hum"]
            # Used to ensure that a happy plant must have right temperature and humidity
            happy_temp = False
            if curr_temp > max_temp:
                temp_dev = temp_dev + curr_temp - max_temp
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too hot"].append(plant)
            elif curr_temp < min_temp:
                temp_dev = temp_dev + curr_temp - min_temp
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too cold"].append(plant)
            else:
                happy_temp = True
            if curr_hum > max_hum:
                hum_dev = hum_dev + curr_hum - max_hum
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too humid"].append(plant)
            elif curr_hum < min_hum:
                hum_dev = hum_dev + curr_hum - min_hum
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too dry"].append(plant)
            elif happy_temp:
                new_happy_plants.append(plant)

        # inform user of any changes
        for plant in new_happy_plants:
            was_unhappy = False
            for problem in ["too cold", "too hot", "too dry", "too humid"]:
                if plant in self.unhappy_plants[problem]:
                    was_unhappy = True
                    break
            # Only inform user plant was happy if it was unhappy or they are asking about the plant
            if was_unhappy or (plant == self.plant_of_interest):
                self.plant_of_interest = ""
                self.send_msg("Your " + plant + " is now happy!" + u'\U0001F389')

        # randomised emojis for more human-like response
        emojis_dict = {"too cold": [u'\U0001F623', u'\U0001F62B', u'\U0001F630', u'\U0001F631'],
                       "too hot": [u'\U0001F525', u'\U0001F625', u'\U0001F62A', u'\U0001F613', u'\U0001F637'],
                       "too dry": [u'\U0001F480', u'\U0001F6B1', u'\U0001F611'],
                       "too humid": [u'\U0001F4A7', u'\U0001F30A', u'\U0001F4A6']}

        for problem in ["too cold", "too hot", "too dry", "too humid"]:
            new_to_problem = list(set(new_unhappy_plants[problem]) - set(self.unhappy_plants[problem]))
            for plant in new_to_problem:
                random_emoji_index = random.randint(0, len(emojis_dict[problem]) - 1)
                self.send_msg("Your " + plant + " is " + problem + emojis_dict[problem][random_emoji_index])

        # add humidity deviation to hum_dev_history
        self.hum_dev_history.append(hum_dev)

        if DEBUG:
            print(self.hum_dev_history)

        # limit size of history to past 10 hours
        if len(self.hum_dev_history) > 600:
            self.hum_dev_history = self.hum_dev_history[1:]
        if hum_dev < -10: # it's too dry
            # if the refill message hasn't been sent yet and we have a long enough history and the average humidity was very dry
            if (self.send_refill_msg) and (len(self.hum_dev_history) >= 100) and ((sum(self.hum_dev_history)/len(self.hum_dev_history))) < -10:
                self.send_refill_msg = False # only send once
                self.send_msg("Please refill my water tank " + u'\U0001F6B1')
        else:
            # the tank is not empty
            self.send_refill_msg = True

        self.unhappy_plants = new_unhappy_plants

        #happiness is based on fraction of plants which are happy
        self.set_color_to_plant_health(max(int(round(10 - 10*(unhappy_plants/(2*max(len(self.inside_tank), 1) ) ) ) ), 1))

    #Used to change the chat colours to be green if plants are in general happy -> red if plants are unhappy
    def set_color_to_plant_health(self, health_level):
        #health colours from low to high
        health_bar_colors = [
                                # Low Happiness/ no info
                                ThreadColor.SHOCKING,
                                ThreadColor.RADICAL_RED,
                                ThreadColor.LIGHT_CORAL,
                                # Medium Happiness
                                ThreadColor.CAMEO,
                                ThreadColor.PUMPKIN,
                                ThreadColor.GOLDEN_POPPY,
                                # High Happiness
                                ThreadColor.FERN,
                                ThreadColor.FERN,
                                ThreadColor.FREE_SPEECH_GREEN,
                                ThreadColor.FREE_SPEECH_GREEN,
                                ThreadColor.FREE_SPEECH_GREEN
                            ]
        self.change_color(health_bar_colors[health_level])

    # This function is called every minute when a reading is received
    def log_readings(self, info_dict):
        # Check if the lights need turning on or off
        current_date_time = datetime.datetime.now()

        # "on-off" manual control of lights
        if self.lights_off_time:
            if current_date_time.time() >= self.lights_off_time:
                self.lights_off()
                # stop it from happening the next day
                self.lights_off_time = None
        if self.lights_on_time:
            if current_date_time.time() >= self.lights_on_time:
                self.lights_on()
                # stop it from happening the next day
                self.lights_on_time = None

        # Daily control of lights
        if self.lights_schedule[0]:
            if current_date_time.time() >= self.lights_schedule[0]:
                self.lights_on()
            elif current_date_time.time() >= self.lights_schedule[1]:
                self.lights_off()

        # it's a new day
        if current_date_time.date() != self.old_dt.date():
            # record the average readings
            self.daily_stats["temp"].append(sum(self.tank_stats["temp"])/max(len(self.tank_stats["temp"]), 1))
            self.daily_stats["hum"].append(sum(self.tank_stats["hum"])/max(len(self.tank_stats["hum"]), 1))
            # don't record for more than a year
            if len(self.daily_stats["temp"]) > 365:
                self.daily_stats["temp"] = self.daily_stats["temp"][1:]
            if len(self.daily_stats["hum"]) > 365:
                self.daily_stats["hum"] = self.daily_stats["hum"][1:]
            # reset the tank_stats
            self.tank_stats = {"temp": [], "hum": []}
            # inform the users again if the plants are still unhappy
            self.unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}

        # Record the new reading
        self.tank_stats["temp"].append(info_dict["temp"])
        self.tank_stats["hum"].append(info_dict["hum"])

        # Remember todays date so we know when tomorrow is
        self.old_dt = current_date_time
        # Check if the plants are okay and set chat colours
        self.calculate_health(info_dict["temp"], info_dict["hum"])

        # The user wants to know the target environment
        if self.display_status:
            self.display_status = False
            self.send_msg("The temperature inside the planter is " + str(info_dict["temp"]) + u'\U000000B0' + "C and the humidity is " + str(info_dict["hum"]) + "%.")
            if not self.always_off:
                if self.manual_temp != None:
                    self.send_msg("The target temperature is manually set to " + str(self.manual_temp) + u'\U000000B0' + "C")
                else:
                    self.send_msg("The target temperature is optimal for the plants inside the tank")
                if self.manual_hum != None:
                    self.send_msg("The target humidity is manually set to " + str(self.manual_hum) + "%")
                else:
                    self.send_msg("The target humidity is optimal for the plants inside the tank")
            else:
                self.send_msg("The environment is no longer being monitored (turn monitoring on by replying 'Set environment automatically')")

    def lights_off(self):
        client.publish('esys/emplanted/lights', bytes("OFF", 'utf-8'))
        if DEBUG:
            self.send_msg("THE LIGHTS ARE NOW OFF")

    def lights_on(self):
        client.publish('esys/emplanted/lights', bytes("ON", 'utf-8'))
        if DEBUG:
            self.send_msg("THE LIGHTS ARE NOW ON")

    def set_light_schedule(self, on_t, off_t):
        # takes as input datetime.time objects
        self.lights_schedule[0] = on_t
        self.lights_schedule[1] = off_t
        if (self.lights_schedule[1].hour - self.lights_schedule[0].hour < 8):
            self.send_msg("Your plants might need more than 8 hours of light! Please put me in a sunny place " + u'\U0001F60E')

    def set_delay_schedule(self, on, time):
        # takes as input bool and datetime.datetime object
        if on:
            self.lights_on_time = time.time()
        else:
            self.lights_off_time = time.time()

    def acknowledge_plant(self):
        #Acknowledge that tank plants have changed
        print("Inside tank: ")
        print(self.inside_tank)
        self.send_msg("OK " + self.username + " " + u'\U0001F44C')
        inside_tank_set = list(set(self.inside_tank))
        if (self.inside_tank):
            # ensure grammar is correct
            if len(inside_tank_set) > 1:
                self.send_msg("I now know you have " + ", ".join(inside_tank_set[:-1])
                                + " and " + inside_tank_set[-1] + " inside the tank")
            else:
                self.send_msg("I now know you have " + inside_tank_set[0] + " inside the tank")
        self.send_target()

    def send_target(self, temp_override = None, hum_override = None):
        # calculate the new optimal environment and send it to the board
        # aim: try to make the most plants happy
        if (self.inside_tank):
            # the maximum (minimum temperature) of all the plant species
            max_min_temp = -100
            # the maximum (minimum humidity) of all the plant species
            max_min_hum  = 0
            # the minimum (maximum temperature) of all the plant species
            min_max_temp = 100
            # the minimum (maximum humidity) of all the plant species
            min_max_hum  = 100

            # iterate through all the plants
            for plant in self.inside_tank:
                # extract the data
                max_temp = self.plant_data[plant]["max-temp"]
                min_temp = self.plant_data[plant]["min-temp"]
                max_hum = self.plant_data[plant]["max-hum"]
                min_hum = self.plant_data[plant]["min-hum"]

                # set the max-mins and the min-maxs
                if (max_hum < min_max_hum):
                    min_max_hum = max_hum
                if (min_hum > max_min_hum):
                    max_min_hum = min_hum
                if (max_temp < min_max_temp):
                    min_max_temp = max_temp
                if (min_temp > max_min_temp):
                    max_min_temp = min_temp

            # choose the midpoint between the min-max and the max-min
            # This tries to get all the plants to be happy (though can't guaruntee it)
            # i.e. if max_min is above min_max
            target_temp = (max_min_temp + min_max_temp)/2
            target_hum = (max_min_hum + min_max_hum)/2

            # check to see if user has done a manual override
            if temp_override != None:
                # override manual controls
                self.always_off = False
                target_temp = temp_override
                self.manual_temp = temp_override
            if hum_override != None:
                # override manual controls
                self.always_off = False
                target_hum = hum_override
                self.manual_hum = hum_override

            # inform the board client
            target_payload = json.dumps([target_temp, target_hum])
            client.publish('esys/emplanted/target', bytes(target_payload, 'utf-8'))

            # as this is run whenever a new plant is added, turn the lights on (used when the tank goes from empty -> non-empty)
            if self.lights_schedule[0] and self.lights_schedule[1]:
                current_time = datetime.datetime.now().time()
                if (current_time >= self.lights_schedule[0]) and (current_time <= self.lights_schedule[1]):
                    self.lights_on()
        else:
            # turn outputs off to save electricity
            client.publish('esys/emplanted/fan', bytes("OFF", 'utf-8'))
            client.publish('esys/emplanted/hum', bytes("OFF", 'utf-8'))
            client.publish('esys/emplanted/lights', bytes("OFF", 'utf-8'))
            client.publish('esys/emplanted/heat', bytes("OFF", 'utf-8'))
            # inform user
            self.send_msg("Your tank is now empty!")

        # calculate the health from the most recent data
        if self.tank_stats["temp"] and self.tank_stats["hum"]:
            self.calculate_health(self.tank_stats["temp"][-1], self.tank_stats["hum"][-1])

    def remove_species(self, species_name):
        # used if the user removes all of one species
        print("Inside tank: ")
        print(self.inside_tank)
        print("Removing all of the " + species_name)
        self.inside_tank = [plant for plant in self.inside_tank if plant != species_name]

    def remove_target(self):
        # the user wants manual control of output
        self.manual_hum = None
        self.manual_temp = None
        self.always_off = True

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        # called whenever a FB message is received
        # lowercase everything to reduce variations
        text = (message_object.text).lower()
        # remove characters which are not used in processing
        if "?" in text:
            text = text.replace("?", "")
        # add a space so processing of target humidity is easier
        if "%" in text:
            text = text.replace("%", " %")
        # list of the words
        text_list = text.split(" ")
        # remove pointless words to allow processing via indexing
        # example: "add basil" == "add the basil"
        # after removing "the" we can look at the word after "add" and see if it is a plant name
        while "the" in text_list:
            text_list.remove("the")
        while "of" in text_list:
            text_list.remove("of")
        while "to" in text_list:
            text_list.remove("to")

        # regex used to detect floats (favoured over try, except)
        float_pattern = re.compile("-?\d+\.?\d*$")

        #All the response stuff goes here
        if (thread_id == self.fish_tank_thread_id) and ((message_object.text).lower() not in self.exclude_text):
            if DEBUG and text_list[0] == "temp" and text_list[2] == "hum":
                self.log_readings({"temp": int(text_list[1]), "hum": int(text_list[3])})
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
                        # if it is inside the tank
                        if text_list[plant_name_ind] in self.inside_tank:
                            self.inside_tank.remove(text_list[plant_name_ind])
                            self.acknowledge_plant()
            elif "suggest" in text or "recommend" in text:
                # recommend the user a plant which fits the temperature and humidity
                # i.e. finds species of plant compatible with what's in the tank
                temp_no_of_days = len(self.daily_stats["temp"])
                hum_no_of_days = len(self.daily_stats["hum"])
                # check if it is the first day
                if (temp_no_of_days == 0) or (hum_no_of_days == 0):
                    self.send_msg("I need to monitor you plants for at least one day before making suggestions!")
                else:
                    avg_temp = sum(self.daily_stats["temp"])/temp_no_of_days
                    max_temp = max(self.daily_stats["temp"])
                    min_temp = min(self.daily_stats["temp"])

                    # inform the user of the temperature stats
                    self.send_msg("Your daily average temperature for the last " + str(temp_no_of_days) + " days has a mean of " + str(avg_temp) + u'\U000000B0' + "C")
                    self.send_msg("and a maximum temperature of " + str(max_temp) + " and a minimum temperature of " + str(min_temp))

                    avg_hum = sum(self.daily_stats["hum"])/hum_no_of_days
                    max_hum = max(self.daily_stats["hum"])
                    min_hum = min(self.daily_stats["hum"])

                    # inform the user of the humidity stats
                    self.send_msg("Your daily average humidity for the last " + str(hum_no_of_days) + " days has a mean of " + str(avg_hum) + "%")
                    self.send_msg("and a maximum humidity of " + str(max_hum) + " and a minimum humidity of " + str(min_hum))

                    # user to store which plant is the best
                    chosen_plant = None
                    # used to measure suitability
                    min_deviation = 1000
                    for plant_name in self.plant_data:
                        # check it will be happy
                        good_min_temp = (self.plant_data[plant_name]["min-temp"] < min_temp)
                        good_max_temp = (self.plant_data[plant_name]["max-temp"] > max_temp)
                        good_min_hum = (self.plant_data[plant_name]["min-hum"] < min_hum)
                        good_max_hum = (self.plant_data[plant_name]["max-hum"] > max_hum)

                        if good_max_hum and good_min_hum and good_max_temp and good_min_temp:
                            # calculate ideal environment
                            opt_temp = (self.plant_data[plant_name]["min-temp"] + self.plant_data[plant_name]["max-temp"])/2
                            opt_hum = (self.plant_data[plant_name]["min-hum"] + self.plant_data[plant_name]["max-hum"])/2
                            # calculate deviation from current averages
                            plant_dev = abs(opt_temp - avg_temp) + abs(opt_hum - avg_hum)
                            if plant_dev < min_deviation:
                                # new optimal plant has been found
                                min_deviation = plant_dev
                                chosen_plant = plant_name

                    # if the environment can make a plant happy
                    if chosen_plant:
                        self.send_msg(self.username + ", your smart planter is ideal for growing " + chosen_plant)
                    else:
                        self.send_msg("I don't have any recommendations at the moment.")

            elif "tell me about " in text or ("how " in text and "do" in text_list):
                # The user wants instructions
                plant_name = ""
                # iterate over the words to see if there is a plant
                for name in text_list:
                    if name in self.plant_data:
                        plant_name = name
                    elif name[:-1] in self.plant_data:
                        plant_name = name[:-1]

                # a valid plant is mentioned
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
            elif "what " in text and "does" in text and "temperature" in text:
                # The user wants to know what temperatures are best suited for the plant
                plant_name = ""
                for name in text_list:
                    if name in self.plant_data:
                        plant_name = name

                if plant_name:
                    self.get_temps(plant_name)
            elif "auto" in text:
                # The user wants to let the board find optimal environment and control environment
                if DEBUG:
                    self.send_msg("BOARD IS NOW AUTO")
                self.manual_hum = None
                self.manual_temp = None
                self.always_off = False
                self.send_target()
            elif "set" in text and ("temperature" in text or "degree" in text):
                # User wants to set a target temperature manually (useful if there is a plant that we don't know about)
                for i in range(len(text_list[:-1])):
                    if "degree" in text_list[i + 1] and float_pattern.match(text_list[i]):
                        self.send_target(temp_override = float(text_list[i]), hum_override = None)
            elif "set" in text and ("humidifier" in text or "%" in text or "percent" in text):
                # User wants to set a target humidity manually (useful if there is a plant that we don't know about)
                for i in range(len(text_list[:-1])):
                    if ("%" in text_list[i + 1] or "percent" in text_list[i + 1]) and float_pattern.match(text_list[i]):
                        self.send_target(temp_override = None, hum_override = float(text_list[i]))
            elif "turn" in text and ("spray " in text or "humidifier " in text):
                # turn the humidifer on manually
                # the user no longer cares about targets:
                self.remove_target()
                if "on" in text:
                    client.publish('esys/emplanted/hum', bytes("ON", 'utf-8'))
                    if DEBUG:
                        self.send_msg("Spray ON")
                else:
                    client.publish('esys/emplanted/hum', bytes("OFF", 'utf-8'))
                    if DEBUG:
                        self.send_msg("Spray OFF")
            elif "turn" in text and ("heat" in text):
                # turn the humidifer on manually
                # the user no longer cares about targets:
                self.remove_target()
                if "on" in text:
                    client.publish('esys/emplanted/heat', bytes("ON", 'utf-8'))
                    if DEBUG:
                        self.send_msg("Heater ON")
                else:
                    client.publish('esys/emplanted/heat', bytes("OFF", 'utf-8'))
                    if DEBUG:
                        self.send_msg("Heater OFF")

            elif "turn" in text and ("fan " in text or "vent " in text):
                self.remove_target()
                if "on" in text:
                    client.publish('esys/emplanted/fan', bytes("ON", 'utf-8'))
                    if DEBUG:
                        self.send_msg("Fan ON")
                else:
                    client.publish('esys/emplanted/fan', bytes("OFF", 'utf-8'))
                    if DEBUG:
                        self.send_msg("Fan OFF")
            elif "turn" in text and "lights" in text:
                # lighting control
                on = True
                if "off" in text:
                    on = False;
                time_delay_float = 0.0
                if "in " in text: #e.g. turn lights off in 10 minutes
                    if "hour" in text:
                        # add up the hours
                        for t in text_list:
                            if float_pattern.match(t):
                                time_delay_float = time_delay_float + float(t)
                                break
                        # add fractions of hours
                        if "half" in text:
                            self.set_delay_schedule(on, datetime.datetime.now() + datetime.timedelta(minutes = 30) + datetime.timedelta(hours = time_delay_float))
                        elif "quarter" in text:
                            self.set_delay_schedule(on, datetime.datetime.now() + datetime.timedelta(minutes = 15) + datetime.timedelta(hours = time_delay_float))
                        else:
                            self.set_delay_schedule(on, datetime.datetime.now() + datetime.time_delay_float(hours = time_delay_float))
                    elif "minute" in text:
                        # add up the minutes
                        for t in text_list:
                            if float_pattern.match(t):
                                time_delay_float = time_delay_float + float(t)
                                break
                        self.set_delay_schedule(on, datetime.datetime.now() + datetime.timedelta(minutes = time_delay_float))
                elif "every" in text or "daily" in text:
                    # e.g. turn on lights every day at 6:30
                    time_pattern = re.compile("\d+:\d+(pm)?(am)?")
                    lazy_time_pattern = re.compile("\d+(a)?(p)?m")
                    # e.g. 7 o clock
                    lazy_time = ("clock" in text) or ("pm" in text) or ("am" in text)

                    # initilise times
                    start_time = None
                    end_time = None
                    hours_int = 0
                    minutes_int = 0

                    for t in text_list:
                        if time_pattern.match(t):
                            # user has set time in form HH:MM(pm/am/nothing (if so, 24 hour time assumed))
                            hours_minutes_strings = t.split(":")
                            if "m" in t: #not 24 hour time
                                hours_int = int(hours_minutes_strings[0]) + (("p" in hours_minutes_strings[1])*12)
                                minutes_int = int(hours_minutes_strings[1][:-2])
                            else: #is 24 hour time
                                hours_int = int(hours_minutes_strings[0])
                                minutes_int = int(hours_minutes_strings[1])

                            # set start or end time
                            if not start_time:
                                start_time = datetime.time(hours_int, minutes_int)
                            else:
                                end_time = datetime.time(hours_int, minutes_int)
                        elif lazy_time and lazy_time_pattern.match(t):
                            # e.g. turn lights on at 6pm for 5 hours
                            if "m" in t: #not 24 hour time
                                hours_int = int(t[:-2]) + (("p" in t)*12)
                            else:
                                hours_int = int(t)

                            # set start or end time
                            if not start_time:
                                start_time = datetime.time(hours_int)
                            else:
                                end_time = datetime.time(hours_int)
                        elif float_pattern.match(t):
                            # check for delay
                            time_delay_float = float(t)
                            print("REGEX time_delay_float: ")
                            print(time_delay_float)

                    if not end_time: #use a delay from the start time to set end_time
                        end_time = start_time
                        if "hour" in text:
                            if "half" in text:
                                time_delay_float = time_delay_float + 0.5
                            elif "quarter" in text:
                                time_delay_float = time_delay_float + 0.25
                            time_delay_float = time_delay_float * 60

                        print("hours: ")
                        print(end_time.hour + int(time_delay_float/60))
                        end_time = end_time.replace(minute = end_time.minute + round(time_delay_float % 60), hour = end_time.hour + int(time_delay_float/60))

                    self.set_light_schedule(start_time, end_time)
                elif on:
                    self.lights_on()
                else:
                    self.lights_off()

                print("Lights on time: ")
                print(self.lights_on_time)
                print("Lights off time: ")
                print(self.lights_off_time)

                print("Lights schedule: ")
                print(self.lights_schedule)
            elif "what" in text and ("up" in text or "reading" in text or "status" in text):
                # User wants to know the environment readings and plant status
                self.unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}
                self.display_status = True
                send_request()
            elif ("what" in text) or ("how" in text):
                # User wants to know the plant status
                for plant_name in text_list:
                    if plant_name in self.inside_tank:
                        for problem in ["too cold", "too hot", "too dry", "too humid"]:
                            if plant_name in self.unhappy_plants[problem]:
                                self.unhappy_plants[problem].remove(plant_name)
                        self.plant_of_interest = plant_name
                send_request()
            if "thank" in text:
                # easter egg
                self.send_msg("https://www.youtube.com/watch?v=79DijItQXMM")
            elif ("hello" in text) or ("hi" in text):
                # friendly greeting
                self.send_msg("Hello!")
            elif self.WelcomeDialog:
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
                        text = text.replace("and", ",")
                        if "," in text:
                            text = text.replace(" ", "")
                            text_list = text.split(",")
                        print(text_list)
                        for plant_name in text_list:
                            if plant_name in self.plant_data:
                                self.inside_tank.append(plant_name)
                    else:
                        #They've specified one plant
                        self.inside_tank.append(text)
                    self.acknowledge_plant()
                    self.send_msg("You can add and remove plants any time by typing 'add' or 'remove'")
                    self.WelcomeDialog = 0

    def get_description(self, plant_name):
        # sends the user the description of the plant
        info_list = get_text(self.plant_data[plant_name]["url"])
        desc_ind = after_sub_list_finder(info_list, ['Description', ''])
        if desc_ind:
            self.send_msg(info_list[desc_ind])

    def get_uses(self, plant_name):
        # sends the user the uses of the plant
        info_list = get_text(self.plant_data[plant_name]["url"])
        uses_ind = after_sub_list_finder(info_list, ['Uses', ''])
        if uses_ind:
            self.send_msg(info_list[uses_ind])

    def get_care_instr(self, plant_name):
        # sends the user the propagation details of the plant
        info_list = get_text(self.plant_data[plant_name]["url"])
        propagation_ind = after_sub_list_finder(info_list, ['', 'Propagation'])
        if propagation_ind:
            for line in info_list[propagation_ind:]:
                if line.lower() == "common pests and diseases" or line.lower() == "references":
                    break
                elif len(line) > 40:
                    # it is not a caption
                    self.send_msg(line)

    def get_seeding(self, plant_name):
        # sends user information about when to plant seeds
        info_list = get_text(self.plant_data[plant_name]["url"])
        seeding_ind = after_sub_list_finder(info_list, ['', 'Propagation'])
        if seeding_ind:
            for line in info_list[seeding_ind:]:
                if line.lower() == "common pests and diseases" or line.lower() == "references":
                    break
                elif "seed" in line and len(line) > 40:
                    # it is not a caption and mentions seed
                    self.send_msg(line)

    def get_harvest(self, plant_name):
        # sends user information about when to harvest the plant
        info_list = get_text(self.plant_data[plant_name]["url"])
        harvesting_ind = after_sub_list_finder(info_list, ['', 'Harvest[a-z]*'])
        if harvesting_ind:
            self.send_msg(info_list[harvesting_ind])

    def get_temps(self, plant_name):
        # sends user information about detailed temperature requirements of a plant
        info_list = get_text(self.plant_data[plant_name]["url"])
        temps_ind = after_sub_list_finder(info_list, ['', 'Propagation'])
        if temps_ind:
            for line in info_list[temps_ind:]:
                if line.lower() == "common pests and diseases" or line.lower() == "references":
                    break
                elif (("temperature" in line) or ("degrees" in line)) and len(line) > 40:
                    # only send the sentence that contains the temperature
                    sentences = line.split(". ")
                    for s in sentences:
                        if ("1" in s or "2" in s or "3" in s) and (("temperature" in line) or ("degrees" in line)) and len(line) > 20:
                            self.send_msg(s)
                            return




#Start the client so that on_message can use fb_client
fb_client = Thefish(input("Username: "), getpass(prompt = "Password: "))
fb_always_on_thread = threading.Thread(target = fb_client.listen)
fb_always_on_thread.start()

# Getting info from board stuff:
# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("esys/emplanted/readings")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+ " " + str(msg.payload))
    payload_dict = json.loads(msg.payload.decode("utf-8"))
    fb_client.log_readings(payload_dict)

client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)

def poll_sensors():
    #Poll every minute
    while (True):
        send_request()
        time.sleep(60)

polling_always_on_thread = threading.Thread(target = poll_sensors)
#start polling
polling_always_on_thread.start()

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
