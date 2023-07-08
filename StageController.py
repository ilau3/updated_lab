from Reference import StageController, ConsoleWindowLogHandler
from HardwareConnection import ThorlabsShutterHardware, ThorlabsShutterWidget, PIStageWidget, PIStageHardware
from pipython import GCSError
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QApplication
import sys
#import pylablib
#from pylablib.devices.Thorlabs import ThorlabsError

import logging
logger = logging.getLogger(__name__)
hwlogger = logging.getLogger("D93 DEVICES")

#D93_SHUTTER_USB = dict(comport="COM5")
#D93_PI_PIEZOSTAGE_SERIAL = dict(comport = 'COM5')
#D93_PI_PIEZOSTAGE_SERIAL = dict(model="E-709", serial = "118062371", connect_type="USB", com_port='5',baudrate=19200,axes="A")
#D93_PI_PIEZOSTAGE_SERIAL = dict(model="E-709", serial = None, connect_type="USB", com_port='5',baudrate=19200,axes="A")
#D93_PI_PIEZOSTAGE_SERIAL = dict(model="P-611",connect_type="USB", serial="118056715")
D93_PI_PIEZOSTAGE_SERIAL = dict(model="E-709",connect_type="USB", serial="118062371")
class StageController(StageController):
    def __init__(self,startup=True,stability=False):
        #self.shutter = ThorlabsShutterHardware()
        #self.shutter_widget = ThorlabsShutterWidget(self.shutter)

        self.stage = PIStageHardware()
        #app = QApplication(sys.argv)
        self.stage_widget = PIStageWidget(self.stage, label = "PI Stage")

        #shutter = [self.shutter_widget]
        stage = [self.stage_widget]

        super().__init__(stages=stage)
        #shutters=shutter

        consoleHandler = ConsoleWindowLogHandler()
        consoleHandler.sigLog.connect(self.logView.appendPlainText)
        hwlogger.addHandler(consoleHandler)

        if startup:
            self.start()

    def start(self): 
        self.stage.open(**D93_PI_PIEZOSTAGE_SERIAL)
        #try:
            #self.stage.open(**D93_PI_PIEZOSTAGE_SERIAL)
        #except GCSError:
            #hwlogger.info("Delay Stage unavailable. Check log for more info")
            #self.stage_widget.setEnabled(False)
            #logger.exception("Delay Stage unavailable:")

        #try:
            #self.shutter.open(**D93_SHUTTER_USB)
        #except ThorlabsError:
            #hwlogger.info("Shutter unavailable. Check log for more info")
            #self.shutter_widget.setEnabled(False)
            #logger.exception("Shutter unavailable:")

        #try:
            #self.update(overwriteSetpoints=True)
        #except:
            #hwlogger.exception("Error in initial reading of stages:")
    
    def close(self):
        self.stage.close()
        #try:
            #self.stage.close()
        #except:
            #logger.exception("Error closing delay stage:")
        #try:
            #self.shutter.close()
        #except:
            #logger.exception("Error closing shutter:")
            
