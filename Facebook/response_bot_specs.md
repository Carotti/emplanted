# Facebook Response Robot Specs
# Aim
Get some messages from Nippy and Fpgamy's robot (which is recording info from sensors).
Store the messages in some external file of some format. When the user sends a message asking what is the best plants for the temperature or what the temperature or humidity is in the tank respond with some human like response based on the info in the text file.

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

|           Features          |                                      How we do it                                     | Implemented? |
|-----------------------------|---------------------------------------------------------------------------------------|--------------|
| Need                        |                                                                                       |              |
| Extreme temperature warning |                                                                                       |              |
| What's wrong?               | Tell user which plants are outside ideal temp/humidity range                          |              |
| Setup instructions          |                                                                                       |              |
| Should                      |                                                                                       |              |
| Water/humidity control      | "Water my plant"                                                                      |              |
| Heater control              | "Increase temperature", "make it hotter"                                              |              |
| Suggestions                 | "Suggest me a plant"                                                                  |              |
| Could                       |                                                                                       |              |
| Seasonal suggestions        | "Now would be a great time to seed/fertilise/harvest XYZ"                             |              |
| Height warning              | "Your plants are ready to harvest!"                                                   |              |
| Water tank empty warning    | Weight sensor ?                                                                       |              |
| Common disease diagnosis    | "Spots on leaf" = Fungul infection, lower humidity, "Curled up leaves" = too dry etc. |              |
| What's up?                  | Sends emoji representing plants current state                                                                                      |              |
