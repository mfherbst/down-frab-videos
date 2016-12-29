# down-frab-videos
Download videos and lecture attachments from events managed with the
[frab](https://github.com/frab/frab) system
(like the Chaos communication congress, MRMCD, Camp, ...)   

By default the most recent, known chaos event is considered and high-quality ``webm``
files are downloaded.
This can, however, be changed using the ``--event`` and ``--format`` flags respectively.
A list of configured events and available formats for a given event can be printed as well.

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

The script can be configured for downloading other talks or media formats via a
configuration file as well.
If you want to personalise it, you should probably start by dumping the default configuration somewhere
(use ``--config`` and ``--dump`` for this)
