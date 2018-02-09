from umqtt.simple import MQTTClient
import network
from machine import Pin,I2C
import machine
import time
import json

boardConfig = {
    "network": {
        "ssid": "emplanted-wifi",
        "password": "emplanted#$_"
    },
    "mqtt": {
        "name": "emplanted-iot",
        "broker": "192.168.43.92",
        "topic": "esys/emplanted/",
        "subscriptions": [
            "lights",
            "request",
            "fan",
            "heat",
            "hum",
            "target",
            "sleep"
        ]
    },
    "th-sensor": {
        "scl": 5,
        "sda": 4,
        "freq": 100000,
        "slave-addr": 0x40,
        "htr-ctrl-value" : 0xF,
        "htr-write-cmd" : 0x51,
        "user-reg1" : 0xE6,
        "commands": {
            "measure-hum": 0xF5,
            "measure-temp": 0xF3
        }
    },
    "lights": {
        "pin": 14,
        "default-state": 0
    },
    "fan": {
        "pin": 13,
        "default-state": 1
    },
    "humidifer": {
        "pin": 15,
        "default-state": 1
    },
    "heater": {
        "pin": 12,
        "default-state": 1
    }
}

class THSensor:
    def __init__(self, config):
        self.i2cport = I2C(scl=Pin(config["scl"]), sda=Pin(config["sda"]), freq=config["freq"])
        self.slaveAddr = config["slave-addr"]
        self.commands = config["commands"]

    def rw(self, inAddress, outAddress):
        self.i2cport.writeto(self.slaveAddr, bytearray([inAddress]))
        time.sleep(0.1) # Hack, but important!
        data=self.i2cport.readfrom(outAddress, 2) # Read 2 bytes
        return data

    def getTemp(self):
        temp = int.from_bytes(self.rw(self.commands["measure-temp"], self.slaveAddr), 'big')
        temp_celsius = (175.72*temp/65536) - 46.85
        return temp_celsius

    def getHum(self):
        hum = int.from_bytes(self.rw(self.commands["measure-hum"], self.slaveAddr), 'big')
        hum_perc = (125*hum/65536) - 6
        return hum_perc

# ACTIVE LOW output
class Output:
    def __init__(self, config):
        self.pin = Pin(config["pin"], Pin.OUT)
        self.pin.value(config["default-state"])

    def enable(self):
        self.pin.value(0)

    def disable(self):
        self.pin.value(1)

class EmplantedBoard:
    def __init__(self, config):
        ap_if = network.WLAN(network.AP_IF)
        ap_if.active(False)

        sta_if = network.WLAN(network.STA_IF)

        sta_if.active(True)
        sta_if.connect(config["network"]["ssid"], config["network"]["password"])

        while not sta_if.isconnected():
            machine.idle()

        self.mqttClient = MQTTClient(config["mqtt"]["name"], config["mqtt"]["broker"])
        self.mqttTopic = config["mqtt"]["topic"]
        self.mqttClient.set_callback(self.mqttReceived)
        self.mqttClient.connect()
        for i in config["mqtt"]["subscriptions"]:
            self.mqttClient.subscribe(self.mqttTopic + i)

        self.thSensor = THSensor(config["th-sensor"])

        # Create each of the outputs
        self.outputs = {
            "lights" : Output(config["lights"]),
            "fan" : Output(config["fan"]),
            "hum" : Output(config["humidifer"]),
            "heat" : Output(config["heater"])
        }

        self.targetTemp = None
        self.targetHum = None

    # Given an output, determine if automatic mode should be disabled
    def disableAuto(self, output):
        if output != "lights":
            self.targetTemp = None
            self.targetHum = None

    def mqttReceivedOutput(self, o, msg):
        if msg == "ON":
            self.outputs[o].enable()
            self.disableAuto(o)
        elif msg == "OFF":
            self.outputs[o].disable()
            self.disableAuto(o)

    def mqttReceivedRequest(self, msg):
        requests = json.loads(msg)
        readings = {}
        for i in requests:
            reading = None
            if i == "temp":
                reading = self.thSensor.getTemp()
            elif i == "hum":
                reading = self.thSensor.getHum()
            readings[i] = reading
        self.mqttPublish("readings", json.dumps(readings))

    def mqttSetTarget(self, msg):
        tempHumTarget = json.loads(msg)
        self.targetTemp = float(tempHumTarget[0])
        self.targetHum = float(tempHumTarget[1])

    def monitorEnvironment(self):
        currentTemp = self.thSensor.getTemp()
        currentHum = self.thSensor.getHum()
        if (self.targetTemp != None) and (self.targetHum != None):
            if currentTemp < self.targetTemp:
                self.outputs["heat"].enable()
            else:
                self.outputs["heat"].disable()
            if currentHum < self.targetHum:
                self.outputs["hum"].enable()
            else:
                self.outputs["hum"].disable()
            if ((currentHum - self.targetHum) + (currentTemp - self.targetTemp)) > 0:
                self.outputs["fan"].enable()
            else:
                self.outputs["fan"].disable()

    def mqttReceived(self, topic, msg):
        topicStr = topic.decode("utf-8")
        msgStr = msg.decode("utf-8")

        if topicStr == (self.mqttTopic + "request"):
            self.mqttReceivedRequest(msgStr)
        elif topicStr == (self.mqttTopic + "target"):
            self.mqttSetTarget(msgStr)
        else:
            for o in self.outputs:
                if topicStr == (self.mqttTopic + o):
                    self.mqttReceivedOutput(o, msgStr)

    def mqttPublish(self, topic, payload):
        self.mqttClient.publish(self.mqttTopic + topic, bytes(payload, 'utf-8'))

    def mqttCheck(self):
        self.mqttClient.check_msg()

    def mqttWait(self):
        self.mqttClient.wait_msg()

board = EmplantedBoard(boardConfig)

while True:
    board.mqttCheck()
    board.monitorEnvironment()
    time.sleep(1)
