from PyQt5 import QtCore
import numpy as np

# axes_to_rect from pytwtools, (c) Tobias Witting
# updated to allow independent vertical binning factors
def axes_to_rect(x, y, xscale=1, yscale=1):
    """Return QRectF covering first and last elements of axis vectors.

    Args:
        x: array with one nonsingleton dimension
        y: array with one nonsingleton dimension
        xscale (scalar): Factor by which axes are multiplied.
        yscale (scalar): Factor by which axes are multiplied.

    Returns:
        QRectF with centre of top-left pixel x[0],y[0] and centre of lower-right pixel at x[-1],y[-1]
    """
    x = np.array(x).squeeze()
    y = np.array(y).squeeze()
    Dx = x[1] - x[0]
    Dy = y[1] - y[0]
    return QtCore.QRectF((x[0]-Dx/2)*xscale, (y[0]-Dy/2)*yscale, (x[-1]-x[0]+Dx)*xscale, (y[-1]-y[0]+Dy)*yscale)

# find_index from pytwtools, (c) Tobias Witting
# renamed parameters for clarity.
def find_index(Array, values, axis=None):
    """Return indices or values in array."""
    values = np.array(values)
    if np.size(values) > 1:
        ix = np.zeros(values.shape, dtype=int)
        for n in range(np.size(values)):
            ix[n] = int(np.abs(Array-values[n]).argmin(axis))
    else:
        ix = int(np.abs(Array-values).argmin(axis))

    return ix

def gaussian(x, fwhm=1, power=2):
    """Define a gaussian."""
    setSigma = fwhm / (2*(2*np.log(2))**(1/power))
    g = np.exp(-(np.abs(x)**power) / (2*setSigma**power))
    return g

def highpass(data,bdwth=100):
    fPOndf = np.fft.fft(data,axis=-1)
    filt = np.fft.fftshift(gaussian(np.arange(fPOndf.shape[-1],dtype=np.complex128)-fPOndf.shape[-1]//2,bdwth,8))
    POndf = (np.fft.ifft(fPOndf-fPOndf*filt,axis=-1))
    # Comment out next line to stop filtering
    return np.real(POndf)    
