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

from d35 import xuvcamera
from d35.collections.d35 import D35StageController

#%%
"""
SETTINGS BLOCK
"""
gasTransientConfig = dict(
    # Required Parameters
    cell_x = 12.8,
    cell_y = 19.2,
    camera_exposure = 40,
    experiment_name = "default",
    piezo_start = 5,
    piezo_end = 15,
    piezo_step = 0.1,
    fileinfo = "Gas Transient", # Free text info field
    # Optional Parameters. Comment out to use default parameters or
    #   use the parameters you have set in the GUIs
    # long_delay_pos = 18.000,
    # camera_gain = 3
    # camera_slow = False
    # camera_high_sensitivity = False
    # camera_temp = -20.

    # Default Parameters, only change if you need to.
    filename_base = "gasTransient_",
    filename_extension = "" ,
    filename_addDate = True,
    data_folder = QtCore.QStandardPaths.locate(QtCore.QStandardPaths.DesktopLocation,"XUVData",QtCore.QStandardPaths.LocateDirectory), # Find XUVData folder on Desktop
    experiment_folder = time.strftime("%Y_%m_%d/"), # YYYY_MM_DD/
    experiment_type = "gasTransient"
    )

# Pre-process some of the settings, create folders & files.
destination_folder = os.path.join(gasTransientConfig["data_folder"],gasTransientConfig["experiment_folder"])
if not os.path.exists(destination_folder): # Create folder if it doesn't exist already
    os.mkdir(destination_folder) 
log_file = os.path.join(destination_folder,'message.log')

#%%

"""
Prepare Files and Outputs.
"""

# create logger with 'spam_application'
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
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
logger.addHandler(fh)
logger.addHandler(ch)

#%%

"""
Initialize the hardware and show GUI controlls
"""

app = QtWidgets.QApplication.instance()

logger.info("Initializing camera")
cam = xuvcamera.XUVCamera()

logger.debug("Starting Camera GUI")
window = xuvcamera.XUVCameraGui(device=cam)
window.show()

window.connect() # Get camera online with default parameters.

logger.info("Initializing Hardware")
controller = D35StageController()
controller.show()


#app.exec_()

#%%
#####################
# Run Gas Transient #
#####################



# Let the GUI refresh while waiting for hardware
wait_function = QtWidgets.QApplication.processEvents

piezo_start = gasTransientConfig["piezo_start"]
piezo_end = gasTransientConfig["piezo_end"]
piezo_step = gasTransientConfig["piezo_step"]
exposure_ms = gasTransientConfig["camera_exposure"]

logger.info("Starting Gas Transient on Piezo stage, going from {:.1f} to {:.1f} with {:.01f} steps.".format(piezo_start,piezo_end,piezo_step))

delays = np.arange(piezo_start,piezo_end,piezo_step)
results = np.zeros((len(delays),1340),dtype=np.double)

# Prepare Camera
cam.releasePreviewLock() # Make sure the preview loop is stopped.
while not cam.clearAcquisition():
    wait_function()

logger.info("Setting camera settings...")
logger.info("... Exposure: {:d} ms".format(exposure_ms))
cam.setExposure(exposure_ms)

if "camera_gain" in gasTransientConfig:
    pass
if "camera_slow" in gasTransientConfig:
    pass
if "camera_high_sensitivity" in gasTransientConfig:
    pass
if "camera_temperature" in gasTransientConfig:
    pass

logger.debug("Locking GUI")
cam.requestAcquisitionLock()

logger.info("Preparing Files...")
# Prepare the file name
if gasTransientConfig["filename_addDate"]:
    file_string = gasTransientConfig["filename_base"]+gasTransientConfig["filename_extension"]+time.strftime("%Y_%m_%d_%H_%M_%S")+".hdf5"
else:
    file_string = gasTransientConfig["filename_base"]+gasTransientConfig["filename_extension"]+".hdf5"
data_file = os.path.join(destination_folder,file_string)
f = h5py.File(data_file, "x")
f.attrs["experiment_type"] = gasTransientConfig["experiment_type"]
f.attrs["fileinfo"] = gasTransientConfig["fileinfo"]
f.attrs["timestamp"] = time.time()

parameters = f.create_group("script_parameters")
for key in gasTransientConfig:
    parameters.attrs[key] = gasTransientConfig[key]

data_group = f.create_group("data")

try:
    # Check if stages need to be moved.
    if not (controller.xstage.isPosition(gasTransientConfig["cell_x"]) and controller.ystage.isPosition(gasTransientConfig["cell_y"])):
        logger.info("Moving sample stage to position X:{:.2f} Y:{:.2f}...".format(gasTransientConfig["cell_x"],gasTransientConfig["cell_y"]))
        controller.shutter.setShutter(False) # Close shutter for safety
        controller.ystage.setPosition(gasTransientConfig["cell_y"])
        controller.xstage.setPosition(gasTransientConfig["cell_x"])
        controller.piezoStage.setPosition(delays[0])
    if "long_delay_pos" in gasTransientConfig:
        if not (controller.longStage.isPosition(gasTransientConfig["long_delay_pos"])):
            logger.info("Moving long delay stage to position {}...".format(gasTransientConfig["long_delay_pos"]))
            controller.longStage.setPosition(gasTransientConfig["long_delay_pos"])
            while not controller.longStage.isOnTarget():
                wait_function()
    while not (controller.ystage.isOnTarget() and controller.xstage.isOnTarget()):
        wait_function()

    logger.info("! Starting Acquisition !")
    
    controller.shutter.setShutter(True)
    for n, tau in enumerate(delays):

        logger.info("At position {}".format(tau))
        controller.piezoStage.setPosition(tau)
        while not cam.clearAcquisition():
            wait_function()
            # Throw away old data
        while not controller.piezoStage.isOnTarget():
            wait_function()


        if not cam.startFrame(): # Start acquisition loop        
            logger.error("Did not start acquisition, error: {}".format(cam.cam.getLastError()))
        err, res = cam.grabFrame(timeout=exposure_ms*10)
        # res = cam.getFrame()
        if res is not None:
            results[n,:] = res[0][0,0,:]
        else:
            if err == 32:
                logger.warning("Could not grab frame")
        wait_function()
        if controller.aborted:
            logger.warning("Acquisition aborted!")
            break
        while controller.paused:
            wait_function()

    logger.info("Finished acquisition, cleaning up.")
    controller.shutter.setShutter(False)
    cam.clearAcquisition()
    cam.clearAcquisition()
    cam.releaseAcquisitionLock()
except:
    logger.exception("Aborting Acquisition: An error occured during the scan:")
    controller.shutter.setShutter(False)
    cam.stopFrame()
    cam.releaseAcquisitionLock()
    raise
finally:
    data_set = data_group.create_dataset("res0",data=results)
    data_set.attrs["delays"] = delays
    data_set.attrs["x_axis"] = np.arange(results.shape[-1])

#%%

