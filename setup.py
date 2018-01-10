from setuptools import setup

setup(
    name='redicts',
    version='1.0.0',
    description='save arbitary nested python dicts and objects in redis',
    url='http://github.com/adnymics/redicts',
    author='adnymics',
    author_email='dev@adnymics.com',
    license='???',
    package_dir={"": "src"},
    packages=["redicts"],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)
