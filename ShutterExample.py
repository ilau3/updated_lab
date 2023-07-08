import time, sc10
try:
    bb.shutdown()
except:
    pass
bb = sc10.SC10()
# bb.openShutter()
# print('Shutter Open? '+str(bb.qopenShutter()))
bb.toggleShutter()
time.sleep(5)
# bb.closeShutter()
bb.toggleShutter()
print('Shutter Closed? '+str(bb.qcloseShutter()))


