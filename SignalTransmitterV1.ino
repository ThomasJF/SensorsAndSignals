// PINs: SDA 2, SCL 14, VCNL4020-INT 13
/*
// configure wifi
const char* ssid = "somme ssid";
const char* password = "some password";
//
Interfaces:
Sensors:      2 x I2C + active low interrupt  (I2C need pullup resistors on the sensor side, for the interrupt there is one on the card
MP3:          TX, GND, 3.3V on 3 solder points
Signal:       either 4 pin plug with +3.3 and 3 Bits ord solder points witg 3.3v and 4 Bits. Acive low. External resistors.
              Max. current accoring to ESP8266 i/O limits.             
Programming:  6 pin plug with 2 x GND, TX, RX, RTS, DTR

LED:          If configured 1 sec blinker, 2  secs on if proximity detected, fast blink when Boot / factory reset, 
              Signal and LED blinking whenn access through webbrowser

Factory reset: Sets the WLAN to DHCP and some of the parameters to a default value. 

Proxy sensor: For the VCNL3020 the interrupts are not used. Instead the ready bit is checked in every loop. if a value is available,
              it is read and a new conversion is startet.
              the actual proxy value is the avarage of the last 8 conversions. 
              If a proxy state change has occured there will be now other state chnage accepted for a some time (hysteresis). This time
              is normally 1 sec and is specified in source code.
              Timeout: If a sensor does not deliver a value after more than 500ms (if it has been sucessfully initialized) the 
              sensor might hang. In this case the board is rebooted. If the sensor comes online ---> OK, otherwise the board continues 
              with 1 sensor. Before the reboot a UDP-message TMOUT,channel,0 is send out. 

Webinterface: IP-Address-Change requires reboot. Other parameters are apllied on the fly.
              Server IP
              Some parameters are only reconfigurable via source code, such as UID/Pass for WLAN, Port for UDP, trace on/off, etc.
              If any of the play-Sound values are !=-1 (255), trace is disabled after next boot (because the serial TX-Pin is shared
              between the MP3-Player and the Serial conection (Serial to USB converter) to the PC).
              
WLAN:         Send and listen ports are both 1963.
              aend and receive packet layout:
              xx xx xx xx xx 00 00 00 nn nn 00 00 ll ll ll ll
              xx=chr[5] op-code, nn = Integer OP-Code Value, ll = long packet id (set to millis() when bilding packet)
              So far there is no field defined for RFID data.
              
OP-Codes:     Send:
              PROX1,  CH,   0/ID        Proxy Value Channel CH is "ON", ID=miliseconds since boot
              PROX0,  CH,   0/ID        Proxy Value Channel CH is "OFF", ID=miliseconds since boot
              SGVAL,  CH,   VAL         Signal ist set to VAL (4 Bit) (channel allways 0)   
              TMOUT   CH,   0           Sensor CH timeout. Board will reboot now!
               
              Receive:
              SGSET,  n/a,  VAL         Set Signal to VAL. Mapping table in the source code.
              ACKCH,  CH,   ID          Receive an ACK for a PROX-package send. ID is the ID sent with the last pack.
              QRYSG,  CH,   n/a         Request to transmit the current Signal Value (sourc code: variable Signal).
              QRYCH,  CH,   n/a         Request to transmit the current Proxy-State for channel CH (answer with PROX1/0).
              BOOT!,  n/a,  n/a         REBOOT 
              (Value for SGSET must be a long int with the lowest value byte in front: Val=3 --> "03 00 00 00"
              
ACK/Timeout:  If set to nonzero value in the Webbrwser, an ACK message with the correct value for ID is expected.
              Otherwise after the timeout value the package is resent with a new ID-value.   
              If ACCtimeout is set to 0, ACKCH messages are ignored and the ID sent ist set to 0. 
              ACKtimeout values are in millliseconds. Values below 100ms seconds are replaced by 100 ms.    
              
MP3 player:   Mini DFPlayer DFR0299 (with a YX5300 MP3 chip).
              no checksum byte are required (they are omitted). Commads used:
              Play Sound NN : 7E FF 06 03 00 00 NN EF   (e.g. 0x01 fpr sound 0001.mp3 on root directory)
              Sound Volume VV: 7E FF 06 06 00 00 VV EF  (Volume 0 to 30)
              Volume is defined in source code and set after boot time.
              Sounds must be stored on the root directory in the SD-Card. 0001.mp3.
              Webinterface "Channel 2 Play=2" means "Play Sound 0002.mp3 when proxy state changes from OFF to ON". 
              255 (-1) means play nothing. 0 means Stop Play current sound.
              Volume on Webfrontend mut be betweeen 1 and 30.
*/
// The following is required for LIGHT_SLEEP_T delay mode
extern "C" {
#include "user_interface.h"
}
// PINs: SDA 2, SCL 14, INT 
#include <ESP8266WiFi.h>
#include <WiFiUDP.h>
#include <ESP8266WebServer.h>
#include <Wire.h>
#include <Ticker.h>
#include <EEPROM.h>

#define release "Release 0.9 &nbsp&nbsp&nbsp 2016-07-01" 
#define Min_ACK_Timeout 100             // min 100 ms ACK Timeout
#define Hysteresis 1000                 // tim (ms) before a new proxy state change can occur after the last state change
#define VCNL3020_ADDRESS 0x13           // I2C Address of the Sensor Chip
#define DefaultThreshold 0x956          // default threshold values
#define MUX_ADDRESS 0x70                // I2C Address of the MUX PCA9540B, 0x04 --> channel 0, 0x05 --> channel 1
#define Expander_ADDRESS 0x41           // I2C Address of the I/O Expander PCA9536
#define LEDadr 12                       // GPIO for LEDadr

//
//    ----------------> DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBU <-------------------------- 
byte trace=1;                                                           // Serial trace Mmessages right from start
//
Ticker ticker10ms;
byte factory=0;                                                         // factory reset mode if value != 0
byte LED=0;                                                             // LED indicator on or off
byte Signal=0;                                                          // Signal State                           
byte SignalMap[]={15,1,2,4,15,15,15,15,15,15,15,15,15,15,15,15};        // Signal Map 3 Aspect SBB Zwergsignal
//config Sensors
String SensorDescription[]={"No Sensor", "Proximity Sensor", "Something else"};
byte   SensorType[]={0,0};
byte   Channel=0;

//config Proximity
unsigned int  threshold[]={0,0};                                         // threshold values    
unsigned int  proximityAvg[]={0,0};                                      // Current Proximity Average Value
unsigned int  sensorTimeout[]={0,0};                                     //
unsigned int  timeout[]={0,0};                                           // time to wait before resend packet
unsigned int  LastChange[]={0,0};  
unsigned long ACK_ID[]={0,0};                                            // filled with millis at time of packet send
byte          power[]={15,15};                                           // Infared LED Current
byte          play[]={0,0};                                              // Play MP3 Sound No when train detected
byte          proximityAvgCount[]={0,0};                                 // Initial number of measurments before ready
byte          proximityState[]={0,0};                                    // Current Proximity State
byte          OldproximityState[]={0,0};

//MP3 Player
//char volume[]={0x7E ,0xFF ,0x06 ,0x06 ,0x00 ,0x00 ,0x15 ,0xEF};       // Set Volumen. 0x15 = Volume (0 - 30)
char volumeH[]={0x7E ,0xFF ,0x06 ,0x06 ,0x00 ,0x00};                    // Set Volumen. 0x15 = Volume (0 - 30)
char volumeF=0xEF;
char Volume=0x10;                                                       // Sound Volume
char playSound[]={0x7E ,0xFF ,0x06 ,0x03 ,0x00 ,0x00 ,0x02 ,0xEF};      // Play Sound. 0x02 = Sound Number
char stopPlay[]={0x7E ,0xFF ,0x06 ,0x16 ,0x00 ,0x00 ,0x00 ,0xEF};      // Stop Playback   
//Diverse
int mscount=0;
int LEDtimer=0;

// ********************************************************************************************************************
// ****************************************   Web and UDP Definitions and Pages ***************************************
// ********************************************************************************************************************
//
ESP8266WebServer server(80);
IPAddress ip;   
IPAddress gateway;
IPAddress subnet; 
IPAddress raspi;    
char IpString[15];
int  WebAccess=0;
// UDP-Stuff
WiFiUDP Udp;
byte packetBuffer[64];                                                  // buffer to hold incoming and outgoing packets
typedef struct {
    char          UDPcmd[6];
    int           UDPcmdVal;
    unsigned long UDPdata;}
UDPpacket;                          // HEX(53 47 53 45 54 00 00 00 02 01 00 00 03 01 00 00)  ----> "SIGSET", 258, 259
                                    // e.g. long UDPdata HEX(15 CD 5B 07) = DEC(123456789)
UDPpacket UDPmessage;  
unsigned int localPort = 1963;                                          // UDB listen port
unsigned int ACK_Timeout=0;
//String UDPcmd="";
//byte   UDPcmdVal=0;
//
// ****************************************************
// *********************  ROOT  ***********************
// ****************************************************
void handleRoot() {
   char temp[420];
   snprintf ( temp, 400,\
"<HTML><HEAD><TITLE>The Site</TITLE></HEAD>\
<FRAMESET rows='410,*' framespacing='0' border='0' frameborder='1'>\
      <FRAME NAME='topLeft' SRC='/main.htm' scrolling='no' noresize>\
      <FRAMESET cols='50%,50%' framespacing='0' border='0' frameborder='1'>\
           <FRAME NAME='bottomLeft' SRC='/sensor.htm?sensor=1'>\
           <FRAME NAME='bottomRight' SRC='/sensor.htm?sensor=2'>\
      </FRAMESET>\
 </FRAMESET>\
</HTML>");
  server.send(200, "text/html", temp);
  WebAccess=9000;
}
// ****************************************************
// ******************  Main (Form)  *******************
// ****************************************************
void handleMain() {
  int sec = millis() / 1000;
  int min = sec / 60;
  int hr = min / 60;
  String temp="";
  int V;
  //Serial.print( "Form Submit received. Argumentcount =" );
  //Serial.println(server.args());
  if (server.args() > 0 ) {
  //  ****************** Save Values ****************""""""""
      writeExpander(0x01, 0x00);
      //for ( uint8_t i = 0; i < server.args(); i++ ) {
      //    Serial.println (server.arg(i));
      //}
      if(server.arg(12)=="1"){LED=1;}else{LED=0;} 
      V= server.arg(11).toInt();
      if(V>30){V=30;};
      if(V<1){V=1;};
      Volume=(char)V;
      if(play[0]<255 or play[1]<255){                                                      // if any play defined
        Serial.write(volumeH,6),Serial.write(Volume),Serial.write(volumeF);
      }
      ACK_Timeout=server.arg(10).toInt();
      if(ACK_Timeout != 0 and ACK_Timeout < 100){ACK_Timeout=Min_ACK_Timeout;}           //if ACK-Timeout != 0 and below limit
      threshold[0]=server.arg(4).toInt(),threshold[1]=server.arg(7).toInt(); 
      power[0]=(server.arg(5).toInt())/10,power[1]=(server.arg(8).toInt())/10;  
      play[0]=server.arg(6).toInt(),play[1]=server.arg(9).toInt(); 
      //Serial.print("ch 0: "),Serial.print( play[0]);
      //Serial.print("  ch 1: "),Serial.println(play[1]);
      raspi.fromString(server.arg(3));
      subnet.fromString(server.arg(2));
      gateway.fromString(server.arg(1));
      ip.fromString(server.arg(0));
      EEPROM.begin(64);
      EEPROM.write(0,0),EEPROM.write(1,LED);
      // EEPROM 2 = Signal
      EEPROM.put(4,Volume);
      EEPROM.put(8,ACK_Timeout);
      EEPROM.put(12,power[0]),EEPROM.put(13,power[1]);
      EEPROM.put(14,play[0]),EEPROM.put(15,play[1]);
      EEPROM.put(16,threshold[0]),EEPROM.put(20,threshold[1]); 
      EEPROM.put(24,raspi),EEPROM.put(32,subnet),EEPROM.put(40,gateway),EEPROM.put(48,ip);
      delay(100);
      EEPROM.commit();
      delay(100);
      EEPROM.end();
      WebAccess=3000;         
  }
  //  ****************** Display Values ****************""""""""
  temp+="<html><head><title>Input Form</title></head><body><font size='6'>Sensor/Signal Transmitter</font> &nbsp&nbsp&nbsp<font size='2'>";
  temp+=release;
  temp+="<form action='/main.htm' method='POST'>";
  //
  temp+="<BR><table><tr><td><b>Network Config</B></td></tr>";
  sprintf(IpString, "%d.%d.%d.%d", ip[0], ip[1], ip[2], ip[3]);
  temp+="<tr><td>My IP Address: </td><td><input type='text' name='IP' value='",temp+=IpString,temp+="'></td></tr>";
  sprintf(IpString, "%d.%d.%d.%d", gateway[0], gateway[1], gateway[2], gateway[3]);
  temp+="<tr><td>Gateway Address: </td><td><input type='text' name='Gateway' value='",temp+=IpString,temp+="'></td></tr>";
  sprintf(IpString, "%d.%d.%d.%d", subnet[0], subnet[1], subnet[2], subnet[3]);
  temp+="<tr><td>Network Mask: </td><td><input type='text' name='Mask' value='",temp+=IpString,temp+="'></td></tr>";
  sprintf(IpString, "%d.%d.%d.%d", raspi[0], raspi[1], raspi[2], raspi[3]);
  temp+="<tr><td>Server Address: </td><td><input type='text' name='RASPI' value='",temp+=IpString,temp+="'></td></tr>";
  temp+="<tr><td><BR><b>Channel/Proximity Properties:</B></td></tr>";
  temp+="<tr><td>Channel 1: &nbsp&nbsp&nbsp&nbsp&nbsp&nbspThreshold: </td><td><input type='text' name='Threshold1' value='",  temp+=String(threshold[0]),  temp+="'></td>";
  temp+="<td>&nbsp&nbsp&nbsp&nbspLED mA (max 200): </td><td><input type='text' name='Power1' value='", temp+=String(10*power[0]),  temp+="'></td>";
  temp+="<td>&nbsp&nbsp&nbsp&nbspPlay Sound: </td><td><input type='text' name='Play1' value='",  temp+=String(play[0]),  temp+="'></td></tr>";
  temp+="<tr><td>Channel 2: &nbsp&nbsp&nbsp&nbsp&nbsp&nbspThreshold: </td><td><input type='text' name='Threshold2' value='",  temp+=String(threshold[1]), temp+="'></td>";
  temp+="<td>&nbsp&nbsp&nbsp&nbspLED mA (max 200): </td><td><input type='text' name='Power2' value='",  temp+=String(10*power[1]),  temp+="'></td>"; 
  temp+="<td>&nbsp&nbsp&nbsp&nbspPlay Sound: </td><td><input type='text' name='Play2' value='",  temp+=String(play[1]),  temp+="'></td></tr>";
  temp+="<tr><td>&nbsp</td></tr><tr><td>ACK Timeout ms: </td><td><input type='text' name='Timeout' value='",  temp+=String(ACK_Timeout),  temp+="'></td>";
  temp+="<td>&nbsp&nbsp(0=no ACK required)</td><td></td><td>&nbsp&nbsp&nbsp&nbspVolume:</td><td><input type='text' name='Volume' value='",  temp+=String((int)Volume),  temp+="'></td></tr>";  
  temp+="<tr><td>&nbsp</td></tr><tr><td><input type='checkbox' name='LEDenable' value='1' ";
  if(LED){temp+=" checked";}
  temp+="> Enable LED Blinker</td></tr></table>";
  //
  temp+="<p><input type='submit' value='Store Values'></form></body></html>";
  server.send(200, "text/html", temp);
}

// ****************************************************
// ********************  Sensors  *********************
// ****************************************************
void handleSensor() {
   int sec = millis() / 1000;
   int min = sec / 60;
   int hr = min / 60;
   int SensorNumber,ST;
   char tm[9];
   String temp="";
   String sensor;  
   sensor=server.arg(0);
   SensorNumber=sensor.toInt();
   ST=SensorType[SensorNumber-1],sensor=SensorDescription[ST];
   temp+="<html><head><title>Sensors</title><meta http-equiv=refresh content='2', URL='sensor.htm?sensor=",temp+=String(SensorNumber),temp+="'>";
   temp+="</head><body><font size='5'>Channel ",temp+=SensorNumber,temp+=": ",temp+=sensor ,temp+="</font><p>";
   switch (ST) {                                              // sensor specific code
     case 1:
       temp+="Current Proximity State: <b><span style='background-color:";
       if(proximityState[SensorNumber-1]){temp+="red'>&nbsp&nbsp&nbspON";}else{temp+="silver'>&nbsp&nbsp&nbspOFF";};
       temp+="&nbsp&nbsp&nbsp</span></B><p>Current Proximity Value: " + String(proximityAvg[SensorNumber-1]);
       break;
    case 2:
       //do something when var equals 2
       break;
     default: 
        // do nothing
     break;
   }
   snprintf ( tm, 9,"%02d:%02d:%02d",hr, min % 60, sec % 60);
   temp+="<p><P>Uptime: " + String(tm) + "</p></body></html>";
   server.send(200, "text/html", temp);
}

// ********************************************************************************************************************
// **************************************************   Subroutine ****************************************************
// ********************************************************************************************************************
//
// ****************************************************
// ********************* Reboot ***********************
// ****************************************************
void REBOOT(){
    if(trace){Writetrace(0,1,"REBOOT");};
    int count=0;
    pinMode(LEDadr, OUTPUT);
    while (count<80) {
        digitalWrite(LEDadr, LOW);  
        delay(20);
        digitalWrite(LEDadr, HIGH);  
        delay(80);
        count++;
    }
    ESP.restart();                                                      // reboot now  
}

// ****************************************************
// *********************** trace **********************
// ****************************************************
void Writetrace(byte MSGtype, byte CRLF ,String MSG) {
    if(CRLF){Serial.println();};
    if(MSGtype){Serial.print("------> Error: ");};
    Serial.print(MSG);
}

// ****************************************************
// ********************* Timer ************************
// ****************************************************
void clock1ms(int state) {
  mscount++;
  if(timeout[0]>0){timeout[0]--;}
  if(timeout[1]>0){timeout[1]--;}
  if(LastChange[0]>0){LastChange[0]--;}
  if(LastChange[1]>0){LastChange[1]--;}
  if(SensorType[0]!=0){sensorTimeout[0]++;}
  if(SensorType[1]!=0){sensorTimeout[1]++;}
  if(LEDtimer>0){
      LEDtimer--;
      if(LED){digitalWrite(LEDadr, LOW);}; 
  }else{
      if(WebAccess>0){WebAccess--;}else{writeExpander(0x01, SignalMap[Signal]);}
      if(mscount>980)
      {
        //digitalWrite(12, !digitalRead(12));   // Toggle LEDadr
        if(LED)digitalWrite(LEDadr, LOW);
        if(WebAccess>0){writeExpander(0x01, 0x00);}
      }
      if(mscount>999)
        {
        if(LED)digitalWrite(LEDadr, HIGH);
        if(WebAccess>0){writeExpander(0x01, 0x0F);}
      }
  }    
      if(mscount>999){mscount=0;;}
}

// ****************************************************
// ******** Wrtie to GPIO Expander Chip ***************
// ****************************************************
void writeExpander(byte address, byte data){
  Wire.beginTransmission(Expander_ADDRESS);
  Wire.write(address);
  Wire.write(data);
  Wire.endTransmission();
}

// **********************************************************
// ******** read single byte from Sensor Chip ***************
// **********************************************************
byte readSensorByte(byte chip,byte address){
  // readByte(Chip Address, byte address) reads a single byte of data from address
  int count=0;
  byte data=0;
  Wire.beginTransmission(chip);
  Wire.write(address);
  Wire.endTransmission();
  Wire.requestFrom(chip, 1);
  while(!Wire.available() and count<1000){count++;delay(1);};
  if(count<1000){data = Wire.read();}
  return data;
}

// **********************************************************
// ******** write single byte to Sensor Chip ***************
// **********************************************************
void writeSensorByte(byte chip,byte address, byte data){
  // writeVCNLByte(address, data) writes a single byte of data to address
  Wire.beginTransmission(chip);
  Wire.write(address);
  Wire.write(data);
  Wire.endTransmission();
}

// **********************************************************
// ********** Initialize VCNL3020 / 4020 Chip ***************
// **********************************************************
byte InitializeVCNL3020(int CH){
  int count=0;
  writeSensorByte(VCNL3020_ADDRESS,0x80, 0x00);                     // no periodic measurments
  writeSensorByte(VCNL3020_ADDRESS,0x83, power[CH]);                // sets IR current in steps of 10mA 0-200mA --> e.g. 15=150mA
  writeSensorByte(VCNL3020_ADDRESS,0x89, 0x00);                     // No Interrupts
  writeSensorByte(VCNL3020_ADDRESS,0x8E, 0);                        // Int Stat
  writeSensorByte(VCNL3020_ADDRESS,0x8f,0x01);                      // recommended by Vishay 
  writeSensorByte(VCNL3020_ADDRESS,0x80,0x08);                      //  start first conversion
  while(!(readSensorByte(VCNL3020_ADDRESS,0x80)&0x20) and count<1000){count++;delay(1);}; // Wait for the proximity data ready bit to be set
  return 1;  
}

// **********************************************************
// ************* Read VCNL3020 Proximity Data ***************
// **********************************************************
unsigned int readProximity(){
    unsigned int data = readSensorByte(VCNL3020_ADDRESS,0x87) << 8;
    data |= readSensorByte(VCNL3020_ADDRESS,0x88);
    return data;
}

// ***********************************************************************
// ******** Detect and Initialize Sensor on Curent Channel ***************
// ***********************************************************************
byte InitialzeSensor(int SensorChannel){
  byte val;
  //try VCNL3020 Chip
  val=readSensorByte(VCNL3020_ADDRESS,0x81);
  if(val==0x21){                                                      // VCNL Product ID = 0x21 
     if(InitializeVCNL3020(SensorChannel)){
       proximityAvg[SensorChannel]=readProximity();                   // Read first Value
       writeSensorByte(VCNL3020_ADDRESS,0x80,0x08);                   //  start next conversion                                            // Start next Reading for this chip
       proximityAvgCount[SensorChannel]=32;
       return 1;};                                                    // if VCNL Chip Found and Initialzed
  }   
  //try to find other Sensors
  // ........
  // Return 0 if no sensor found
  return 0;
}

// ***********************************************************************
// ***************** Send UDP Packet to Server port 1963 *****************
// ***********************************************************************
void SendUDP(String OPcode,int CHNL, long AT){
    OPcode.toCharArray(UDPmessage.UDPcmd, 6) ;
    UDPmessage.UDPcmdVal=CHNL;
    if(ACK_Timeout != 0 or OPcode=="SGVAL"){
          ACK_ID[CHNL]=AT;
          UDPmessage.UDPdata=AT;
    }else{
          ACK_ID[CHNL]=0;                                 // Send package ID = 0 if not timeout defined
          UDPmessage.UDPdata=0;
    }
    Udp.beginPacket(raspi, 1963);
    Udp.write((char *) &UDPmessage, sizeof UDPmessage);
    Udp.endPacket(); 
}


// ********************************************************************************************************************************
// ********************************************************************************************************************************
// *****************************************************      S E T U P     *******************************************************
// ********************************************************************************************************************************
// ********************************************************************************************************************************

void setup() {
    EEPROM.begin(64);
    pinMode(LEDadr, OUTPUT);
    digitalWrite(LEDadr, HIGH);
    delay(10);
    pinMode(LEDadr, INPUT);                                             // Factory Reset if LEDadr-PIN connected to Ground
    if(digitalRead(LEDadr)==0){                                         // (Samll cable from ground to LEDadr-PIN on side of ESP-03)
      EEPROM.write(0,255);    
      delay(100);
      EEPROM.commit();
      REBOOT();
    }
// EEPROM or Default Values    
    factory= EEPROM.read(0);                                            // factory reset mode (EEPROM 0 != 0)
    if(factory){
        LED=1,EEPROM.write(1,1);
        Volume=15,EEPROM.put(4,Volume);
        ACK_Timeout=0;
        EEPROM.put(8,ACK_Timeout);
        power[0]=15,power[1]=15,play[0]=2551,play[1]=255;
        EEPROM.put(12,power[0]),EEPROM.put(13,power[1]);
        EEPROM.put(14,play[0]),EEPROM.put(15,play[1]);   
        threshold[0]=DefaultThreshold, threshold[1]=DefaultThreshold;
        EEPROM.put(16,threshold[0]),EEPROM.put(20,threshold[1]);
        Signal=1;EEPROM.write(2,Signal);                               //Signal Default Value   
        delay(10);
        EEPROM.commit();              
    }else{
        LED=EEPROM.read(1);                                               // LED indicator on or off
        EEPROM.get(4,Volume);
        EEPROM.get(8,ACK_Timeout);
        EEPROM.get(12,power[0]),EEPROM.get(13,power[1]);
        EEPROM.get(14,play[0]),EEPROM.get(15,play[1]);   
        EEPROM.get(16,threshold[0]),EEPROM.get(20,threshold[1]);           // Threshold Values
        Signal=EEPROM.read(2);                                           // Signal State
        EEPROM.get(24,raspi),EEPROM.get(32,subnet),EEPROM.get(40,gateway),EEPROM.get(48,ip);   // IP Config
    }
    proximityAvg[0]=threshold[0],proximityAvg[1]=threshold[1];            // initial average 
    if(trace)delay(5000);
    pinMode(LEDadr, OUTPUT);
    digitalWrite(LEDadr, LOW);                                            // LEDadr ON
    Serial.begin(9600);                                                   // Serial's used to trace and print data
    if(play[0]<255 or play[1]<255){
      trace=0;                                                            // no trace if MP3 Player active...
      Serial.write(volumeH,6),Serial.write(Volume),Serial.write(volumeF); 
    }
    Wire.begin(2,14);                                                     // initialize I2C stuff (SDA, SCL)
    writeExpander(0x01, 0x00);                                            //Expander set to 1
    writeExpander(0x03, 0x00);                                            //Expander set direction output
    if(trace){Writetrace(0,1,"Hello.");};
//Connect to WiFi
    int tries=0;  
    if(trace){Writetrace(0,1,"Try to connect to WLAN ...");};
    delay(500);
    if(!factory){    
        WiFi.config(ip, gateway, subnet); 
        delay(100);
    }
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
    delay(600);
    if(trace){Writetrace(0,0,".");};
    tries++;
    if (tries > 30){ 
      if(trace){Writetrace(1,1,"No WLAN Connection");};
      REBOOT();      
    } 
  }
  if(trace){Writetrace(0,0," connected");};
  server.on("/", handleRoot);
  server.on("/main.htm",handleMain);
  server.on("/sensor.htm",handleSensor);
  server.begin();                                                     // Start Webserver
  if(trace){Writetrace(0,1,"Webserver started. IP: ");};  
  if(trace){Serial.println(WiFi.localIP());};  
  if(factory){
      ip=WiFi.localIP();
      gateway=WiFi.gatewayIP();
      subnet=WiFi.subnetMask();  
      raspi.fromString("0.0.0.0");     
  }       
  Udp.begin(localPort);
  if(trace){Writetrace(0,1,"UDP Server Started. local Port: ");Writetrace(0,0,String(localPort));};                           
  ticker10ms.attach_ms(1, clock1ms, 0);                               // Start Ticker: every 1 ms, call clock1ms(0) 
  // Inititalze Sensors
  Wire.beginTransmission(MUX_ADDRESS), Wire.write(0x04), Wire.endTransmission();  // Select Channel 0
  SensorType[0]=InitialzeSensor(0);
  Wire.beginTransmission(MUX_ADDRESS), Wire.write(0x05), Wire.endTransmission();  // Select Channel 1
  SensorType[1]=InitialzeSensor(1);
  EEPROM.end();                                                       // Release RAM copy of EEPROM
  writeExpander(0x01, Signal);                                        // Restore Sinal State
  digitalWrite(LEDadr, HIGH);                                         // LED OFF      
}
// ********************************************************************************************************************************
// ********************************************************************************************************************************
// *******************************************************      L o o p          **************************************************
// ********************************************************************************************************************************
// ********************************************************************************************************************************

void loop() {
    for(Channel=0;Channel<3;Channel++){
        Wire.beginTransmission(MUX_ADDRESS), Wire.write(0x04+Channel), Wire.endTransmission();  // Select Channel
        switch (SensorType[Channel]) {                                              // sensor specific code
        case 1:
            if(sensorTimeout[Channel]>500){                                         // if more than 500ms no proxy data
                SendUDP("TMOUT",Channel,0);  
                REBOOT();  
            }
            
            if(readSensorByte(VCNL3020_ADDRESS,0x80)&0x20){                         // if new value available
                sensorTimeout[Channel]=0;                                        // reset timeout
                proximityAvg[Channel]=(7*proximityAvg[Channel]+readProximity())/8;  // update average
                writeSensorByte(VCNL3020_ADDRESS,0x80,0x08);                        //  start next conversion  
                if(proximityAvgCount[Channel]>0){proximityAvgCount[Channel]--;}     // decrement initialization     
                if(!LastChange[Channel]){
                    OldproximityState[Channel]=proximityState[Channel];                 // store previous state            
                    if(!proximityAvgCount[Channel] and proximityAvg[Channel]>=threshold[Channel]){
                        proximityState[Channel]=1;
                        //Serial.print(OldproximityState[Channel]),Serial.print("/"),Serial.println(OldproximityState[Channel]);
                        if(OldproximityState[Channel]==0){
                            LastChange[Channel]=Hysteresis;                               
                            SendUDP("PROX1",Channel,millis());
                            timeout[Channel]=ACK_Timeout;
                            if(play[Channel]<255){
                                if(play[Channel]==0){
                                  Serial.write(stopPlay,8);
                                }
                                else{
                                  playSound[6]=play[Channel];
                                  Serial.write(playSound,8);
                                }
                            }                   
                            if(trace){Writetrace(0,1,"Trigger Channel "),Writetrace(0,0,String(Channel));};
                            LEDtimer=1000;
                        }           
                   }else{
                        proximityState[Channel]=0;   
                        if(OldproximityState[Channel]==1){
                            SendUDP("PROX0",Channel,millis());
                            timeout[Channel]=ACK_Timeout;
                        }           
                    } 
                }             
            }
        case 2:
          //do something when var equals 2
          break;
        default: 
          // do nothing
        break;     
        } // end switch
    
      // ****************** Check Ack Timeout an resend if necessary **********************
        if(timeout[Channel] and timeout[Channel]<10){
            if(proximityState[Channel]){SendUDP("PROX1",Channel,millis());}else{SendUDP("PROX0",Channel,millis());} // resend packet
            timeout[Channel]=ACK_Timeout;      
          
        }
       
    } // end for channel
    yield();
    // ******************************** Check UDP Receive ********************************
    // UDP receive: SGSET x d, ACKCH 0 d, ACKCH 1 d, QRYSG x d, QRYCH 0 d, QRYCH 1 d, PLAYS x d
    // UDP send:    SGVAL x d, PROX1 0 d, PROX1 1 d, PROX0 0 2, PROX0 1 d
    int noBytes = Udp.parsePacket();
    UDPmessage.UDPcmd[0]=32,UDPmessage.UDPcmdVal=0,UDPmessage.UDPdata=0;
    if ( noBytes ) {              // if there is UDP-Data
       Udp.read((char *) &UDPmessage, sizeof UDPmessage);
       String cmd=String(UDPmessage.UDPcmd);
       if(trace){Serial.println(),Serial.print("*"),Serial.print(String(UDPmessage.UDPcmd)),Serial.print("*/"),Serial.print(String(UDPmessage.UDPcmdVal)),Serial.print("/"),Serial.println(String(UDPmessage.UDPdata));};
       /*
       String test="SGVAL";
       test.toCharArray(UDPmessage.UDPcmd, 6) ;
       UDPmessage.UDPcmdVal=258;
       UDPmessage.UDPdata=259;
       Udp.beginPacket(Udp.remoteIP(), Udp.remotePort());
       Udp.write((char *) &UDPmessage, sizeof UDPmessage);
       Udp.endPacket(); 
       */       
        //decode packet
        if(cmd=="ACKCH"){
            //Serial.print("Channel: "),Serial.print(timeout[0]),Serial.print(" / "),Serial.println(timeout[1]);
            //Serial.print("Channel: "),Serial.print(UDPmessage.UDPcmdVal),Serial.print(" Received: ");
            //Serial.print(UDPmessage.UDPdata),Serial.print(" / Stored: "),Serial.println(ACK_ID[UDPmessage.UDPcmdVal]);
            if(UDPmessage.UDPcmdVal==0 or UDPmessage.UDPcmdVal==1){
                if(ACK_ID[UDPmessage.UDPcmdVal]==UDPmessage.UDPdata){timeout[UDPmessage.UDPcmdVal]=0;}  // if ACK matches sent packet
            }      
        }
        else if(cmd=="QRYCH"){
            if(UDPmessage.UDPcmdVal==0 or UDPmessage.UDPcmdVal==1){
                if(proximityState[UDPmessage.UDPcmdVal]){SendUDP("PROX1",UDPmessage.UDPcmdVal,0);}else{SendUDP("PROX0",UDPmessage.UDPcmdVal,0);} // answer query
            }
        }
        else if(cmd=="QRYSG"){
            SendUDP("SGVAL",0,long(Signal));         // Send Signal State            
        }
        else if(cmd=="SGSET"){
            Signal=byte(UDPmessage.UDPdata);     
            EEPROM.begin(64);
            EEPROM.write(2,Signal);
            writeExpander(0x01, SignalMap[Signal]);  
            //Serial.print("Signal Value:"),Serial.print(Signal),Serial.print("  MapValue: "),Serial.println(SignalMap[Signal]);
            EEPROM.commit();
            EEPROM.end(); 
        }
        else if(cmd=="PLAYS"){ 
            int s=byte(UDPmessage.UDPdata); 
            if(s<255){
              if(s==0){
                Serial.write(stopPlay,8);
              }
              else{
                playSound[6]=s;
                Serial.write(playSound,8);
              }
            }
        }  
        else if(cmd=="BOOT!"){
            REBOOT();               
        }
        else{ // do nothing  
        }
    }
    yield();
    server.handleClient();                                                          // Handle Webbrowser Requests
    yield();
}
