# vi: set et ts=4 sw=4 sts=4:
import yaml
import datetime
import sys
import os
import re


class config:
    __default_config = {
        "settings": {
            "video_preference": ["webm-hd", "h264-hq", "h264-hd"],
        },
        "events": {
            "32c3": {
                "starts": "2015-12-26",
                "name": "32c3",
                "fahrplan": "https://events.ccc.de/congress/2015/Fahrplan",
                "media_prefix": "https://cdn.media.ccc.de/congress/2015",
            },
            "mrmcd2015": {
                "starts": "2015-09-04",
                "name": "mrmcd2015",
                "fahrplan": "https://mrmcd.net/events_page/2015/fahrplan",
                "media_prefix": "https://cdn.media.ccc.de/events/mrmcd/mrmcd15",
            },
            "camp2015": {
                "starts": "2015-08-13",
                "name": "camp2015",
                "fahrplan": "https://events.ccc.de/camp/2015/Fahrplan",
                "media_prefix": "https://cdn.media.ccc.de/events/camp2015",
            },
            "mrmcd2016": {
                "starts": "2016-09-02",
                "name": "mrmcd2016",
                "fahrplan": "https://2016.mrmcd.net/fahrplan",
                "media_prefix": "http://cdn.media.ccc.de/events/mrmcd/mrmcd16",
            },
            "33c3": {
                "starts": "2016-12-27",
                "name": "33c3",
                "fahrplan": "https://fahrplan.events.ccc.de/congress/2016/Fahrplan",
                "media_prefix": "https://cdn.media.ccc.de/congress/2016"
            },
            "EH2017": {
                "starts": "2017-04-14",
                "name": "EH2017",
                "media_prefix": "http://cdn.media.ccc.de/events/eh2017",
                "fahrplan": "https://eh17.easterhegg.eu/Fahrplan",
            },
            "GPN17": {
                "starts": "2017-05-25",
                "name": "GPN17",
                "media_prefix": "https://cdn.media.ccc.de/events/gpn/gpn17",
                "fahrplan": "https://entropia.de/GPN17:Fahrplan",
                "json_location": "https://entropia.de/GPN17:Fahrplan:JSON?action=raw",
            },
            "SHA2017": {
                "starts": "2017-08-05",
                "name": "Still hacking away",
                "fahrplan": "https://program.sha2017.org",
                "media_prefix": "https://cdn.media.ccc.de/events/SHA2017",
            },
            "mrmcd2017": {
                "starts": "2017-09-01",
                "name": "mrmcd2017",
                "fahrplan": "https://cfp.mrmcd.net/2017",
                "media_prefix": "http://cdn.media.ccc.de/events/mrmcd/mrmcd17",
            },
            "34c3": {
                "starts": "2017-12-27",
                "name": "34c3",
                "fahrplan": "https://fahrplan.events.ccc.de/congress/2017/Fahrplan/",
                "media_prefix": "https://cdn.media.ccc.de/congress/2017",
            },
            "GPN18": {
                "starts": "2018-05-10",
                "name": "GPN18",
                "media_prefix": "https://cdn.media.ccc.de/events/gpn/gpn18",
                "fahrplan": "https://entropia.de/GPN18:Fahrplan",
                "json_location": "https://entropia.de/GPN18:Fahrplan:JSON?action=raw",
            },
            "mrmcd2018": {
                "starts": "2018-09-07",
                "name": "mrmcd2018",
                "fahrplan": "https://talks.mrmcd.net/2018",
                "media_prefix": "http://cdn.media.ccc.de/events/mrmcd/mrmcd18",
            },
            "35c3": {
                "starts": "2018-12-27",
                "name": "35c3",
                "fahrplan": "https://fahrplan.events.ccc.de/congress/2018/Fahrplan/",
                "media_prefix": "https://cdn.media.ccc.de/congress/2018",
            },
        },
    }

    __default_config_comments = {
        "settings": {
            "video_preference": "List of strings, giving the order of "
                                "preference for the file formats to download",
        },
        "events": {
            "32c3": {
                "starts": "When does the event start? Format: yyyy-mm-dd",
                "name": "The name of the event (should be the same as the key)",
                "fahrplan": "Prefix url to the main Fahrplan page without "
                            "index.html or similar. Expects a schedule.json "
                            "to be directly below this path.",
                "json_location": "A direct link to the schedule JSON.",
                "media_prefix": "Prefix url to the location of the media file. "
                                "This url should present a list of available file "
                                "formats.",
            },
        },
    }

    def __init__(self, file=None):
        """
        Parse the config from a file

        If file is None the defaults will be used, else the defaults will be
        updated with the parsed data
        """

        self.__settings = config.__default_config["settings"]
        self.__events = config.__default_config["events"]
        if file is not None:
            if isinstance(file, str):
                with open(file) as f:
                    parsed = yaml.load(f)
            else:
                parsed = yaml.load(file)

            try:
                self.__settings = parsed["settings"]
            except KeyError:
                pass

            try:
                self.__events = parsed["events"]
            except KeyError:
                pass

        # determine most recent event:
        mrecent = datetime.timedelta(10*365)
        mname = ""
        for name, event in self.events.items():
            try:
                eventdate = datetime.date(*map(int, event["starts"].split("-")))
            except ValueError as e:
                raise ValueError("Date format for starts field of event \"" + name +
                                 "\" is not valid: " + str(e))

            offset = datetime.date.today() - eventdate
            if offset < mrecent and offset.total_seconds() >= 0:
                mrecent = offset
                mname = name

        self.__most_recent_event = self.events[mname]

        # make sure that the key and the name field are identical
        self.__most_recent_event["name"] = mname

    @property
    def settings(self):
        """Return the dictionary giving the settings"""
        return self.__settings

    @property
    def events(self):
        """
        Return the dictionary containing the events.
        """
        return self.__events

    @property
    def most_recent_event(self):
        return self.__most_recent_event

    @staticmethod
    def default_config():
        """Returns default config as a string"""

        string = "---\n"
        string += "#\n"
        string += "# Config file for " + os.path.basename(sys.argv[0]) + "\n"
        string += "#\n"
        string += "# The keys have the following meanings:\n"

        comments = yaml.safe_dump(config.__default_config_comments,
                                  default_flow_style=False)
        # add comment symbols in front of each new line:
        string += re.sub("\n", "\n# ", re.sub("^", "# ", comments))
        string += "\n########\n\n"

        # add actual fields:
        string += yaml.safe_dump(config.__default_config, default_flow_style=False)
        string += "..."
        return string
