
from PyQt6 import QtWidgets
import logging
#logger name?
logger = logging.getLogger(__name__)

wait_function = QtWidgets.QApplication.processEvents

def waitForCamera():
        while not cam.clearAcquisition():
            wait_function()

def waitForPiezoStage():
        while not controller.piezoStage.isOnTarget():
            wait_function()

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

def refreshGUI():
        wait_function()

def lockGUI():
        cam.requestAcquisitionLock()

def unlockGUI():
        waitForCamera()
        cam.releaseAcquisitionLock()