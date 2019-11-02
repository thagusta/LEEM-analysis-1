# Quantitative Data Analysis for spectroscopic LEEM.

This repository contains the code to showcase the methods and algorithms presented in the paper 
"[Quantitative analysis of spectroscopic Low Energy Electron Microscopy data: High-dynamic range imaging, drift correction and cluster analysis](https://arxiv.org/abs/1907.13510)".

**This is still a WORK IN PROGRESS**

It is organized as a set of notebooks, reproducing the different techniques and algorithms as presented in the paper, as well as the Figures. The notebooks are in some cases supported by a separate Python file with library functions.
For human readable diffs, each notebook is shadowed by a Python file using [jupytext](https://github.com/mwouts/jupytext).

## Implementation
The code makes extensive use of [`dask`](https://dask.org/) for lazy and parallel computation, the N-D labeled arrays and datasets library [`xarray`](http://xarray.pydata.org/), as well as the usual components of the scipy stack such as `numpy`, `matplotlib` and `skimage`.

## Getting started
* Git clone or download this repository.
* Create a Python environment with the necessary packages, as documented in [requirements.txt](requirements.txt).
* Start a Jupyter notebook or Jupyter lab and have a look at the notebooks

## Data
The data will be available separately at https://researchdata.4tu.nl/. The [zeroth notebook](0_-_Data-download.ipynb) facilitates easy download of all related data.
