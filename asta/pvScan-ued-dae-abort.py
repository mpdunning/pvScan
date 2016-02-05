#!/usr/bin/env python
# For aborting scans.  
# mdunning 1/7/16

from epics import caget,caput,PV,Motor
from time import sleep
import datetime,math,os,sys,signal
from threading import Thread

args='PV_PREFIX'

def show_usage():
    "Prints usage"
    print 'Usage: %s %s' %(sys.argv[0], args)

if len(sys.argv) != 2:
    show_usage()
    sys.exit(1)

# PV prefix for pvScan IOC; should be passed as an argument
pvPrefix=sys.argv[1]

# Get PID PV
pidPV=PV(pvPrefix + ':PID')
pid=pidPV.get()

# PV for status message
msgpv=PV(pvPrefix + ':MSG')

# Motors to be stopped
motor1='ASTA:POLX01:AO:ABSMOV'
motor1Stop=PV('ASTA:POLX01:BO:ABORT')
motor2='MOTR:AS01:MC02:CH8:MOTOR'
motor2Stop=PV(motor2 + '.STOP')
motor3='MOTR:AS01:MC02:CH2:MOTOR'
motor3Stop=PV(motor3 + '.STOP')

# Shutters to be disabled (does not necessarily close them)
shutter1TTLDisablePv=PV('ASTA:LSC01:TTL:IN:DISABLE')
shutter2TTLDisablePv=PV('ASTA:LSC02:TTL:IN:DISABLE')
shutter3TTLDisablePv=PV('ASTA:LSC03:TTL:IN:DISABLE')

# Shutters to be inserted
laserShutter1Pv=PV('ASTA:LSC01:OC:CLOSE')
laserShutter2Pv=PV('ASTA:LSC02:OC:CLOSE')
laserShutter3Pv=PV('ASTA:LSC03:OC:CLOSE')

##################################################################################################################            
    
def abortRoutine():
    "This is the abort routine"
    msgpv.put('Aborting')
    # kill scan routine process
    os.kill(pid, signal.SIGKILL)
    # Disable shutters
    pvScan.uedShutterDisable(shutter1TTLDisablePv,shutter2TTLDisablePv,shutter3TTLDisablePv)
    sleep(0.5)
    # Close shutters
    laserShutter1Pv.put(0)
    laserShutter2Pv.put(0)  
    laserShutter3Pv.put(0)  
    # stop stages
    motor1Stop.put(1)
    motor2Stop.put(1)
    motor3Stop.put(1)
    print 'Aborted'
    msgpv.put('Aborted')


if __name__ == "__main__":
    "Do abort routine"
    abortRoutine()
        
##################################################################################################################
        

exit

