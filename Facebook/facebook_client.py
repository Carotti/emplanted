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

DEBUG = True

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
    big_list_ind = 0
    for element in big_list:
        if element == sub_list[current_sub_list_ind] or (sub_list[current_sub_list_ind] and re.compile(sub_list[current_sub_list_ind]).match(element)):
            current_sub_list_ind = current_sub_list_ind + 1
            if current_sub_list_ind == len(sub_list):
                return big_list_ind + 1
        else:
            current_sub_list_ind = 0
        big_list_ind = big_list_ind + 1

def times_match(time1, time2):
    if (time1.hour == time2.hour) and (time1.minute == time2.minute):
        return True
    else:
        return False

#All the MQTT stuff - uncomment out when you have the board:

client = mqtt.Client()

request_payload = json.dumps(["temp", "hum"])

def send_request():
    client.publish('esys/emplanted/request', bytes(request_payload, 'utf-8'))

# Subclass fbchat.Client and override required methods
class Thefish(Client):
    def __init__(self, user, password):
        Client.__init__(self, user, password)
        self.fish_tank_thread_id = '1863119160367263'
        self.lights_off_time = None
        self.lights_on_time = None

        # On time, off time
        self.lights_schedule = [None, None]

        #initial tank statistics, needs to change at regular interval
        self.tank_stats = {"temp": [], "hum": []}
        self.daily_stats = {"temp": [], "hum": []}

        self.unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}

        #log the current day and month to check for new day
        self.old_dt = datetime.datetime.now()

        #the name of the rich guy/girl
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

        self.display_status = False

        self.plant_of_interest = ""

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

    def change_color(self, tc):
        self.changeThreadColor(tc, thread_id = self.fish_tank_thread_id)

    def calculate_health(self, curr_temp, curr_hum, specific_plant = None):
        #Needs to look at tank_stats, plant_data and inside_tank
        #returns a rating from 1 to 10
        hum_dev = 0
        temp_dev = 0
        unhappy_plants = 0
        new_unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}
        new_happy_plants = []
        for plant in self.inside_tank:
            max_temp = self.plant_data[plant]["max-temp"]
            min_temp = self.plant_data[plant]["min-temp"]
            max_hum = self.plant_data[plant]["max-hum"]
            min_hum = self.plant_data[plant]["min-hum"]
            happy_temp = False
            if curr_temp > max_temp:
                temp_dev = temp_dev + curr_temp - max_temp
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too hot"].append(plant)
            elif curr_temp < min_temp:
                temp_dev += temp_dev + min_temp - curr_temp
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too cold"].append(plant)
            else:
                happy_temp = True
            if curr_hum > max_hum:
                hum_dev = hum_dev + curr_hum - max_hum
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too humid"].append(plant)
            elif curr_hum < min_hum:
                hum_dev = hum_dev + min_hum - curr_hum
                unhappy_plants = unhappy_plants + 1
                new_unhappy_plants["too dry"].append(plant)
            elif happy_temp:
                new_happy_plants.append(plant)

        for plant in new_happy_plants:
            was_unhappy = False
            for problem in ["too cold", "too hot", "too dry", "too humid"]:
                if plant in self.unhappy_plants[problem]:
                    was_unhappy = True
                    break
            if was_unhappy or (plant == self.plant_of_interest):
                self.plant_of_interest = ""
                self.send_msg("Your " + plant + " is now happy!" + u'\U0001F389')

        emojis_dict = {"too cold": [u'\U0001F623', u'\U0001F62B', u'\U0001F630', u'\U0001F631'],
                       "too hot": [u'\U0001F525', u'\U0001F625', u'\U0001F62A', u'\U0001F613', u'\U0001F637'],
                       "too dry": [u'\U0001F480', u'\U0001F6B1', u'\U0001F611'],
                       "too humid": [u'\U0001F4A7', u'\U0001F30A', u'\U0001F4A6']}

        for problem in ["too cold", "too hot", "too dry", "too humid"]:
            new_to_problem = list(set(new_unhappy_plants[problem]) - set(self.unhappy_plants[problem]))
            for plant in new_to_problem:
                random_emoji_index = random.randint(0, len(emojis_dict[problem]) - 1)
                self.send_msg("Your " + plant + " is " + problem + emojis_dict[problem][random_emoji_index])

        if hum_dev > 10:
            #SPRAY WATER
            pass
        elif hum_dev < -10:
            #TURN ON FAN
            pass
        elif temp_dev > 10:
            #TURN ON FAN
            pass
        elif temp_dev < -10:
            #TURN ON HEATER
            pass

        self.unhappy_plants = new_unhappy_plants

        self.set_color_to_plant_health(max(int(round(10 - 10*(unhappy_plants/(2*max(len(self.inside_tank), 1) ) ) ) ), 1))


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

    def log_readings(self, info_dict):
        #TODO needs to store the current reading inside the self.tank_stats
        # Check if it is a new day using python datetime
        # If it is a new day append the average of the tank_stats list into the daily_stats
        # tank_stats = []
        # If daily_stats is greater than length 30, delete the first in the listen
        # If the current reading is outside the range of one of the plants, send a message to the user saying which plants are unhappy and why

        current_date_time = datetime.datetime.now()

        if self.lights_off_time:
            if times_match(current_date_time, self.lights_off_time):
                self.lights_off()
                self.lights_off_time = None
        if self.lights_on_time:
            if times_match(current_date_time, self.lights_on_time):
                self.lights_on()
                self.lights_on_time = None

        # On time, off time
        if self.lights_schedule[0]:
            if times_match(current_date_time, self.lights_schedule[0]):
                self.lights_on()
            elif times_match(current_date_time, self.lights_schedule[1]):
                self.lights_off()


        if current_date_time.date() != self.old_dt.date():
            self.daily_stats["temp"].append(sum(self.tank_stats["temp"])/max(len(self.tank_stats["temp"]), 1))
            self.daily_stats["hum"].append(sum(self.tank_stats["hum"])/max(len(self.tank_stats["hum"]), 1))
            if len(self.daily_stats["temp"]) > 64:
                self.daily_stats["temp"] = self.daily_stats["temp"][1:]
            if len(self.daily_stats["hum"]) > 64:
                self.daily_stats["hum"] = self.daily_stats["hum"][1:]
            self.tank_stats = {"temp": [], "hum": []}
            self.unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}
        self.tank_stats["temp"].append(info_dict["temp"])
        self.tank_stats["hum"].append(info_dict["hum"])
        self.old_dt = current_date_time
        self.calculate_health(info_dict["temp"], info_dict["hum"])
        if self.display_status:
            self.display_status = False
            self.send_msg("The temperature inside the planter is " + str(info_dict["temp"]) + u'\U000000B0' + "C and the humidity is " + str(info_dict["hum"]) + "%.")

    def lights_off(self):
        print ("CALLING LIGHTS OFF")
        client.publish('esys/emplanted/lights', bytes("OFF", 'utf-8'))
        if DEBUG:
            self.send_msg("THE LIGHTS ARE NOW OFF")

    def lights_on(self):
        client.publish('esys/emplanted/lights', bytes("ON", 'utf-8'))
        if DEBUG:
            self.send_msg("THE LIGHTS ARE NOW ON")

    def set_light_schedule(self, on_t, off_t):
        self.lights_schedule[0] = on_t
        self.lights_schedule[1] = off_t
        if (self.lights_schedule[1].hour - self.lights_schedule[0].hour < 8):
            self.send_msg("Your plants might need more than 8 hours of light! Please put me in a sunny place " + u'\U0001F60E')


    def set_delay_schedule(self, on, time):
        if on:
            self.lights_on_time = time
        else:
            self.lights_off_time = time

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

        if self.tank_stats["temp"] and self.tank_stats["hum"]:
            self.calculate_health(self.tank_stats["temp"][-1], self.tank_stats["hum"][-1])

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
                        if text_list[plant_name_ind] in self.inside_tank:
                            self.inside_tank.remove(text_list[plant_name_ind])
                            self.acknowledge_plant()
            elif "tell me about " in text or ("how " in text and "do" in text):
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
            elif "what " in text and "does" in text and "temperature" in text:
                plant_name = ""
                for name in text_list:
                    if name in self.plant_data:
                        plant_name = name

                if plant_name:
                    self.get_temps(plant_name)

            elif "turn" in text and "lights" in text:
                on = True
                if "off" in text:
                    on = False;

                float_pattern = re.compile("\d+\.?\d*")
                time_delay_float = 0.0
                if "in " in text:
                    #Turn lights of in 10 minutes
                    if "hour" in text:
                        for t in text_list:
                            if float_pattern.match(t):
                                time_delay_float = time_delay_float + float(t)
                                break
                        if "half" in text:
                            self.set_delay_schedule(on, datetime.datetime.now() + datetime.timedelta(minutes = 30) + datetime.timedelta(hours = time_delay_float))
                        elif "quarter" in text:
                            self.set_delay_schedule(on, datetime.datetime.now() + datetime.timedelta(minutes = 15) + datetime.timedelta(hours = time_delay_float))
                        else:
                            self.set_delay_schedule(on, datetime.datetime.now() + datetime.time_delay_float(hours = time_delay_float))
                    elif "minute" in text:
                        for t in text_list:
                            if float_pattern.match(t):
                                time_delay_float = time_delay_float + float(t)
                                break
                        self.set_delay_schedule(on, datetime.datetime.now() + datetime.timedelta(minutes = time_delay_float))
                elif "every" in text or "daily" in text:
                    #turn on lights every day at 6:30
                    time_pattern = re.compile("\d+:\d+(pm)?(am)?")
                    lazy_time_pattern = re.compile("\d+(pm)?(am)?")
                    # e.g. 7 o clock
                    lazy_time = ("clock" in text) or ((("pm" in text) or ("am" in text)) and (":" not in text))
                    start_time = None
                    end_time = None
                    hours_int = 0
                    minutes_int = 0
                    for t in text_list:
                        if time_pattern.match(t):
                            hours_minutes_strings = t.split(":")
                            if "m" in t:
                                hours_int = int(hours_minutes_strings[0]) + (("p" in hours_minutes_strings[1])*12)
                                minutes_int = int(hours_minutes_strings[1][:-2])
                            else:
                                hours_int = int(hours_minutes_strings[0])
                                minutes_int = int(hours_minutes_strings[1])

                            if not start_time:
                                start_time = datetime.time(hours_int, minutes_int)
                            else:
                                end_time = datetime.time(hours_int, minutes_int)
                        elif lazy_time and lazy_time_pattern.match(t):
                            if "m" in t:
                                hours_int = int(t[:-2]) + (("p" in t)*12)
                            else:
                                hours_int = int(t)
                            if not start_time:
                                start_time = datetime.time(hours_int)
                            else:
                                end_time = datetime.time(hours_int)
                        elif float_pattern.match(t):
                            time_delay_float = float(t)
                            print("REGEX time_delay_float: ")
                            print(time_delay_float)

                    if not end_time:
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
                self.unhappy_plants = {"too cold": [], "too hot": [], "too dry": [], "too humid": []}
                self.display_status = True
                send_request()
            elif ("what" in text) or ("how" in text):
                for plant_name in text_list:
                    if plant_name in self.inside_tank:
                        for problem in ["too cold", "too hot", "too dry", "too humid"]:
                            if plant_name in self.unhappy_plants[problem]:
                                self.unhappy_plants[problem].remove(plant_name)
                        self.plant_of_interest = plant_name
                send_request()
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

    def get_temps(self, plant_name):
        info_list = get_text(self.plant_data[plant_name]["url"])
        temps_ind = after_sub_list_finder(info_list, ['', 'Propagation'])
        if temps_ind:
            for line in info_list[temps_ind:]:
                if line.lower() == "common pests and diseases" or line.lower() == "references":
                    break
                elif (("temperature" in line) or ("degrees" in line)) and len(line) > 40:
                    sentences = line.split(". ")
                    for s in sentences:
                        if ("1" in s or "2" in s or "3" in s) and (("temperature" in line) or ("degrees" in line)) and len(line) > 20:
                            self.send_msg(s)
                            return

    def get_disease(self, plant_name, keywords):
        #Do some fancy regex stuff here!
        pass




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
polling_always_on_thread.start()

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
