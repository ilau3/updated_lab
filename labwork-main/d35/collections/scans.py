# -*- coding: utf-8 -*-
"""
Acquire a GasTransient
This is a sample script file to acquire a GasTransient.

The script will:
- Move to the cell position
- Open the shutter
- Acquire one spectrum for each delay position on the piezo
- Close the shutter
- Save the scan to a h5 file for further processing

Copy the script to your experiment folder,
Adapt the configuration parameters (see below),
run the script.
"""

import time
import os
from PyQt5 import QtCore, QtWidgets
import h5py
import logging
import numpy as np

from .d35 import ExperimentHelper, cam, controller, wait_function


class Background(object):
    def __init__(self,membrane_x,membrane_y,frames=10,camera=cam,stageController=controller):
        self._x = membrane_x
        self._y = membrane_y
        self.frames = frames
        
        self.cam = camera
        self.controller = stageController
        pass
    
    def pumpOff(self):
        results = np.zeros((self.frames,1340),dtype=np.uint16)
        #logger.info("Starting Background")
        try:
            
            #logger.debug("Locking GUI")
            self.cam.requestAcquisitionLock()   
            #logger.info("Starting Background with pump off") 
            self.controller.shutter.setShutter(False)
            self.controller.ystage.setPosition(self._y)
            self.controller.xstage.setPosition(self._x)      
            while not (self.controller.ystage.isOnTarget() and self.controller.xstage.isOnTarget()):
                wait_function()    
            for n in range(self.frames):      
                while not self.cam.clearAcquisition():
                    wait_function()
                    
                #logger.info("Take Background")
                results[n,:] = ExperimentHelper.getSpectrum(10000)
                wait_function()
            self.cam.clearAcquisition()
            self.cam.clearAcquisition()
            self.cam.releaseAcquisitionLock()
        except:
            # logger.exception("Aborting Acquisition: An error occured during the scan:")
            self.controller.shutter.setShutter(False)
            self.cam.stopFrame()
            self.cam.releaseAcquisitionLock()
            raise        
        return results
    
    def pumpOn(self):
        results = np.zeros((self.frames,1340),dtype=np.uint16)
        #logger.info("Starting Background")
        try:
            
            #logger.debug("Locking GUI")
            self.cam.requestAcquisitionLock()   
            #logger.info("Starting Background with pump off") 
            self.controller.shutter.setShutter(False)
            self.controller.ystage.setPosition(self._y)
            self.controller.xstage.setPosition(self._x)      
            while not (self.controller.ystage.isOnTarget() and self.controller.xstage.isOnTarget()):
                wait_function()    
            for n in range(self.frames):      
                while not self.cam.clearAcquisition():
                    wait_function()
                self.controller.shutter.setShutter(True)                    
                #logger.info("Take Background")
                results[n,:] = ExperimentHelper.getSpectrum(10000)
                wait_function()
                
            self.controller.shutter.setShutter(False)                
            self.cam.clearAcquisition()
            self.cam.clearAcquisition()
            self.cam.releaseAcquisitionLock()
        except:
            # logger.exception("Aborting Acquisition: An error occured during the scan:")
            self.controller.shutter.setShutter(False)
            self.cam.stopFrame()
            self.cam.releaseAcquisitionLock()
            raise        
        return results
       


    

class GasTransient(object):
    def __init__(self,cell_x,cell_y,piezo_start,piezo_stop,piezo_step,cam=cam,stageController=controller,**kwargs):
        self.cam = cam
        self.controller = stageController
        self.cell_x = cell_x
        self.cell_y = cell_y
        self.piezo_start = piezo_start
        self.piezo_stop = piezo_stop
        self.piezo_step = piezo_step
        self.experiment_name = kwargs.pop("experiment_name","default")

        self.fileinfo = kwargs.pop("fileinfo","")

        self.cam_settings = dict()
        for key in ["camera_exposure","camera_gain","camera_slow","camera_high_sensitivity","camera_temp"]:
            if key in kwargs:
                self.cam_settings[key] = kwargs[key]                

        self.long_delay_pos = kwargs.pop("long_delay_pos",None)

        self.file_settings = dict()
        self.file_settings["filename_base"] = kwargs.pop("filename_base","gasTransient_")
        self.file_settings["filename_extension"] = kwargs.pop("filename_extension","")
        self.file_settings["filename_addDate"] = kwargs.pop("filename_addDate", True)
        self.data_folder = kwargs.pop("data_folder",
            QtCore.QStandardPaths.locate(QtCore.QStandardPaths.DesktopLocation,"XUVData",QtCore.QStandardPaths.LocateDirectory))
        self.experiment_folder = kwargs.pop("experiment_folder", time.strftime("%Y_%m_%d/"))
        self.experiment_type = kwargs.pop("experiment_type","gasTransient")

        self.wait_function = kwargs.pop("wait_function",QtWidgets.QApplication.processEvents)

        # Pre-process some of the settings, create folders & files.
        self.destination_folder = os.path.join(self.data_folder,self.experiment_folder)

        self._createDestinationFolder()
        if "logger" in kwargs:
            self.logger = kwargs["logger"]
        else:
            self._initLogger()
        self._checkHardware()


    def _createDestinationFolder(self):
        if not os.path.exists(self.destination_folder): # Create folder if it doesn't exist already
            os.mkdir(self.destination_folder) 

    def _initLogger(self):
        log_file = os.path.join(self.destination_folder,'message.log')

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        # create file handler which logs even debug messages
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def _checkHardware(self):
        if not self.cam.isConnected():
            self.logger.error("Camera not ready, abort.")
            raise RuntimeError

    def _prepareArrays(self):
        self.delays = np.arange(self.piezo_start,self.piezo_stop,self.piezo_step)
        self.results = np.zeros((len(self.delays),1340),dtype=np.double)

    def _prepareCamera(self):
        # Prepare Camera
        self.cam.releasePreviewLock() # Make sure the preview loop is stopped.
        while not self.cam.clearAcquisition():
            self.wait_function()

        self.logger.info("Setting camera settings...")
        if "camera_exposure" in self.cam_settings:
            self.logger.info("... Exposure: {:d} ms".format(self.cam_settings["camera_exposure"]))
            self.cam.setExposure(self.cam_settings["camera_exposure"])

        if "camera_gain" in self.cam_settings:
            pass
        if "camera_slow" in self.cam_settings:
            pass
        if "camera_high_sensitivity" in self.cam_settings:
            pass
        if "camera_temperature" in self.cam_settings:
            pass

        self.logger.debug("Locking GUI.")
        self.cam.requestAcquisitionLock()

    def _createConfig(self):
        config =  dict(
            cell_x = self.cell_x,
            cell_y = self.cell_y,
            experiment_name = self.experiment_name,
            piezo_start = self.piezo_start,
            piezo_end = self.piezo_stop,
            piezo_step = self.piezo_step,
            fileinfo = self.fileinfo,
            experiment_type = self.experiment_type                
            )
        if self.long_delay_pos is not None:
            config["long_delay_pos"] = self.long_delay_pos
        for key in self.cam_settings:
            config[key] = self.cam_settings[key]
        for key in self.file_settings:
            config[key] = self.file_settings[key]
        return config

    def save(self,**kwargs):
        for key in kwargs:
            self.file_settings[key] = kwargs[key]

        self.logger.info("Preparing Files...")
        # Prepare the file name
        if "filename" in kwargs:
            file_base = kwargs["filename"]
        else:
            file_base = self.file_settings["filename_base"]+self.file_settings["filename_extension"]
        if self.file_settings["filename_addDate"]:
            file_string = file_base+time.strftime("%Y_%m_%d_%H_%M_%S")+".hdf5"
        else:
            file_string = file_base+".hdf5"
        data_file = os.path.join(self.destination_folder,file_string)
        f = h5py.File(data_file, "x")
        f.attrs["experiment_type"] = self.experiment_type
        f.attrs["fileinfo"] = self.fileinfo
        f.attrs["timestamp"] = time.time()
        parameters = f.create_group("script_parameters")
        config = self._createConfig()
        for key in config:
            parameters.attrs[key] = config[key]

        data_group = f.create_group("data")

        data_set = data_group.create_dataset("res0",data=self.results)
        data_set.attrs["delays"] = self.delays
        data_set.attrs["x_axis"] = np.arange(self.results.shape[-1])

        self.logger.info("File saved")


    def run(self):
        self._prepareArrays()
        self.logger.info("Starting Gas Transient on Piezo stage, going from {:.1f} to {:.1f} with {:.01f} steps.".format(self.piezo_start,self.piezo_stop,self.piezo_step))
        self._prepareCamera()

        try:
            # Check if stages need to be moved.
            if not (self.controller.xstage.isPosition(self.cell_x) and self.controller.ystage.isPosition(self.cell_y)):
                self.logger.info("Moving sample stage to position X:{:.2f} Y:{:.2f}...".format(self.cell_x,self.cell_y))
                self.controller.shutter.setShutter(False) # Close shutter for safety
                self.controller.ystage.setPosition(self.cell_y)
                self.controller.xstage.setPosition(self.cell_x)
                self.controller.piezoStage.setPosition(self.delays[0])
            if self.long_delay_pos is not None:
                if not (self.controller.longStage.isPosition(self.long_delay_pos)):
                    self.logger.info("Moving long delay stage to position {}...".format(self.long_delay_pos))
                    self.controller.longStage.setPosition(self.long_delay_pos)
                    while not self.controller.longStage.isOnTarget():
                        self.wait_function()
            while not (self.controller.ystage.isOnTarget() and self.controller.xstage.isOnTarget()):
                self.wait_function()

            self.logger.info("! Starting Acquisition !")
            
            self.controller.shutter.setShutter(True)
            for n, tau in enumerate(self.delays):

                self.logger.info("At position {}".format(tau))
                self.controller.piezoStage.setPosition(tau)
                while not self.cam.clearAcquisition():
                    self.wait_function()
                    # Throw away old data
                while not self.controller.piezoStage.isOnTarget():
                    self.wait_function()


                if not self.cam.startFrame(): # Start acquisition loop        
                    self.logger.error("Did not start acquisition, error: {}".format(self.cam.cam.getLastError()))
                err, res = self.cam.grabFrame(timeout=10000)
                # res = cam.getFrame()
                if res is not None:
                    self.results[n,:] = res[0][0,0,:]
                else:
                    if err == 32:
                        self.logger.warning("Could not grab frame")
                self.wait_function()
                if self.controller.aborted:
                    self.logger.warning("Acquisition aborted!")
                    break
                while self.controller.paused:
                    self.wait_function()                    

            self.logger.info("Finished acquisition, cleaning up.")
            self.controller.shutter.setShutter(False)
            self.cam.clearAcquisition()
            self.cam.clearAcquisition()
            self.cam.releaseAcquisitionLock()
        except:
            self.logger.exception("Aborting Acquisition: An error occured during the scan:")
            self.controller.shutter.setShutter(False)
            self.cam.stopFrame()
            self.cam.releaseAcquisitionLock()
            raise
