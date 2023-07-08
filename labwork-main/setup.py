"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here,'README.rst')) as f:
    long_description=f.read()

dep_base=['numpy','scipy']
dep_hardware = ['pylablib','pipython']
dep_pyqt5=['pyqt5>=5.9','pyqtgraph']

setup(
    name='d35',
    version='1.0.1',
    description='Collection of modules to control experiments on the Leone Lab D35 Beamline',
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url='https://github.berkeley.edu/lbdrescher/d35',
    author='Lorenz B Drescher',
    author_email='lbdrescher@berkeley.edu',
    license="GPLv3",
    classifiers=[
    'Development Status :: 4 - Beta',
    'Operating System :: Microsoft :: Windows',
    'Intended Audience :: Developers',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    ],
    project_urls={
    'Source': 'https://github.berkeley.edu/lbdrescher/d35/',
    'Tracker': 'https://github.berkeley.edu/lbdrescher/d35/issues'
    },
    packages=find_packages(include=['d35*']),
    install_requires=dep_base+dep_pyqt5+dep_hardware,
    entry_points={'gui_scripts':['plotGasTransients=d35.collections.plotGasTransients:main',]}
    #extras_require={
    #    'devio-full':dep_devio_extra,
    #}
    # install_requires=dep_base,
    # extras_require={
    #     'extra':dep_extra,
    #     'devio':dep_devio,
    #     'devio-full':dep_devio+dep_devio_extra,
    #     'gui-pyqt5':dep_pyqt5,
    #     'gui-pyside2':dep_pyside2,
    # }
)