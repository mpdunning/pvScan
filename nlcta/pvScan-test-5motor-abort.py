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
motor1='ESB:XPS1:m3'
motor1Stop=PV(motor1 + ':MOTR.STOP')
motor2='ESB:XPS1:m6'
motor2Stop=PV(motor2 + ':MOTR.STOP')
motor3='ESB:XPS1:m7'
motor3Stop=PV(motor3 + ':MOTR.STOP')

# Shutters to be inserted
#laserShutter1Pv=PV('')
#laserShutter2Pv=PV('')
#laserShutter3Pv=PV('')


##################################################################################################################            
    
def abortRoutine():
    "This is the abort routine"
    msgpv.put('Aborting')
    # kill scan routine process
    os.kill(pid, signal.SIGKILL)
    # block laser
    #laserShutter1Pv.put(0)
    #laserShutter2Pv.put(0)  
    #laserShutter3Pv.put(0)  
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

