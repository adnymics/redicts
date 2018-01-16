import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='redicts',
    version='1.0.4',
    description='Save arbitary nested python dicts and objects in redis',
    url='http://github.com/adnymics/redicts',
    author='adnymics',
    author_email='dev@adnymics.com',
    license='GPLv3',
    package_dir={"": "src"},
    packages=["redicts"],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    long_description=read("README.rst"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]
)
