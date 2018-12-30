"""Setup for down-frab-videos"""

# Use setuptools for these commands (they don't work well or at all
# with distutils).  For normal builds use distutils.
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='down-frab-videos',
    description="Download videos and lecture attachments from CCC events",
    long_description='Command line tool to download videos and lecture '
    'attachments for CCC events',
    #
    url='https://github.com/mfherbst/down-frab-videos',
    author='Michael F. Herbst',
    author_email="info@michael-herbst.com",
    license="GPL v3",
    #
    packages=['down_frab_videos'],
    scripts=["bin/down-frab-videos"],
    version='0.5.5',
    #
    python_requires='>=3',
    install_requires=[
        'beautifulsoup4 (>= 4.2)',
        'lxml (>= 4.2)',
        'pycountry (>= 17.5.14)',
        'PyYAML (>= 3.12)',
        'requests (>=2.2)',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Intended Audience :: Information Technology',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Operating System :: Unix',
    ],
)
