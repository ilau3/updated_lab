from PyQt5 import QtGui, QtCore
from PIPython import GCSDevice, GCSError, gcserror

from ..utils.widgets import ClosedLoopStageWidget

import logging
logger = logging.getLogger(__name__)
hwlogger = logging.getLogger("D35 DEVICES")


D35_PI_PIEZOSTAGE_SERIAL = dict(model="E-754", connect_type="USB", serial=None)
D35_PI_XSTAGE_SERIAL = dict(model="C-663", connect_type="RS232", com_port="1")
D35_PI_YSTAGE_SERIAL = dict(model="C-663", connect_type="RS232", com_port="2")
D35_PI_HHGSTAGE_SERIAL = dict(model="C-663", connect_type="RS232", com_port="12")


class PIStageWidget(ClosedLoopStageWidget):
    def __init__(self,device=None,parent=None,label="PI Stage",**kwargs):
        super().__init__(parent,label=label,**kwargs)        
        if device is None:
            device = PIStageHardware(**kwargs)
        self._dev = device
        self._dev.signalDeviceConnect.connect(self.setStateOK)

        self.newSetpoint.connect(self.changeSetpoint)
       

    def _update(self):
        try:
            self.updatePos(self._dev.getPosition())
            if self._dev.isOnTarget: 
                self.setStateOK() 
            else: 
                self.setStateMoving()
        except GCSError as e:
            self.updateStateError()
            ClosedLoopStageWidget.handleError(self,e)



    def setStateOK(self):
        self.updateState(0)

    def setStateError(self):
        self.updateState(-1)

    def setStateMoving(self):
        self.updateState(1) # orange

    def changeSetpoint(self,value):
        try:
            self._dev.setPosition(value)
        except GCSError as e:
            self.updateStateError()
            self.handleError(e)




class PIStageHardware(QtCore.QObject):
    signalDeviceConnect = QtCore.pyqtSignal()
    signalDeviceDisconnected = QtCore.pyqtSignal()
    newSetpoint = QtCore.pyqtSignal(float)
    newPosition = QtCore.pyqtSignal(float)
    onTarget = QtCore.pyqtSignal()
    onMove = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()

    def open(self,model=None,serial=None,connect_type=None,com_port=None,ip=None,baudrate=115200,fastmode=False):
        if model is None:
            raise AttributeError
        self._dev = GCSDevice(model)
        if serial is not None and connect_type == 'USB':
            self._dev.ConnectUSB(serial)
        elif com_port is not None and connect_type == "RS232":
            self._dev.ConnectRS232(comport=com_port, baudrate=baudrate)
        elif ip is not None and connect_type == "IP":
            self._dev.ConnectTCPIP(ipaddress=ip)
        else:
            self._dev.InterfaceSetupDlg()

        logger.info("Connected to device: " + self._dev.qIDN().strip())

        if fastmode:
            self._dev.errcheck = False

        self.signalDeviceConnect.emit()

    def close(self):
        self._dev.CloseConnection()

    def getLimits(self,axes="1"):
        return self.getMinimum(axes), self.getMaximum(axes)

    def getMinimum(self,axes="1"):
        return self._dev.qTMN(axes)[axes]

    def getMaximum(self,axes="1"):
        return self._dev.qTMX(axes)[axes]

    def startup(self,axes="1"):
        self._dev.SVO(axes,1)

    def shutdown(self,axes="1"):
        self._dev.SVO(axes,0)

    def getPosition(self,axes="1"):
        pos = self._dev.qPOS(axes)[axes]
        self.newPosition.emit(pos)
        return pos

    def getTarget(self,axes="1"):
        return self._dev.qMOV(axes)[axes]

    def setPosition(self,position,axes="1"):
        self._dev.MOV(axes,position)
        self.newSetpoint.emit(position)

    def isPosition(self,position,eps=0.001,axes="1"):
        pos = self.getPosition()
        return abs(position-pos)<eps and self.isOnTarget()
        
    def isOnTarget(self,axes="1"):
        state = self._dev.qONT(axes)[axes]
        if state:
            self.onTarget.emit()
        return state

    def isMoving(self,axes="1"):
        state = self.isOnTarget(axes)
        if not state:
            self.onMove.emit()
        return not state







