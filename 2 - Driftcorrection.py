# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.5.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # 2 - Drift Correction
# This notebook implements and show cases the drift correction algorithm as described in section 4 of the paper. It uses cross correlation of all pairs of images after applying digital smoothing and edge detection filters to align Low Energy Electron Microscopy images with each other. When applied correctly, this allows for sub-pixel accurate image registration.
# This process is applied to the output of notebook 1, the detector corrected images

# +
import numpy as np
import os
import numba
import time
import dask

import dask.array as da
from dask.delayed import delayed
from dask.distributed import Client, LocalCluster
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib as mpl

import ipywidgets as widgets
from ipywidgets import interactive

from scipy.optimize import least_squares
import scipy.ndimage as ndi
import scipy.sparse as sp
from scipy.interpolate import interp1d

from skimage import filters

# Most relevant functions can be found in registration
from registration import *

plt.rcParams["figure.figsize"] = [12., 8.]
SAVEFIG = True
# -

cluster = LocalCluster(n_workers=1, threads_per_worker=8)
client = Client(cluster)
client.upload_file('registration.py')
client


def plot_stack(images, n, grid=False):
    """Plot the n-th image from a stack of n images.
    For interactive use with ipython widgets"""
    im = images[n, :, :].compute()
    plt.figure(figsize=[12,10])
    plt.imshow(im.T, cmap='gray', vmax=im.max())
    if grid:
        plt.grid()
    plt.show()

# +
# A bunch of constants

folder = r'./data'

# Pick the dataset to apply driftcorrection to and the range
name = '20171120_160356_3.5um_591.4_IVhdr'
start, stop = 42, -1 #BF

# name = '20171120_215555_3.5um_583.1_IVhdr_DF2'
# start, stop = 0, -1 #DF

# A stride larger than 1 takes 1 every stride images of the total dataset. 
# This decreases computation time by a factor of stride**2, but decreases accuracy
stride = 5
# dE is the blocksize used by dask, the number of images computed for at once.
dE = 10

Eslice = slice(start, stop, stride)

# Grab a window of 2*fftsize around the center of the picture
fftsize=256 * 2 // 2
z_factor = 1
# -

dataset = xr.open_dataset(os.path.join(folder, name + '_detectorcorrected.nc'), chunks={'time': dE})
original = dataset.Intensity.data

# For interactive use we can view the original data
interactive(lambda n: plot_stack(original, n), 
            n=widgets.IntSlider(original.shape[0]//2, 0, original.shape[0]-1, 1, continuous_update=False)
           ) 

# Get extent, by any means necessary. Example with center and square of fftsize
center = [dim//2 for dim in original.shape[1:]]
extent = (center[0]-fftsize, center[0]+fftsize, center[1]-fftsize, center[1]+fftsize)
fftsize = max(extent[1]-extent[0], extent[3]-extent[2]) //2 # used in calc half matrices

# Step 1 to 3 of the algorithm as described in section 4 of the paper.
sobel = Reg.crop_and_filter_extent(original[Eslice, ...].rechunk({0: dE}), extent, sigma=sigma)
#sobel = crop_and_filter(original[Eslice,...].rechunk({0:dE}), sigma=3, finalsize=2*fftsize)
sobel = (sobel - sobel.mean(axis=(1,2), keepdims=True)) #.persist()  
sobel

# Step 4 of the algorithm as described in paper.
Corr = dask_cross_corr(sobel)
Corr

# +
# Plot combination of original images, filtered images, crosscorrelation 
# for illustration purposes
def plot_corr(i,j, save=SAVEFIG):
    #fig = plt.figure(figsize=(8.2, 3.5), constrained_layout=True)
    fig = plt.figure(figsize=(4, 7), constrained_layout=True)
    fig.set_constrained_layout_pads(hspace=0.0, wspace=0.06)
    #gs = mpl.gridspec.GridSpec(2, 3,
    #                   width_ratios=[1, 1, 2.9],
    #                   #height_ratios=[4, 1]
    #                   )
    
    gs = mpl.gridspec.GridSpec(3, 2,
                       height_ratios=[1, 1, 1.8],
                               figure=fig,
                       )
    
    ax0 = plt.subplot(gs[0, 0])
    ax1 = plt.subplot(gs[1, 0])
    ax2 = plt.subplot(gs[0, 1])
    ax3 = plt.subplot(gs[1, 1])
    ax4 = plt.subplot(gs[2, :]) #2grid((2, 4), (0, 2), rowspan=2, colspan=2)
    ax0.imshow(original[i*stride + start,(640-fftsize):(640+fftsize),(512-fftsize):(512+fftsize)].T, 
               cmap='gray', interpolation='none')
    ax0.set_title(f'i={i*stride + start}')
    ax1.imshow(sobel[i,...].T, cmap='gray')
    ax2.imshow(original[j*stride + start,(640-fftsize):(640+fftsize),(512-fftsize):(512+fftsize)].T,
               cmap='gray', interpolation='none')
    ax2.set_title(f'j={j*stride + start}')
    ax3.imshow(sobel[j,...].T,
               cmap='gray', interpolation='none')
    im = ax4.imshow(Corr[i,j,...].compute().T, extent=[-fftsize, fftsize, -fftsize, fftsize], interpolation='none')
    ax4.axhline(0, color='white', alpha=0.5)
    ax4.axvline(0, color='white', alpha=0.5)
    for ax in [ax2, ax3]:
        ax.yaxis.set_label_position("right")
        ax.tick_params(axis='y', labelright=True, labelleft=False)
    plt.colorbar(im, ax=ax4)
    if save:
        #Saving Figure for paper.
        plt.savefig('autocorrelation.pdf', dpi=300)
    plt.show()
    return fig

widget = interactive(plot_corr, 
            i=widgets.IntSlider(58-start,0,sobel.shape[0]-1,1, continuous_update=False), 
            j=widgets.IntSlider(100-start,0,sobel.shape[0]-1,1, continuous_update=False),
            save=SAVEFIG
           )
display(widget)
# -

# Step 5 of the algorithm
weights, argmax = max_and_argmax(Corr)

# Do actual computations; get a cup of coffee. If this takes to long, consider increasing stride to reduce the workload, at the cost of accuracy
t = time.monotonic()
W, DX_DY = calculate_halfmatrices(weights, argmax, fftsize=fftsize)
print(time.monotonic()-t)

# Step 6 of the algorithm
w_diag = np.atleast_2d(np.diag(W))
W_n = W / np.sqrt(w_diag.T*w_diag)

# +
# Plot W, DX and DY to pick a value for W_{min} (Step 7 of algorithm)
def plot_masking(min_normed_weight, save=SAVEFIG):
    extent = [start, stop, stop, start]
    fig, axs = plt.subplots(1, 3, figsize=(8, 2.5), constrained_layout=True)
    im = {}
    im[0] = axs[0].imshow(DX_DY[0], cmap='seismic', extent=extent, interpolation='none')
    im[1] = axs[1].imshow(DX_DY[1], cmap='seismic', extent=extent, interpolation='none')
    im[2] = axs[2].imshow(W_n - np.diag(np.diag(W_n)), cmap='inferno', 
                          extent=extent, clim=(0.0, None), interpolation='none')
    axs[0].set_ylabel('$j$')
    fig.colorbar(im[0], ax=axs[:2], shrink=0.82, fraction=0.1)
    axs[0].contourf(W_n, [0, min_normed_weight], 
                    colors='black', alpha=0.6, 
                    extent=extent, origin='upper')
    axs[1].contourf(W_n, [0, min_normed_weight], 
                    colors='black', alpha=0.6, 
                    extent=extent, origin='upper')
    CF = axs[2].contourf(W_n, [0, min_normed_weight], 
                         colors='white', alpha=0.2, 
                         extent=extent, origin='upper')
    cbar = fig.colorbar(im[2], ax=axs[2], shrink=0.82, fraction=0.1)
    cbar.ax.fill_between([0,1], 0, min_normed_weight, color='white', alpha=0.2)
    for i in range(3):            
        axs[i].set_xlabel('$i$')
        axs[i].tick_params(labelbottom=False, labelleft=False)  
    axs[0].set_title('$DX_{ij}$')
    axs[1].set_title('$DY_{ij}$')
    axs[2].set_title('$W_{ij}$')
    if save:
        plt.savefig('shiftsandweights.pdf', dpi=300)
    plt.show()
    return min_normed_weight

widget = interactive(plot_masking, 
                     min_normed_weight=widgets.FloatSlider(value=0.15, min=0., max=1, 
                                                      step=0.01, continuous_update=False),
                     save=SAVEFIG
               )
display(widget)
# -

# Part two of step 7 of the algorithm
min_norm = widget.result
nr = np.arange(W.shape[0])*stride + start
coords, weightmatrix, DX, DY, row_mask = threshold_and_mask(min_norm, W, DX_DY, nr)
#Step 8 of the algorithm: reduce the shift matrix to two vectors of absolute shifts
dx, dy = calc_shift_vectors(DX, DY, weightmatrix)
plt.plot(coords, dx, '.', label='dx')
plt.plot(coords, dy, '.', label='dy')
plt.xlabel('n')
plt.ylabel('shift (pixels)')
plt.legend()

# Interpolate the shifts for all values not in coords
shifts = np.stack(interp_shifts(coords, [dx, dy], n=original.shape[0]), axis=1)
neededMargins = np.ceil(shifts.max(axis=0)).astype(int)
shifts = da.from_array(shifts, chunks=(dE,-1))
shifts


# +
#Step 9, the actual shifting of the original images

#Inferring output dtype is not supported in dask yet, so we need original.dtype here.
@da.as_gufunc(signature="(i,j),(2)->(i,j)", output_dtypes=original.dtype, vectorize=True)
def shift_images(image, shift):
    """Shift `image` by `shift` pixels."""
    return ndi.shift(image, shift=shift, order=1)

padded = da.pad(original.rechunk({0:dE}), 
                ((0, 0), 
                 (0, neededMargins[0]), 
                 (0, neededMargins[1])
                ),
                mode='constant'
               )
corrected = shift_images(padded.rechunk({1:-1, 2:-1}), shifts)
# -

# Do an interactive viewer to inspect the results
interactive(lambda n: plot_stack(corrected, n, grid=True), 
            n=widgets.IntSlider(corrected.shape[0]//4,0,corrected.shape[0]-1,1, continuous_update=False)
           ) 

# ## Saving data
# Save the resulting data in a new netCDF file

xrcorrected = dataset.reindex({'x': np.arange(0, dataset.x[1]*corrected.shape[1], dataset.x[1]), 
                               'y': np.arange(0, dataset.y[1]*corrected.shape[2], dataset.y[1])})
xrcorrected.Intensity.data = corrected
xrcorrected.Intensity.attrs['DriftCorrected'] = 'True'
xrcorrected.to_netcdf(os.path.join(folder, name + '_driftcorrected.nc'))

# Or, save the results to zarr
import zarr
from numcodecs import Blosc
compressor = Blosc(cname='zstd', clevel=1, shuffle=Blosc.SHUFFLE)
corrected.to_zarr(os.path.join(folder, name + '_driftcorrected.zarr'), 
                  overwrite=True, compressor=compressor)

#Or, although parallel access to HDF5 is hard, so go single process, save to hdf5
with dask.config.set(scheduler='threads'):  
    corrected.to_hdf5(os.path.join(folder, name + '_driftCorrected.h5', '/Intensity')
