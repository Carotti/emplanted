import time
from umqtt.simple import MQTTClient
import network

# Publish test messages e.g. with:
# mosquitto_pub -t foo_topic -m hello

# Received messages from subscriptions will be delivered to this callback
def sub_cb(topic, msg):
    print((topic, msg))

def main(server="192.168.43.92"):
    print("Hello")

    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(False)

    sta_if = network.WLAN(network.STA_IF)

    if not sta_if.isconnected():
        sta_if.active(True)
        sta_if.connect("emplanted-wifi", "emplanted#$_")

    c = MQTTClient("umqtt_client", server)
    c.set_callback(sub_cb)
    c.connect()
    c.subscribe("#")

    c.wait_msg()

    c.disconnect()

if __name__ == "__main__":
    main()
