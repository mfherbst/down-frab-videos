# down-frab-videos
Download videos and lecture attachments from events managed with the
[frab](https://github.com/frab/frab) system
or with the [pretalx](https://github.com/openeventstack/pretalx)
(like the Chaos communication congress, MRMCD, Camp, ...)   

By default the most recent, known chaos event is considered and high-quality ``webm``
files are downloaded.
This can, however, be changed using the ``--event`` and ``--format`` flags respectively.
A list of configured events and available formats for a given event can be printed
(using flags ``--list-events`` and ``--list-formats``).
For a list of all flags the script understands, try
```
down-frab-videos --help
```

When downloading a talk the script will not only download the recording,
but also some information from the frab Fahrplan as well.
This includes:
- The attached files
- The abstract and summary for the talk
- The list of links and references

In order to download talks, you just need to provide the script with a list of talk ids.
You can find the talkid in the url of your webbrowser.
For example the **frab** page with url ending in `events/8414.html`
has the talkid `8414` and the **pretalx** page ending in `talk/VHLTSN/`
corresponds to talkid `VHLTSN`.

You can either list the talkids
line-by-line in a file and hand that file over to the script via the argument
``--input-file``.
For example the file
```
6258
# some crazy comment
6450
```
downloads the talks with IDs ``6258`` and ``6450``.
For downloading only a small number of talks with the script the command line syntax
```
down-frab-videos 6258 6450
```
is usually more convenient.

Some of the options configured via the command line can be set more permanently via
a configuration file as well.
To get started with this you should dump the defaults using
```
down-frab-videos --dump-config
```
This will write a stub config to ``~/.config/down-frab-videos/config.yaml``.

## Installation
```
pip install down-frab-videos
```

## Requirements and Python dependencies
- Python >= 3.5
- [Beautiful Soup](https://pypi.python.org/pypi/beautifulsoup4)
- [json](https://pypi.python.org/pypi/json)
- [pycountry](https://pypi.python.org/pypi/pycountry/)
- [PyYAML](https://pypi.python.org/pypi/PyYAML)
- [requests](https://pypi.python.org/pypi/requests)
- subprocess
- textwrap
