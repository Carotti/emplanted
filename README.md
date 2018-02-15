# emplanted
Just a bunch of kids trying to grow plants

TODO:
1. get fb client to rate health out of 10
2. get basic functionality in hw sorted

|           Features          |                               How we do it                              | Implemented? |
|-----------------------------|-------------------------------------------------------------------------|--------------|
| Need                        |                                                                         |              |
| light cycle times           | Use MQTT to get time every hour, Use relays to control light connection | Yup          |
| extreme temperature warning | Use temperature sensor                                                  | Yup          |
| facebook chat interface     | Get Magson's Python thing running on uPython                            | Yup          |
| Should                      |                                                                         |              |
| Water control               | Use valve to get water out of tank.                                     | Replaced     |
| Heater control              | Buy a heater                                                            | Yup          |
| Humidity control            | Humidifier                                                              | Done         |
| Could                       |                                                                         |              |
| Height warning              | IR beam break sensor                                                    | Nope         |
| Colour Temperature          | Use 2 relays to turn lights on/off                                      | Nope         |
| Polling ability via chat    | Magson can do this "easy"                                               | EASY         |
| Plant suggestions           | Have a dictionary and try to match it with avg temps etc                | Yup          |
| Water tank empty warning    | Humidity level stays same after spraying?                               | Yup          |
