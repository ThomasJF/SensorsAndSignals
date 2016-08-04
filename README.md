# SensorsAndSignals
A system with signals and infrared sensors for Rocrail

this is the Python 3 code that routes commands to and from the sensor boards and to an from Rocrail using RocNet.
The values for all the seonsors and signals are displayed on the Rasperry screen.
Most of the parameters a are defined in 3 config files: router.cfg, signals.cfg and sensors.cfg. Parameters are explained in the config files.
There are 4 threads:
- main:  that contains the TKINTER-loop and a 100ms screen refresh routine
- Sensor: Listens for UDP packets from sensor boards on defined port (1963) and sends packets to Rocrail
- Rocrail: Listens for RocNet packets on 224.0.0.1 port 4321 and sends packets to Sensor boards
- Ping: Checks every sensor and signal for availablity (1 address per 100 ms). If a sensor or signal does not respond after a few   polls, it's display is turned purple.

The signal and rockrail treads send changes to a display update queue that is read by the display update routine.
Only the currently displed frame gets updated.

Opcodes to an from Sensor boards according to Doc in the Arduino branch.
Sound: If a MP3 Player is connected to a board it is adressed the same way as the respective signal.
A sound can either be played by specifying the choosen sound to be activeated when a sensor gets active (0 means stop current playing, -1 (255) means do nothing.). In Rocrail a "Action" can be defined the playes a sound. Action Type= Sound and only the address is relevant. The Player-(Signal-)-Number and the sound number are defined in the parameter field:
"sssplaynnnn" sss=signal number (allways 3 digits) nnnn=sound number (allways 4 digits. The sound files are stored in the player directly in the root directory with the names 0001.mp3 ..... 0254.mp3. So 014play0123 means play sound 0123.mp3 on board 14.
play0000 means stop playing.

Opcodes to an from Rocnet:


