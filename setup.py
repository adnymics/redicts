from setuptools import find_packages
from setuptools import setup

setup(
    name='redict',
    version='1.0.0',
    description='save arbitary nested python dicts and objects in redis',
    url='http://github.com/adnymics/redict',
    author='adnymics',
    author_email='dev@adnymics.com',
    license='???',
    packages=find_packages('redict'),
    package_dir={"": "src"},
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)
