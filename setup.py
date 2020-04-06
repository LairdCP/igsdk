# coding: utf-8
import sys
from setuptools import setup, find_packages

NAME = "igsdk"
VERSION = "3.0.0"

CODE_FOLDER = 'python'

setup(
    name=NAME,
    version=VERSION,
    description="Laird Sentrius IGSDK",
    license="MIT",
    url="https://github.com/LairdCP/igsdk",
    install_requires=[],
    package_dir={'': CODE_FOLDER},
    packages=find_packages(CODE_FOLDER),
    include_package_data=True,
)
