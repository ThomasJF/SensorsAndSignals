# SensorsAndSignals
A system with signals and infrared sensors for Rocrail

this is the Python 3 code the routes command to an from the sensor boards to an from Rocrail usinf RocNet.
The values for all the seonsors and signals are displayed on the Rasperry screen.
There are 4 threads:
- main:  that contains the TKINTER-loop and a 100ms screen refresh routine
- Sensor: Listens for UDP packets from sensor boards on defined port (1963) and sends packets to Rocrail
- Rocrail: Listens for RocNet packets on 224.0.0.1 port 4321 and sends packets to Sensor boards
- Ping: Checks every sensor and signal for availablity (1 address per 100 ms). If a sensor or signal does not respond after a few   polls, it's display is turned purple.

The signal and rockrail treads send changes to a display update queue that is read by the display update routine.
Only the currently displed frame gets updated.

Opcodes to an from Sensor boards according to Doc in the Arduino branch.
Opcodes to an from Rocnet:


