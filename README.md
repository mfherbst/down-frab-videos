# down-frab-videos
Download videos and lecture attachments from events managed with the
[frab](https://github.com/frab/frab) system
(like the Chaos communication congress, MRMCD, Camp, ...)   

By default the most recent, known chaos event is considered and high-quality ``webm``
files are downloaded.
This can, however, be changed using the ``--event`` and ``--format`` flags respectively.
A list of configured events and available formats for a given event can be printed
(using flags ``--list-events`` and ``--list-formats``).
For a list of all flags the script understands, try
```
./down_frab_videos.py --help
```

When downloading a talk the script will not only download the recording,
but also some information from the frab Fahrplan as well.
This includes:
- The attached files
- The abstract and summary for the talk
- The list of links and references

In order to download talks, you just need to provide the script with a list of 4-digit talk ids. 
These should be listed line-by-line in a file, handed over to the script via ``--listfile``.
For example the file 
```
6258
# some crazy comment
6450
```
downloads the talks with ids ``6258`` and ``6450``.
For downloading only a small number of talks with the script the commandline syntax
```
./down_frab_videos.py --ids 6258 6450
```
is usually more convenient.

Some of the options configured via the commandline can be configured more permanently via
a configuration file as well.
To get started with this you should dump the defaults using
```
./down_frab_videos.py --dump-config
```
This will write a stub config to ``~/.config/down_frab_videos/config.yaml``.

## Requirements and Python dependencies
- Python >= 3.5
- [Beautiful Soup](https://pypi.python.org/pypi/beautifulsoup4)
- [json](https://pypi.python.org/pypi/json)
- [pycountry](https://pypi.python.org/pypi/pycountry/)
- [PyYAML](https://pypi.python.org/pypi/PyYAML)
- [requests](https://pypi.python.org/pypi/requests)
- subprocess
- textwrap
