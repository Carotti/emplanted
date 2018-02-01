readData sets up data read for humidity and temperature sensor. We have two separate functions for reading temperature and reading humidity.

Humidity and temperature is converted according to the formula given in the datasheet.

We had issues with reading and writing right after each other, but sleeping in between the two operations solved the problem.

Register 0x40 is the slaver register.
Command 0xF3 is measure temp, hold no master mode.
Command 0xE3 is measure temp, hold master mode.
Command 0xF5 is measure humidity, hold master mode.
Command 0xE5 is measure humidity, hold no master mode.
