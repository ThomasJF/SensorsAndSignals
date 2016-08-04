from tkinter import *
import tkinter.font 
import sys
import queue
import csv
import threading
import time
import logging
import socket
import struct                         
# ****************************************************
# **************** Global Variables  *****************
# ****************************************************
WindowX=WindowY=0
Config={}
ACKtimeout={}                                            # Dict of pending ACKs
Sensors={}                                              # Dict of Sensor Objects with number as key
SensorKeys=[]                                           # Sorted Keys
SensorLabels={} 
SensorsIndex={}                                         # secondary key for above ip.channel, number
Signals={}                                              # Dict of Signal Objects with number as key
SignalKeys=[]                                           # Sorted Keys
SignalLabels={} 
SignalsIndex={}                                         # secondary key for above ip.channel, number 
SensorColors = {-2:"magenta2",-1:"light grey",0:"alice blue",1:"chartreuse"}
SignalColors = {-2:"magenta2",-1:"light grey",0:"SkyBlue1",1:"red",2:"chartreuse",3:"yellow",
                4:"ivory",5:"SkyBlue1",6:"SkyBlue1",7:"SkyBlue1",8:"SkyBlue1",9:"SkyBlue1",
                10:"SkyBlue1",11:"SkyBlue1",12:"SkyBlue1",13:"SkyBlue1",14:"SkyBlue1",15:"SkyBlue1",
                }
SensorUpdateQueue=queue.LifoQueue()                     #
SignalUpdateQueue=queue.LifoQueue()                     #
MSGQueue=queue.Queue()                                  # Queue for Text in Message Window
visibleFrame=''                                         # contains which frame is visible
StopThreads=0                                           # Treads will exit when this is nonzero
RocNet=0                                                # 0=not ready,, 1=Rready, 2=Initialized


# ****************************************************
# ********************* Classes **********************
# ****************************************************


class Signal():
    pass

class Sensor():   
    pass



'''
The following tooltip class is borrowed from Michael Lange <klappnase (at) freakmail (dot) de>
The ToolTip class provides a flexible tooltip widget for Tkinter; it is based on IDLE's ToolTip
module which unfortunately seems to be broken (at least the version I saw).
INITIALIZATION OPTIONS:
anchor :        where the text should be positioned inside the widget, must be on of "n", "s", "e", "w", "nw" and so on;
                default is "center"
bd :            borderwidth of the widget; default is 1 (NOTE: don't use "borderwidth" here)
bg :            background color to use for the widget; default is "lightyellow" (NOTE: don't use "background")
delay :         time in ms that it takes for the widget to appear on the screen when the mouse pointer has
                entered the parent widget; default is 1500
fg :            foreground (i.e. text) color to use; default is "black" (NOTE: don't use "foreground")
follow_mouse :  if set to 1 the tooltip will follow the mouse pointer instead of being displayed
                outside of the parent widget; this may be useful if you want to use tooltips for
                large widgets like listboxes or canvases; default is 0
font :          font to use for the widget; default is system specific
justify :       how multiple lines of text will be aligned, must be "left", "right" or "center"; default is "left"
padx :          extra space added to the left and right within the widget; default is 4
pady :          extra space above and below the text; default is 2
relief :        one of "flat", "ridge", "groove", "raised", "sunken" or "solid"; default is "solid"
state :         must be "normal" or "disabled"; if set to "disabled" the tooltip will not appear; default is "normal"
text :          the text that is displayed inside the widget
textvariable :  if set to an instance of Tkinter.StringVar() the variable's value will be used as text for the widget
width :         width of the widget; the default is 0, which means that "wraplength" will be used to limit the widgets width
wraplength :    limits the number of characters in each line; default is 150

WIDGET METHODS:
configure(**opts) : change one or more of the widget's options as described above; the changes will take effect the
                    next time the tooltip shows up; NOTE: follow_mouse cannot be changed after widget initialization

Other widget methods that might be useful if you want to subclass ToolTip:
enter() :           callback when the mouse pointer enters the parent widget
leave() :           called when the mouse pointer leaves the parent widget
motion() :          is called when the mouse pointer moves inside the parent widget if follow_mouse is set to 1 and the
                    tooltip has shown up to continually update the coordinates of the tooltip window
coords() :          calculates the screen coordinates of the tooltip window
create_contents() : creates the contents of the tooltip window (by default a Tkinter.Label)
'''

class ToolTip:
    def __init__(self, master, text='Your text here', delay=1500, **opts):
        self.master = master
        self._opts = {'anchor':'center', 'bd':1, 'bg':'lightyellow', 'delay':delay, 'fg':'black',\
                      'follow_mouse':0, 'font':None, 'justify':'left', 'padx':4, 'pady':2,\
                      'relief':'solid', 'state':'normal', 'text':text, 'textvariable':None,\
                      'width':0, 'wraplength':150}
        self.configure(**opts)
        self._tipwindow = None
        self._id = None
        self._id1 = self.master.bind("<Enter>", self.enter, '+')
        self._id2 = self.master.bind("<Leave>", self.leave, '+')
        self._id3 = self.master.bind("<ButtonPress>", self.leave, '+')
        self._follow_mouse = 0
        if self._opts['follow_mouse']:
            self._id4 = self.master.bind("<Motion>", self.motion, '+')
            self._follow_mouse = 1
    
    def configure(self, **opts):
        for key in opts:
            if self._opts.has_key(key):
                self._opts[key] = opts[key]
            else:
                KeyError = 'KeyError: Unknown option: "%s"' %key
                raise KeyError
    
    ##----these methods handle the callbacks on "<Enter>", "<Leave>" and "<Motion>"---------------##
    ##----events on the parent widget; override them if you want to change the widget's behavior--##
    
    def enter(self, event=None):
        self._schedule()
        
    def leave(self, event=None):
        self._unschedule()
        self._hide()
    
    def motion(self, event=None):
        if self._tipwindow and self._follow_mouse:
            x, y = self.coords()
            self._tipwindow.wm_geometry("+%d+%d" % (x, y))
    
    ##------the methods that do the work:---------------------------------------------------------##
    
    def _schedule(self):
        self._unschedule()
        if self._opts['state'] == 'disabled':
            return
        self._id = self.master.after(self._opts['delay'], self._show)

    def _unschedule(self):
        id = self._id
        self._id = None
        if id:
            self.master.after_cancel(id)

    def _show(self):
        if self._opts['state'] == 'disabled':
            self._unschedule()
            return
        if not self._tipwindow:
            self._tipwindow = tw = tkinter.Toplevel(self.master)
            # hide the window until we know the geometry
            tw.withdraw()
            tw.wm_overrideredirect(1)

            if tw.tk.call("tk", "windowingsystem") == 'aqua':
                tw.tk.call("::tk::unsupported::MacWindowStyle", "style", tw._w, "help", "none")

            self.create_contents()
            tw.update_idletasks()
            x, y = self.coords()
            tw.wm_geometry("+%d+%d" % (x, y))
            tw.deiconify()
    
    def _hide(self):
        tw = self._tipwindow
        self._tipwindow = None
        if tw:
            tw.destroy()
                
    ##----these methods might be overridden in derived classes:----------------------------------##
    
    def coords(self):
        # The tip window must be completely outside the master widget;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        # or we take care that the mouse pointer is always outside the tipwindow :-)
        tw = self._tipwindow
        twx, twy = tw.winfo_reqwidth(), tw.winfo_reqheight()
        w, h = tw.winfo_screenwidth(), tw.winfo_screenheight()
        # calculate the y coordinate:
        if self._follow_mouse:
            y = tw.winfo_pointery() + 20
            # make sure the tipwindow is never outside the screen:
            if y + twy > h:
                y = y - twy - 30
        else:
            y = self.master.winfo_rooty() + self.master.winfo_height() + 3
            if y + twy > h:
                y = self.master.winfo_rooty() - twy - 3
        # we can use the same x coord in both cases:
        x = tw.winfo_pointerx() - twx / 2
        if x < 0:
            x = 0
        elif x + twx > w:
            x = w - twx
        return x, y

    def create_contents(self):
        opts = self._opts.copy()
        #print("opts:"+str(opts))
        for opt in ('delay', 'follow_mouse', 'state'):
            del opts[opt]
        #print("text:'" +opts['text'] +"'")    
        label = tkinter.Label(self._tipwindow, **opts)
        label.pack()

# ****************************************************
# ******************** Functions   *******************
# ****************************************************

def ReadConfig():
    global WindowX,WindowY,Config
    Config = {}
    with open('./router.cfg', 'r') as f:
        for line in f:
            line = line.rstrip()                        #removes trailing whitespace and '\n' chars

            if "=" not in line: continue                #skips blanks and comments w/o =
            if line.startswith("#"): continue           #skips comments which contain =

            k, v = line.split("=", 1)
            Config[k] = v
    #print(Config)
    temp=Config['window'].split("x", 1)
    WindowX=int(temp[0])
    WindowY=int(temp[1])
    Config['enable_timeout'].lower()
    Config['enable_livecheck'].lower()
    #print(Config)

def ReadSensors():
    global Sensors,SensorKeys,SensorsIndex,Config
    if Config['sensors']:
        try:
            fp = open(Config['sensors'])
        except:
            DisplayMessage('Error Reading Sensor Config File. Path:"' + Config['sensors']+'"',True)
            return
        rdr = csv.DictReader(filter(lambda row: row[0]!='#', fp))
        for row in rdr:
            #print(row)
            if row['ip']+'.'+row['channel'] in SensorsIndex.keys():
                DisplayMessage('Sensor Config: Duplicate Sensor Definition: IP.Channel: ' +row['ip']+'.'+row['channel'],True)
            elif row['no'].zfill(3) in Sensors.keys():
                DisplayMessage('Sensor Config: Duplicate Rocrail Sensor Number:' + row['no'],True)
            else:
                x=Sensor()
                x.SensorNumber=row['no'].zfill(3)
                x.SensorIP=row['ip']
                x.SensorChannel=row['channel']
                x.SensorName=row['name']
                x.SensorComment=row['comment']
                x.SensorState=-1                                # -1=unknown -2=Ping exeeded, 0=off, 1=On
                x.SensorPingCount=1                             # start with 1 ping
                Sensors[x.SensorNumber]=x
                SensorsIndex[row['ip']+'.'+row['channel']]=x.SensorNumber
        fp.close()
        SensorKeys = sorted(Sensors.keys())
        DisplayMessage('Sensor-Count = ' + str(len(Sensors)),False)
    else:
        Sensors={}
        SensorsIndex={}
        DisplayMessage('********** No Sensors ***********',False)
    pass    

def ReadSignals():
    global Signals,SignalKeys,SignalsIndex,Config
    if Config['signals']:
        try:
            fp = open(Config['signals'])
        except:
            DisplayMessage('Error Reading Signal Config File. Path:"' + Config['Signals']+'"',True)
            return
        rdr = csv.DictReader(filter(lambda row: row[0]!='#', fp))
        for row in rdr:
            #print(row)
            if row['ip']+'.'+row['channel'] in SignalsIndex.keys():
                DisplayMessage('Signal Config: Duplicate Signal Definition: IP.Channel: ' +row['ip']+'.'+row['channel'],True)
            elif row['no'].zfill(3) in Signals.keys():
                DisplayMessage('Signal Config: Duplicate Rocrail Signal Number:' + row['no'],True)
            else:
                x=Signal()
                x.SignalNumber=row['no'].zfill(3)
                x.SignalIP=row['ip']
                x.SignalChannel=row['channel']
                x.SignalName=row['name']
                x.SignalComment=row['comment']
                x.SignalState=-1                                # -1=unknown -2=Ping exeeded, 0=off, 1=On
                x.SignalPingCount=1                             # start with 1 ping
                Signals[x.SignalNumber]=x
                SignalsIndex[row['ip']+'.'+row['channel']]=x.SignalNumber
                #print(x.SignalNumber,x.SignalIP,x.SignalChannel)
        fp.close()
        SignalKeys = sorted(Signals.keys())
        DisplayMessage('Signal-Count = ' + str(len(Signals)),False)
    else:
        Signals={}
        SignalsIndex={}
        DisplayMessage('********** No Signals ***********',False)
    pass    
#
# ***********************************************************************************
# **************************  Sensor/Signal Thread  *********************************
# ***********************************************************************************
# Receive packets from all sensor boars on port config['transmitter_port'] (1963)
#
#
def SensorThread():
    global RocNet,Config,visibleFrame,StopThreads,Sensors,SensorIndex,Signals,SignalIndex,SensorKeys
    buf=32
    data=''
    host=''
    port=int(Config['transmitter_port'])
    addr = (host,port)
    SensorSocketSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    SensorSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    SensorSocket.bind((host,port))
# RocNet
    RocSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    RocHost = (Config['rocnet_group'],int(Config['rocnet_port']))
    SensorSocketSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
# Init Complete. Wait for data...
    time.sleep(5) #wait 5 secs before start checking for changes
    while True:
        SensorSocket.settimeout(2)   # set timeout to 2 sec to make sure we go throgh loop at least every 2 sec
        data=''
        try:
            data,addr = SensorSocket.recvfrom(buf)
            if  data:
                #print(data,addr)
                x=struct.unpack('5sxxxhxxl',data)
                # if answer to signal query or state change
                if x[0]==b"PROX1" or x[0]==b"PROX0":
                    try:
                        no=SensorsIndex[str(addr[0]) +"." + str(x[1])]
                        Sensors[no].SensorPingCount=0                   # Sensor is alive --> reset Ping Count
                    except:
                        no=""
                        DisplayMessage('Unknown Sensor! IP:' + str(addr[0])+'  Channel:' +str(x[1]),True)                
                    if no:
                        if x[0]==b"PROX1":
                            #print('IP: #' +str(addr[0]) + '#  CMD: ' + STR(x[0])+ '  Channel: ' + str(x[1]) + '  ACK: ' + str(x[2]))
                            if Sensors[no].SensorState < 1:
                                Sensors[no].SensorState=1
                                RocNetTransmit(RocSock,RocHost,no,10)
                                SensorRespond(SensorSocketSend,x,no,addr)
                                if visibleFrame=="Sensors": 
                                    SensorLabels[no].config(bg=SensorColors[1])
                        else:
                            #print('   IP: #' +str(addr[0]) + '#  CMD: ' + str(x[0]) + '  Channel: ' + str(x[1]) + '  ACK: ' + str(x[2]))
                            if Sensors[no].SensorState != 0:
                                Sensors[no].SensorState=0
                                RocNetTransmit(RocSock,RocHost,no,10)
                                SensorRespond(SensorSocketSend,x,no,addr)
                                if visibleFrame=="Sensors": 
                                    SensorLabels[no].config(bg=SensorColors[0])
                   
                # if answer to signal query
                elif x[0]==b"SGVAL":
                    try:
                        no=SignalsIndex[str(addr[0]) +"." + str(x[1])]
                        Signals[no].SignalPingCount=0                   # Signal is alive --> reset Ping Count
                    except:
                        no=""
                        DisplayMessage('Unknown Signal! IP:' + str(addr[0])+'  Channel:' +str(x[1]),True)                
                    if no:
                        #print('   IP: #' +str(addr[0]) + '#  CMD: ' + str(x[0]) + '  Channel: ' + str(x[1]) + '  ACK: ' + str(x[2]))
                        s=x[2]
                        if s<0 or s>15:
                            s=-2
                        #print("no=" + no + "   s=" + str(s) + "  Color:" + SignalColors[s])    
                        Signals[no].SignalState=s
                        if visibleFrame=="Signals": 
                             SignalLabels[no].config(bg=SignalColors[s])                     
                else:
                    pass
        except Exception as e:
            if str(e) != 'timed out':
                raise
            pass
        if StopThreads:
            SensorSocket.close()
            SensorSocketSend.close()
            #print('Exit SensorThread')
            break
    pass # end while


''' Sensor respond to ACK request '''
def SensorRespond(SendSock,x,SNumber,addr):                         # x= decoded received packet, SNumber= sensor number
    global Sensors
    SensorUpdateQueue.put(SNumber)
    if x[2]:
        m=struct.pack('5sxxxhxxl',b'ACKCH',x[1],x[2])
        SendSock.sendto(m, addr)
        #print(m,addr)
    pass

''' Sensor send State chnage to Rocrail '''
def RocNetTransmit(RSock,RHost,SNumber,tc):                          # x= decoded received packet, SNumber= sensor number
    global RocNet,Sensors,Config,ACKtimeout
    # build Packet to Rocnet 00 00 01 00 02 08 01 04 00 00 xx nn    xx=0/1 on/off nn=Sesnor Number
    if RocNet>1:
        p=b'\x00\x00\x01\x00' 
        p+=bytes([int(Config['rocnet_node'])])
        p+=b'\x08\x01\x04\00\00'
        p+=bytes([Sensors[SNumber].SensorState])
        p+=bytes([int(SNumber)]) #p SNumber
        #print(" ".join(format(c,'02x') for c in p))      
        try:
            RSock.sendto(p,RHost)
            if Config['enable_timeout']== 'true':                               # if ACK timeout for Rocrail is configured
                ACKtimeout[SNumber]=(tc,int(round(time.time()*1000))+1000)      #timeout= 10 or less times 1 s
        except:
            print('Error sending to RocNet')
        pass
    else:
        if RocNet<1:                                                # Unkown state of RocNet --> send dummy packet
            RocNet=1
            #print('send dummy packet')   
            p=b'\x00\x00\x01\x00' #\x01\x01'
            p+=bytes([int(Config['rocnet_node'])])
            p+=b'\x08\x01\x04\00\00\00\00'
            RSock.sendto(p,RHost)
    pass


# ***********************************************************************************
# ******************************  Rockrail Thread  *********************************
# ***********************************************************************************
def RockrailThread():
    global RocNet,Config,ACKtimeout,visibleFrame,StopThreads,Sensors,SensorIndex,Signals,SignalIndex
    buf=32
    host=''
    port=int(Config['transmitter_port'])
    addr = (host,port)
    SensorSocketSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# RocNet
    RocSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    RocHost = ('',int(Config['rocnet_port']))
    RocSock.bind(('',int(Config['rocnet_port'])))
    RocGroup = socket.inet_aton(Config['rocnet_group'])
    mreq = struct.pack('4sL', RocGroup, socket.INADDR_ANY)
    RocSock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    while True:
        RocSock.settimeout(1)   # set timeout to 1 sec to make sure we go throgh loop at least every 2 sec
        data=''
        # set 2 seconds socket read timeout here
        try:
            (data, address) = RocSock.recvfrom(64)
            print(" ".join(format(c,'02x') for c in data)) 
            if  RocNet<2:                                                       # if this is first response from RocNet
                if data[3:]==b'\x00\x01\x03\x0a\02\01\00':                      # if this is an ACk for Sensor 0
                    RocNet=2
                    for x in SensorKeys:                                        # synch all online Sensors
                        if Sensors[x].SensorState>=0:
                            RocNetTransmit(RocSock,(Config['rocnet_group'],int(Config['rocnet_port'])),x,10)
                            if Config['enable_timeout']== 'true':                        #if ACK Timeout is configured
                                ACKtimeout[x]=(10,int(round(time.time()*1000))+1000)    #timeout= 10 times 1s
                            time.sleep(0.01)
            else:
                if data[2]==int(Config['rocnet_node']):
                    #
                    # Case Request "Set Signal" (RocNet Output Code 9)
                    #
                    if data[5:10]==b'\x09\x01\x05\x01\x06':                         # Signal = Rocrail Output Type Makro   
                        no=str(data[12]).zfill(3)
                        if data[11]>=0 and data[11]<16:
                            m=struct.pack('5sxxxhxxl',b'SGSET',int(Signals[no].SignalChannel),data[11])
                            addr=(Signals[no].SignalIP,int(Config['transmitter_port']))
                            SensorSocketSend.sendto(m,addr)
                            m=struct.pack('5sxxxhxxl',b'QRYSG',int(Signals[no].SignalChannel),0) #request a state update
                            SensorSocketSend.sendto(m, addr)
                    #
                    #case Sensor ACK
                    #
                    elif data[5:7]==b'\x03\x0a':
                        key=str(data[9]).zfill(3)
                        if key in ACKtimeout:
                            del ACKtimeout[str(data[9]).zfill(3)]                   # Remove this sensor from Timeout List
                    #
                    # case Play Sound
                    #
                    # in "actions" Type: "Sound"  Parameter "xxxplaynnnn"
                    # Play Sound nnnn on signal board xxx. nnnn="0000" ...."0254". 0000 means Stop playing.
                    # !!! Use the Signals Table for adressing Sound !!!
                    elif data[5:7]==b'\x0b\x01':
                            play=data[15:19]
                            try:
                                n=int(play)
                            except:
                                n=-1
                            if n>=0 and n<255:
                                m=struct.pack('5sxxxhxxl',b'PLAYS',0,n)             #(command channel data)
                                key=data[8:11].decode("utf-8")
                                if key in Signals:   
                                    addr=(Signals[key].SignalIP,int(Config['transmitter_port']))
                                    SensorSocketSend.sendto(m, addr)
                                    print('submit ' + str(m) + '   to ' + str(addr))
                                else:
                                    DisplayMessage('Play Sound: Signal Number ' + key +' not found: ',True)
                    else:
                        pass
                pass #if Data[2] 
            pass #if RocNet
            data=''
        except Exception as e:
            if str(e) != 'timed out':
                raise
            else:
                if RocNet<2:            # if timeout because no connection to RocNet --> send another dummy packet                  
                    time.sleep(1)
                    p=b'\x00\x00\x01\x00' 
                    p+=bytes([int(Config['rocnet_node'])])
                    p+=b'\x08\x01\x04\00\00\00\00'
                    RocSock.sendto(p,(Config['rocnet_group'],int(Config['rocnet_port'])))                 
            pass
        #Handle ACK timeouts 
        if RocNet>1 and Config['enable_timeout']== 'true':
            t=int(round(time.time()*1000))      # current time in ms
            while True:
                try:
                    for x in ACKtimeout:
                        if ACKtimeout[x][0]>1:
                            if ACKtimeout[x][1]<t:       # if timeout for this
                                ACKtimeout[x]=(ACKtimeout[x][0]-1,t+1000)
                                RocNetTransmit(RocSock,(Config['rocnet_group'],int(Config['rocnet_port'])),x,ACKtimeout[x][0])
                                print('Timeout ' + x + str(ACKtimeout[x]))
                            pass
                        else:
                            if x in ACKtimeout:
                                del ACKtimeout[x]               # remove from list if more than 10 timeouts
                                DisplayMessage('Rocrail Timeout for Sensor ' + x,True)
                except:                             
                    continue
                break
        pass # if rocnet   
        if StopThreads:
            break #while
    pass
    #print('Exit RockrailThread')
    RocSock.close()
    SensorSocketSend.close()

# ***********************************************************************************
# **********************************  Ping Thread  **********************************
# ***********************************************************************************
def PingThread():
    global visibleFrame,StopThreads,Sensors,SensorKeys,Signals,SignalKeys
    SensorSocketSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    StartupCount=0
    while Config['enable_livecheck'] == 'true' or StartupCount<5:
        StartupCount+=1
        for x in SensorKeys:
            m=struct.pack('5sxxxhxxl',b'QRYCH',int(Sensors[x].SensorChannel),0)
            addr=(Sensors[x].SensorIP,int(Config['transmitter_port']))
            SensorSocketSend.sendto(m, addr)
            if Sensors[x].SensorPingCount < 4:
                Sensors[x].SensorPingCount+=1
            else:
                if Sensors[x].SensorState > -2:
                    Sensors[x].SensorState = -2
                    DisplayMessage("No Response from Sensor "+x+", IP:"+Sensors[x].SensorIP+", Ch:" +Sensors[x].SensorChannel,True)
                    if visibleFrame=="Sensors": 
                        SensorLabels[x].config(bg=SensorColors[-2])              
            if StopThreads:
                break   
            time.sleep(0.1) # pause 100 ms 
        for x in SignalKeys:
            m=struct.pack('5sxxxhxxl',b'QRYSG',int(Signals[x].SignalChannel),0)
            addr=(Signals[x].SignalIP,int(Config['transmitter_port']))
            SensorSocketSend.sendto(m, addr)
            if Signals[x].SignalPingCount < 4:
                Signals[x].SignalPingCount+=1
            else:
                if Signals[x].SignalState > -2:
                    Signals[x].SignalState = -2
                    DisplayMessage("No Response from Signal "+x+", IP:"+Signals[x].SignalIP+", Ch:" +Signals[x].SignalChannel,True)
                    if visibleFrame=="Signals": 
                        SignalLabels[x].config(bg=SignalColors[-2])
            if StopThreads:
                break   
            time.sleep(0.1) # pause 100 ms
        pass # for x
        if StopThreads:
            break   
    pass #while
    SensorSocketSend.close()
    #print('Exit PingThread')
            


# ***********************************************************************************
# **********************************    Gui Stuff   *********************************
# ***********************************************************************************
def ResetButtonColors():
    buttonSensors.config(bg='silver')
    buttonSignals.config(bg='silver')
    buttonInfo.config(bg='silver')
    if buttonMSG.cget('bg')!= 'red':
        buttonMSG.config(bg='silver')


def Button_Click_MSG():
    global visibleFrame
    root.title('Messages')
    visibleFrame='MSG'
    ResetButtonColors()
    buttonMSG.config(bg='white')
    frameMSG.lift()
    
def Button_Click_Sensors():
    global visibleFrame,SensorColors,Sensors,SensorKeys
    root.title('Sensors')
    visibleFrame='Sensors'
    ResetButtonColors()
    buttonSensors.config(bg='white')
    frameSensors.lift()
    for x in SensorKeys:
        SensorLabels[x].config(bg=SensorColors[Sensors[x].SensorState])
    
def Button_Click_Signals():
    global visibleFrame,Colors
    root.title('Signals')
    visibleFrame='Signals'
    ResetButtonColors()
    buttonSignals.config(bg='white')
    frameSignals.lift()
    for x in SignalKeys:
        SignalLabels[x].config(bg=SignalColors[Signals[x].SignalState])
        
def Button_Click_Info():
    global visibleFrame,Colors
    root.title('Info')
    visibleFrame='Info'
    ResetButtonColors()
    buttonInfo.config(bg='white')
    frameInfo.lift()

    
def Button_Click_SetSignal():
    global Signals,Config
    SensorSocketSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sig=entrySignal.get()
        st=int(entryState.get())
        if st>-3 and st<16:
            no=sig.zfill(3)
            #print(no,Signals[no].SignalName,Signals[no].SignalIP,Signals[no].SignalChannel)
            m=struct.pack('5sxxxhxxl',b'SGSET',int(Signals[no].SignalChannel),st)
            addr=(Signals[no].SignalIP,int(Config['transmitter_port']))
            SensorSocketSend.sendto(m,addr)
            Signals[no].SignalState=st
    except:
        pass
    SensorSocketSend.close()
    

def StopAll():
    global StopThreads
    StopThreads=1
    if T_Rockrail.is_alive():
        T_Rockrail.join()
    if T_Sensor.is_alive():    
        T_Sensor.join()
    if T_Ping.is_alive():  
        T_Ping.join()
    root.destroy()
    print('************** EXIT *************')

def DisplayMessage(msg,ErrFlag):
    if ErrFlag:
        text.insert('1.0',time.strftime("%H:%M:%S") + ' Err: ' + msg + '\n')
    else:   
        text.insert('1.0',time.strftime("%H:%M:%S") + '      ' + msg + '\n')
    if ErrFlag:
        buttonMSG.config(bg='red')
    if int(text.index(END).split('.',1)[0]) > 300:
        text.delete('200.0',END)
    pass
    
# **************************************************************************************
# **********************************    Screen Repaint  ********************************
# **************************************************************************************
def UpdateScreen():                                 # calls itself every 100 ms to update screen data
    global visibleFrame
    if visibleFrame=='Sensors':
        while not SensorUpdateQueue.empty():
            x=SensorUpdateQueue.get()    
            #print('Sensor',x)
    if visibleFrame=='Signals':
        while not SignalUpdateQueue.empty():
            y=SignalUpdateQueue.get()    
            #print('Signal',y)
    root.after(100,UpdateScreen)

# *****************************************************************************************************
# *****************************************************************************************************
# **********************************    Start Program now   *******************************************
# *****************************************************************************************************
# *****************************************************************************************************
print("start")
RocNet=0                # RocNet State: 0=after Progstart, 1=Sending a Check Packet every 2 Secs, 2= RocNet OK
# **********************************    Gui Stuff   *********************************                 
root = Tk()
root.title('Sensors')

rootw=root.winfo_screenwidth()
rooth=root.winfo_screenheight()
# create frames
frameMSG = Frame(master=root)
frameMSG.pack(side=LEFT,fill=BOTH, expand='YES',pady=20)

frameSensors = Frame(master=root,bg='white')
frameSensors.place(x=0, y=20, width=rootw, height=rooth-20)

frameSignals = Frame(master=root,bg='white')
frameSignals.place(x=0, y=20, width=rootw, height=rooth-20)

frameInfo = Frame(master=root,bg='white')
frameInfo.place(x=0, y=20, width=rootw, height=rooth-20)

# Buttons for Frams-switching
buttonMSG = Button(master = root, text = 'Messages', bg='silver',command = Button_Click_MSG)
buttonMSG.place(x=0, y=0, width=100, height=20)
buttonSensors = Button(master = root, text = 'Sensors', bg='white', command = Button_Click_Sensors)
buttonSensors.place(x=100, y=0, width=100, height=20)
buttonSignals = Button(master = root, text = 'Signals', bg='silver', command = Button_Click_Signals)
buttonSignals.place(x=200, y=0, width=100, height=20)
buttonInfo = Button(master = root, text = 'Info', bg='silver', command = Button_Click_Info)
buttonInfo.place(x=300, y=0, width=100, height=20)

# **********************************   now start   *********************************

SensorUpdateQueue.put(-1)
frameSensors.lift()
visibleFrame='Sensors'

scrollbar = Scrollbar(frameMSG)
scrollbar.pack(side=RIGHT, fill=Y)
text = Text(frameMSG, wrap=WORD, yscrollcommand=scrollbar.set)
text.pack(side=LEFT,fill=BOTH, expand='YES')
scrollbar.config(command=text.yview)

DisplayMessage('Read Config File.........',False)
ReadConfig()
DisplayMessage('Read Sensors Config File........',False)
ReadSensors()
DisplayMessage('Read Signals Config File........',False)
ReadSignals()
DisplayMessage('Starting Threads ......',False)
T_Rockrail=threading.Thread(target=RockrailThread)
T_Sensor=threading.Thread(target=SensorThread)
T_Ping=threading.Thread(target=PingThread)
T_Rockrail.start() 
if len(Sensors)>0:
    T_Sensor.start()
    
# ******** Define Layout Metrics *********
sensorFont = tkinter.font.Font(family="Helvetica", size=Config['SensorGridFontSize'])
signalFont = tkinter.font.Font(family="Helvetica", size=Config['SignalGridFontSize'])
(sensorw,sensorh) = (7*sensorFont.measure("0X"),sensorFont.metrics("linespace"))
(signalw,signalh) = (7*signalFont.measure("0X"),signalFont.metrics("linespace"))

if WindowX==0:
    root.attributes('-zoomed', True)                            # Full Screen if 0x0
    SensorsIPL=int(rootw/(sensorw+int(Config['SensorGridPadX'])))
    SignalsIPL=int(rootw/(signalw+int(Config['SignalGridPadX'])))
else:
    root.geometry("%dx%d+10+10" % (WindowX, WindowY))
    SensorsIPL=int(WindowX/(sensorw+int(Config['SensorGridPadX'])))
    SignalsIPL=int(WindowX/(signalw+int(Config['SignalGridPadX'])))

# **** Sensors Layout *****
i=0
for x in SensorKeys:
    #print(str(i)+' item: *' + x + '* ' + Sensors[x].SensorName)
    r=int(i/SensorsIPL)
    c=int(i % SensorsIPL) 
    SensorLabels[x]=Label(frameSensors, text=x+" " +Sensors[x].SensorName[:12],bg=SensorColors[-1],font=("Helvetica", Config['SensorGridFontSize']),width="14")
    SensorLabels[x].grid(row=r,column=c,sticky='W',padx=Config['SensorGridPadX'],pady=Config['SensorGridPadY'],ipadx=2,ipady=2)
    ToolTip(SensorLabels[x], text="Sensor: " + x +  "\n\n" + Sensors[x].SensorComment)
    i+=1

# **** Signals Layout *****
i=0
for x in SignalKeys:
    #print(str(i)+' item: *' + x + '* ' + Sensors[x].SensorName)
    r=int(i/SignalsIPL)
    c=int(i % SignalsIPL) 
    SignalLabels[x]=Label(frameSignals, text=x+" " +Signals[x].SignalName[:12],bg=SignalColors[-1],font=("Helvetica", Config['SignalGridFontSize']),width="14")
    SignalLabels[x].grid(row=r,column=c,sticky='W',padx=Config['SignalGridPadX'],pady=Config['SignalGridPadY'],ipadx=2,ipady=2)
    ToolTip(SignalLabels[x], text="Signal: " + x +  "\n\n" + Signals[x].SignalComment)
    i+=1

# **** Info Layout *****
labelColor = Label(master = frameInfo, text = 'Colors for Signal State:',bg='white')
labelColor.place(x=5, y=20)
for i in range(-2,0):
    Label(master = frameInfo, text = '  ' + str(i).zfill(2)+"  ", bg=SignalColors[i]).place(x=180+50*(i+2), y=20)
for i in range(0,8):
    Label(master = frameInfo, text = '  ' + str(i).zfill(2)+"  ", bg=SignalColors[i]).place(x=180+50*i, y=50)
for i in range(8,16):
    Label(master = frameInfo, text = '  ' + str(i).zfill(2)+"  ", bg=SignalColors[i]).place(x=180+50*(i-8), y=80)
Label(master = frameInfo, text = 'Colors for Sensor State:',bg='white').place(x=5, y=140)
for i in range(-2,2):
    Label(master = frameInfo, text = '  ' + str(i).zfill(2)+"  ", bg=SensorColors[i]).place(x=180+50*(i+2), y=140)
Label(master = frameInfo, text = 'Send Signal Set Command:',bg='white').place(x=5, y=220)
Label(master = frameInfo, text = 'Signal Number:',bg='white').place(x=5, y=250)
Label(master = frameInfo, text = 'Signal State (0..15):',bg='white').place(x=150, y=250)
entrySignal=Entry(frameInfo)
entrySignal.place(x=110, y=250,width=30)
entryState=Entry(frameInfo)
entryState.place(x=285, y=250,width=30)
buttonSetSignal = Button(master = frameInfo, text = 'Set Signal', bg='silver', command = Button_Click_SetSignal).place(x=350, y=250, width=100, height=20)

# ******** Start Paint Screens *********
UpdateScreen()
time.sleep(0.5)
# ******** Signal Synch Initial Query (Ping) *********
SensorSocketSend = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for x in SensorKeys:
    m=struct.pack('5sxxxhxxl',b'QRYCH',int(Sensors[x].SensorChannel),0)
    addr=(Sensors[x].SensorIP,int(Config['transmitter_port']))
    SensorSocketSend.sendto(m, addr)
    time.sleep(0.01)
for x in SignalKeys:
    m=struct.pack('5sxxxhxxl',b'QRYSG',int(Signals[x].SignalChannel),0)
    addr=(Signals[x].SignalIP,int(Config['transmitter_port']))
    SensorSocketSend.sendto(m, addr)
    time.sleep(0.01)    
SensorSocketSend.close()
T_Ping.start()
DisplayMessage('Start Pinging Signals and Sensors.',False)
DisplayMessage('Start Complete.',False)
root.protocol("WM_DELETE_WINDOW",StopAll)                       # End Programm request
root.mainloop()


