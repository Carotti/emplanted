# Facebook Response Robot Specs
# Aim
Get some messages from Nippy and Fpgamy's robot (which is recording info from sensors).
Store the messages in some external file of some format. When the user sends a message asking what is the best plants for the temperature or what the temperature or humidity is in the tank respond with some human like response based on the info in the text file.

Fpgamy envisions this running on a separate internet connected machine not connected to the board, so the communication with the sensors are predominantly facebook based.

# Where to get started:
All the docs for the fbchat module are available here:
```
https://fbchat.readthedocs.io/en/master/
```
The module is not preinstalled so you need to use pip or something (if you need help, ask Fpgamy)

A good example to get used to how fbchat works is the Echobot code available here:
```
https://fbchat.readthedocs.io/en/master/examples.html
```

Remember never to echo messages when you are the author of the message otherwise you will have an infinite loop of never ending echos.

# How to test:
Log in to facebook using email 123composer@gmail.com and password emplanted-wifi. In the messages section I have started a conversation with myself (Thefish). Start the python script and send it messages from itself with some numbers on humidity and temperature. Your python needs to take (day/hourly?) averages and store them in some sort of text file. Then log into your own personal fb account and friend Thefish Tank on facebook and send it some messages asking it what temp/humidity/recommendations it has.