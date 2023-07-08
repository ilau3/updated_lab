from ..shutter import ThorlabsShutterWidget, ThorlabsShutterHardware
from ..stages import PIStageWidget, PIStageHardware, GCSError
from ..stages import ThorlabsStageWidget, ThorlabsStageHardware, ThorlabsError
from ..utils.widgets import StageController
from ..utils.definitions import ConsoleWindowLogHandler

from ..xuvcamera import XUVCamera, XUVCameraGui


from PyQt5 import QtCore,QtWidgets

import logging
logger = logging.getLogger(__name__)
hwlogger = logging.getLogger("D93 DEVICES")


data_folder = QtCore.QStandardPaths.locate(QtCore.QStandardPaths.DesktopLocation,"XUVData",QtCore.QStandardPaths.LocateDirectory), # Find XUVData folder on Desktop

wait_function = QtWidgets.QApplication.processEvents

class ExperimentHelper:
    @staticmethod
    def waitForCamera():
        while not cam.clearAcquisition():
            wait_function()

    @staticmethod
    def waitForSampleStage():
        while not (controller.ystage.isOnTarget() and controller.xstage.isOnTarget()):
            wait_function()        

    @staticmethod
    def waitForPiezoStage():
        while not controller.piezoStage.isOnTarget():
            wait_function()        

    @staticmethod
    def waitForLongStage():
        while not controller.longStage.isOnTarget():
            wait_function()


    @staticmethod
    def waitForWaveplate():
        while not controller.waveplate.isOnTarget():
            wait_function()

    @staticmethod
    def getSpectrum(timeout):
        if not cam.startFrame(): # Start acquisition loop        
            logger.error("Did not start acquisition, error: {}".format(cam.cam.getLastError()))
        err, res = cam.grabFrame(timeout=timeout)
        # res = cam.getFrame()
        if res is not None:
            return res[0][0,0,:]
        else:
            if err == 32:
                logger.warning("Could not grab frame")

    @staticmethod
    def initLogger(log,logfile):
        for hdlr in log.handlers[:]:  # remove all old handlers
            log.removeHandler(hdlr)
        # create file handler
        fh = logging.FileHandler(logfile)
        fh.setLevel(logging.INFO)
        # create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        log.addHandler(fh)
        log.addHandler(ch)

    @staticmethod
    def refreshGUI():
        wait_function()

    @staticmethod
    def lockGUI():
        cam.requestAcquisitionLock()

    @staticmethod
    def unlockGUI():
        ExperimentHelper.waitForCamera()
        cam.releaseAcquisitionLock()




D35_PI_PIEZOSTAGE_USB = dict(model="E-754", connect_type="USB", serial=118044513)
D35_THORLABS_DELAYSTAGE_SERIAL = dict(serial=40871684,BSC201=409600)






class D35StageController(StageController):
    def __init__(self,startup=True,stability=False):
        self.xstage = PIStageHardware()
        self.ystage = PIStageHardware()
        self.longStage = ThorlabsStageHardware()
        self.piezoStage = PIStageHardware()

        self.widget_xstage = PIStageWidget(self.xstage,label="Sample X")
        self.widget_ystage = PIStageWidget(self.ystage,label="Sample Y")
        self.widget_longStage = ThorlabsStageWidget(self.longStage,label="Long Stage",digits=3)
        self.widget_piezoStage = PIStageWidget(self.piezoStage,label="Piezo Stage")

        self.shutter = ThorlabsShutterHardware()
        self.widget_shutter = ThorlabsShutterWidget(self.shutter)




        shutters = [self.widget_shutter]
        stages = [self.widget_xstage, self.widget_ystage, None, self.widget_longStage, self.widget_piezoStage]

        if stability:
            # add option to launch directly into attolock
            pass

        super().__init__(stages=stages,shutters=shutters)
        
        # Console handler
        consoleHandler = ConsoleWindowLogHandler()
        consoleHandler.sigLog.connect(self.logView.appendPlainText)
        hwlogger.addHandler(consoleHandler)


        if startup:
            self.startup()


    def addWavepalte(self):
        self.waveplate = ThorlabsStageHardware()
        self.widget_waveplate = ThorlabsStageWidget(self.waveplate,label="Waveplate",digits=1) 

        

        # need to insert stage widget semi-manually to StageController.
        self.insertStage(self.widget_waveplate)
        
        try:                
            self.waveplate.open(**D35_THORLABS_WAVEPLATE_SERIAL)
        except ThorlabsError:
            hwlogger.info("Thorlabs Waveplate Motor unavailable. Check log for more info")
            self.widget_waveplate.setEnabled(False)
            logger.exception("Thorlabs Waveplate Motor unavailable:")
        
        

    def startup(self):
        try:
            self.xstage.open(**D35_PI_XSTAGE_SERIAL)        
        except GCSError:
            hwlogger.info("X-Stage unavailable. Check log for more info")
            self.widget_xstage.setEnabled(False)
            logger.exception("X-Stage unavailable:")
        try:
            self.ystage.open(**D35_PI_YSTAGE_SERIAL)        
        except GCSError:
            hwlogger.info("Y-Stage unavailable. Check log for more info")
            self.widget_ystage.setEnabled(False)
            logger.exception("Y-Stage unavailable:")

        try:                
            self.longStage.open(**D35_THORLABS_DELAYSTAGE_SERIAL)
        except ThorlabsError:
            hwlogger.info("Thorlabs Stage unavailable. Check log for more info")
            self.widget_longStage.setEnabled(False)
            logger.exception("Thorlabs Stage unavailable:")

        try:
            self.piezoStage.open(**D35_PI_PIEZOSTAGE_USB)
        except GCSError:
            hwlogger.info("Piezo Stage unavailable. Check log for more info")
            self.widget_piezoStage.setEnabled(False)
            logger.exception("Piezo Stage unavailable:")

        try:
            self.shutter.open(D35_SHUTTER_SERIAL)
        except ThorlabsError:
            hwlogger.info("Piezo Stage unavailable. Check log for more info")
            self.widget_piezoStage.setEnabled(False)
            logger.exception("Piezo Stage unavailable:")

        try:
            self.update(overwriteSetpoints=True)
        except:
            hwlogger.exception("Error in initial reading of stages:")

        
    def close(self):
        try:
            self.xstage.close()
        except:
            logger.exception("Error closing X-stage:")
        try:
            self.ystage.close()
        except:
            logger.exception("Error closing Y-stage:")
        try:
            self.piezoStage.close()
        except:
            logger.exception("Error closing piezo:")
        try:
            self.longStage.close()
        except:
            logger.exception("Error closing Thorlabs delay stage:")
        try:
            self.shutter.close()
        except:
            logger.exception("Error closing shutter:")
            
        try:
            self.waveplate.close()
        except AttributeError:
            pass
        except:
            logger.exception("Error closing shutter:")            
            
          
            
# Define singleton instances by global import
cam = XUVCamera()
xuvgui = XUVCameraGui(device=cam)
controller = D35StageController()
            