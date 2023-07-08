from PyQt5 import QtGui, QtCore, QtWidgets
from pylablib.devices import Thorlabs

from ..utils.widgets import ShutterWidget
import time


class ThorlabsShutterWidget(ShutterWidget):
    def __init__(self,device=None,parent=None):
        if device is None:
            device = ThorlabsShutterHardware()
        self._dev = device
        super().__init__(parent)

        self.signalOpenShutter.connect(self.openShutter)
        self.signalCloseShutter.connect(self.closeShutter)

        self._dev.signalOpenedShutter.connect(self.shutterOpened)
        self._dev.signalClosedShutter.connect(self.shutterClosed)

        
    def openShutter(self):
        self._dev.setShutter(True)

    def closeShutter(self):
        self._dev.setShutter(False)

    def _update(self):
        self._dev.getShutter()



class ThorlabsShutterHardware(QtCore.QObject):
    signalOpenedShutter = QtCore.pyqtSignal()
    signalClosedShutter = QtCore.pyqtSignal()
    signalDeviceConnect = QtCore.pyqtSignal()
    signalDeviceDisconnected = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._shadowShutter = None # Local copy of desired state

    def _queryState(self):
        msg = self._dev.query(0x04CC)
        return msg.param2==0x01        

    def _emitSignal(self, state):
        if state: self.signalOpenedShutter.emit() 
        else: self.signalClosedShutter.emit()

    def open(self,serial=None):
        if serial is None:
            try:
                serial = D35_SHUTTER_SERIAL
            except NameError:
                # Could try to connect to the first shutter we can find
                # But for now let's give up
                raise
        self._dev = Thorlabs.BasicKinesisDevice(serial)
        self.signalDeviceConnect.emit()
        self._shadowShutter = self.getShutter(forceEmit=True)        

    def close(self):
        self._dev.close()

    def setShutter(self,state=False,timeout=1000):
        """ Open or close the shutter, shutter will open if state is set to true. 
        If timeout is 0, will not check if shutter movement completed.
        If timeout is <0 will wait until shutter movement completed
        If timeout is >0 will wait value in ms for shutter to movement to complete or raise TimeoutError """
        # As per Thorlabs Doc, Set SOL is 0x04CB
        self._dev.send_comm(0x04CB,0x00,0x01 if state else 0x02)
        if timeout != 0:
            return self.waitOnShutter(state,timeout)


    def waitOnShutter(self,state: bool,timeout=1000):
        """ Wait until shutter reports complete opening """
        start = time.time()
        while self._queryState() is not state:
            QtWidgets.QApplication.processEvents()
            if timeout>=0 and (time.time()-start)>(timeout/1000.):
                raise TimeoutError
        self._shadowShutter = state
        self._emitSignal(state)
        return state

    def getShutter(self,forceEmit=False):
        """ Query the state of the shutter, return true if shutter is open """
        # As per Thorlabs Doc, Req SOL is 0x04CC
        state = self._queryState()
        if state is not self._shadowShutter or forceEmit:
            self._emitSignal(state)
            self._shadowShutter = state
        return state


