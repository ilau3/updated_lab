from PyQt5 import QtGui, QtCore
from pylablib.devices import Thorlabs
from pylablib.devices.Thorlabs import ThorlabsError

from ..utils.widgets import ClosedLoopStageWidget

import logging
logger = logging.getLogger(__name__)
hwlogger = logging.getLogger("D35 DEVICES")


D35_THORLABS_DELAYSTAGE_SERIAL = dict(serial=40871684,BSC201=409600)
D35_THORLABS_BBOSTAGE_SERIAL = dict(serial=27501742)

class ThorlabsStageWidget(ClosedLoopStageWidget):
    def __init__(self,device=None,parent=None,label="Thorlabs Stage",digits=3):
        super().__init__(parent,label=label,digits=digits)        
        if device is None:
            device = ThorlabsStageHardware(label=label)
        self._dev = device     
        self._dev.newPosition.connect(self.updatePos)
        self._dev.onTarget.connect(self.setStateOK)
        self._dev.onMove.connect(self.setStateMoving)

        self.newSetpoint.connect(self.changeSetpoint)
        
    def _update(self):
        try:
            self.updatePos(self._dev.getPosition())
            if self._dev.isOnTarget(): 
                self.setStateOK() 
            else: 
                self.setStateMoving()
        except ThorlabsError as e:
            self.updateStateError()
            ClosedLoopStageWidget.handleError(self,e)





    def setStateOK(self):
        self.updateState(0)

    def setStateError(self):
        self.updateState(-1)

    def setStateMoving(self):
        self.updateState(1) # orange

    def changeSetpoint(self,value):
        self._dev.setPosition(value)



class ThorlabsStageHardware(QtCore.QObject):
    signalDeviceConnect = QtCore.pyqtSignal()
    signalDeviceDisconnected = QtCore.pyqtSignal()
    newSetpoint = QtCore.pyqtSignal(float)
    newPosition = QtCore.pyqtSignal(float)
    onTarget = QtCore.pyqtSignal()
    onMove = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._target = 0
        self._eps = 0.1

    def open(self,serial=None,BSC201=None,scale="stage"):
        if serial is None:
            raise AttributeError

        if BSC201 is not None:
            # autodetection of scale fails on BSC201/SCC201 controller
            # due to bug in pylablib and Thorlabs naming inconsistency
            # calculate units by hand.
            ssc = BSC201 # (micro)steps per revolution / screw pitch
            vpr=53.68 # values from pylablib
            avr=204.94E-6
            scale =(ssc,ssc*vpr,ssc*vpr*avr)
        self._dev = Thorlabs.KinesisMotor(serial,scale)
        self.signalDeviceConnect.emit()
        self._target = self._dev.get_position()

    def close(self):
        self._dev.close()

    def getLimits(self):
        return self.getMinimum(), self.getMaximum()

    def getMinimum(self):
        return 0

    def getMaximum(self):
        # It seems there is no way to learn the true range of the stage
        # during execution. One could look up max. travel range from 
        # Thorlabs website...
        return 50

    def startup(self):
        pass

    def shutdown(self):
        pass

    def getPosition(self):
        pos = self._dev.get_position()
        self.newPosition.emit(pos)
        return pos

    def getTarget(self):
        # No hardware support, report internal value
        return self._target

    def setPosition(self,position):
        self._dev.move_to(position)
        self._target = position
        self.newSetpoint.emit(position)

    def isPosition(self,position,eps=0.001):
        pos = self.getPosition()
        return abs(position-pos)<eps
        
    def isOnTarget(self):
        state = abs(self.getPosition()-self._target)<self._eps
        if state:
            self.onTarget.emit()
        return state

    def isMoving(self):
        state =  self._dev.is_moving()
        if state:
            self.onMove.emit()
        return state


