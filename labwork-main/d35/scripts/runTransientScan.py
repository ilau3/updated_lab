# -*- coding: utf-8 -*-
"""
Acquire a Transient Pump On/Off Scan
This is a sample script file to acquire a transient scan.

The script will:
- Take background images
- Loop until max_scans is reached
-- Take a gas transient if gas_transient is true in scanConfig
-- Move to the cell position
-- For each delay, move the piezo in position,
--- Take a spectrum with shutter open and shutter closed
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

from d35 import xuvcamera
from d35.collections.d35 import D35StageController
from d35.collections.scans import GasTransient

#%%
"""
SETTINGS BLOCK
"""
scanConfig = dict(
    ################################
    ### Required Parameters      ###
    ################################
    ## Experiment Configuration
    # Set the sample positions
    sample_x = 12.8,
    sample_y = 19.2,
    # Set the camera exposure
    camera_exposure = 40,
    # Set start and end on the piezo stage. Note: Scan will only go to last step before end!
    piezo_start = 5,
    piezo_end = 15,
    # Set step size. Make sure sign of step points in the right direction
    piezo_step = 0.1,

    fileinfo = "Scan", # Free text info field
    # Optional Parameters. Comment out to use default parameters or
    #   use the parameters you have set in the GUIs
    # long_delay_pos = 18.000,
    # camera_gain = 3
    # camera_slow = False
    # camera_high_sensitivity = False
    # camera_temp = -20.

    # Default Parameters, only change if you need to.
    max_scans = 1000,

    ## File Configuration
    # Files will be saved to folder: Desktop\XUVData\YYYY_MM_DD\
    # with file name "(filename_base)(filename_extension)(scan_number)(date).hdf5
    filename_base = "scan_",
    filename_extension = "PtProperMembrane_" ,    
    #set True if you want the date to be added
    filename_addDate = True,    
    # Free text info line to be saved to files
    fileinfo = "Scan",

    ################################
    ### Optional Parameters      ###
    ################################
    # (currently none)
)


# Default Parameters, only change if you need to.
max_scans = 1000,
filename_addDate = True,
data_folder = QtCore.QStandardPaths.locate(0,"XUVData",1), # Find XUVData folder on Desktop
experiment_folder = time.time().strftime("%Y_%m_%d/"), # YYYY_MM_DD/
experiment_type = "pumpprobescan"


# Pre-process some of the settings, create folders & files.
destination_folder = os.path.join(scanConfig["data_folder"],scanConfig["experiment_folder"])
if not os.path.exists(destination_folder): # Create folder if it doesn't exist already
    os.mkdir(destination_folder) 
log_file = os.path.join(destination_folder,'message.log')

#%%

"""
Prepare Logfile
"""

# get instance of the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

#%%

"""
Initialize the hardware and show GUI controlls
"""

logger.info("Initializing Hardware")
from d35.collections.d35 import cam, xuvgui, controller, ExperimentHelper

ExperimentHelper.initLogger(logger,log_file)

logger.debug("Starting Camera GUI")
window.show()
if not window._connected:
    window.connect() # Get camera online with default parameters.

logger.debug("Starting Controller GUI")
controller.show()


#%%
#####################
# Run Transient with Shutter on/off #
#####################


piezo_start = scanConfig["piezo_start"]
piezo_end = scanConfig["piezo_end"]
piezo_step = scanConfig["piezo_step"]
exposure_ms = scanConfig["camera_exposure"]

logger.info("Setting up scan on Piezo stage, going from {:.1f} to {:.1f} with {:.01f} steps.".format(piezo_start,piezo_end,piezo_step))

delays = np.arange(piezo_start,piezo_end,piezo_step)

resultsBackgroundOff = np.zeros((10,1340),dtype=np.double)
resultsBackgroundOn = np.zeros((10,1340),dtype=np.double)

# Prepare Camera
cam.releasePreviewLock() # Make sure the preview loop is stopped.
ExperimentHelper.waitForCamera()

logger.info("Setting camera settings...")
logger.info("... Exposure: {:d} ms".format(exposure_ms))
cam.setExposure(exposure_ms)

"""
if "camera_gain" in gasTransientConfig:
    pass
if "camera_slow" in gasTransientConfig:
    pass
if "camera_high_sensitivity" in gasTransientConfig:
    pass
if "camera_temperature" in gasTransientConfig:
    pass
"""


#%%
""" Take Background
"""

logger.info("Starting Background")
try:
    
    logger.debug("Locking GUI")
    ExperimentHelper.lockGUI()
    logger.info("Starting Background with pump off") 
    controller.shutter.set_shutter(False)
    # Go to sample position
    controller.ystage.setPosition(scanConfig["sample_y"])
    controller.xstage.setPosition(scanConfig["sample_x"])      
    # Wait for stages to reach position
    ExperimentHelper.waitForSampleStage()  


    for n in range(10):      
        ExperimentHelper.waitForCamera()

        logger.info("Take Background")

        res = ExperimentHelper.getSpectrum(timeout=exposure_ms*10)
        if res is not None:
            resultsBackgroundOff[n,:] = res
        else:
            logger.warning("Could not grab frame")
        ExperimentHelper.refreshGUI()

    logger.info("Starting Background with pump on")
    for n in range(10):       
        ExperimentHelper.waitForCamera()
        controller.shutter.set_shutter(True)

        logger.info("Take Background")

        res = ExperimentHelper.getSpectrum(timeout=exposure_ms*10)
        if res is not None:
              resultsBackgroundOn[n,:] = res
        else:
            logger.warning("Could not grab frame")
        ExperimentHelper.refreshGUI()
        
    logger.info("Finished background, cleaning up.")
    controller.shutter.set_shutter(False)
    ExperimentHelper.unlockGUI()
except:
    logger.exception("Aborting Acquisition: An error occured during the scan:")
    controller.shutter.setShutter(False)
    cam.stopFrame()
    ExperimentHelper.unlockGUI()
    raise

#%%


""" 
Run Scan
"""
logger.info("! Starting pump-probe scan !")
for n_scan in range(scanConfig["max_scans"]):
    logger.info("Iteration Nr. {}".format(n_scan))

    
    logger.info("Doing gas reference")
    gasTransient = GasTransient(cam, controller, 12.8, 19.1,5,15,0.1,camera_exposure=40,logger=logger)
    gasTransient.run()
    
    resultsOn = np.zeros((len(delays),1340),dtype=np.double)
    resultsOff = np.zeros((len(delays),1340),dtype=np.double)
    logger.info("Preparing Files...")
    # Prepare the file name
    if scanConfig["filename_addDate"]:
        file_string = scanConfig["filename_base"]+scanConfig["filename_extension"]+"scan_{:03d}_".format(n_scan)+time.strftime("%Y_%m_%d_%H_%M_%S")+".hdf5"
    else:
        file_string = scanConfig["filename_base"]+scanConfig["filename_extension"]+"scan_{:03d}_".format(n_scan)+".hdf5"
    data_file = os.path.join(destination_folder,file_string)

    f = h5py.File(data_file, "x")
    parameters = f.create_group("script_parameters")
    for key in scanConfig:
        parameters.attrs[key] = scanConfig[key]

    data_group = f.create_group("data")
    sub_group = data_group.create_group("bg0")     
    data_set = sub_group.create_dataset("off",data=resultsBackgroundOff)
    data_set = sub_group.create_dataset("on",data=resultsBackgroundOn)
    
    sub_group = data_group.create_group("gas")
    data_set = sub_group.create_dataset("on",data=gasTransient.results)
    data_set.attrs["delays"] = gasTransient.delays

    try:
        logger.debug("Locking GUI")
        cam.requestAcquisitionLock() 
        cam.setExposure(exposure_ms)
        # Check if stages need to be moved.
        controller.shutter.setShutter(False) # Close shutter for safety
        controller.ystage.setPosition(scanConfig["sample_y"])
        controller.xstage.setPosition(scanConfig["sample_x"])  
        while not cam.clearAcquisition():
            wait_function()
        while not (controller.ystage.isOnTarget() and controller.xstage.isOnTarget()):
            wait_function()    

        for n, tau in enumerate(delays):
            print("Position {}".format(tau))
            controller.piezoStage.setPosition(tau)
            while not cam.clearAcquisition():
                wait_function()
                # Throw away old data
            while not controller.piezoStage.isOnTarget():
                wait_function()

            controller.shutter.setShutter(True)
            #sleep(0.0152)        
            if not cam.startFrame(): # Start acquisition loop        
                logger.error("Did not start acquisition, error: {}".format(cam.cam.getLastError()))
            err, res = cam.grabFrame(timeout=exposure_ms*10)
            # res = cam.getFrame()
            if res is not None:
                resultsOn[n,:] = res[0][0,0,:]
            else:
                if err == 32:
                    logger.warning("Could not grab frame")
            controller.shutter.setShutter(False,timeout=0)
            while not cam.clearAcquisition():
                wait_function()
            controller.shutter.waitOnShutter(False)
            #sleep(0.015)
            if not cam.startFrame(): # Start acquisition loop        
                logger.error("Did not start acquisition, error: {}".format(cam.cam.getLastError()))
            err, res = cam.grabFrame(timeout=exposure_ms*10)
            # res = cam.getFrame()
            if res is not None:
                resultsOff[n,:] = res[0][0,0,:]
            else:
                if err == 32:
                    logger.warning("Could not grab frame")
                    
            wait_function()
            if controller.aborted:
                logger.warning("Acquisition aborted!")
                break
            while controller.paused:
                wait_function()

        controller.shutter.setShutter(False)      
        cam.clearAcquisition()
        cam.clearAcquisition()
        cam.releaseAcquisitionLock()
    except:
        controller.shutter.setShutter(False)
        cam.stopFrame()
        cam.releaseAcquisitionLock()
        raise
    finally:
        scan_group = data_group.create_group("res0")
        scan_group.create_dataset("on",data=resultsOn)
        scan_group.create_dataset("off",data=resultsOff)
        data_group.attrs["delays"] = delays
        data_group.attrs["x_axis"] = np.arange(resultsOn.shape[-1])
    if controller.stopped or controller.aborted:
        logger.info("Stopping acquisition after scan {}".format(n_scan))
        break
#%%

#####################
# Clean up
#####################

f.close()
controller.piezoStage.shutdown()
