#!/usr/bin/env python3
# vi: set et ts=4 sw=4 sts=4:

# os and sys interaction
import sys
import subprocess
import os

# misc
import itertools
import re

# getting and parsing config and input
import argparse
import json
import yaml

# web stuff
import requests
from bs4 import BeautifulSoup

# date and time
import datetime
import time

# Formatting 
import textwrap

class config:
    __default_config = {
        "settings": {
            "video_preference": [ "webm-hd", "h264-hq", "h264-hd" ], 
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
        },
    }

    __default_config_comments = {
        "settings": {
            "video_preference": "List of strings, giving the order of preference for the file formats to download",
        },
        "events": {
            "32c3": {
                "starts": "When does the event start? Format: yyyy-mm-dd",
                "name": "The name of the event (should be the same as the key)",
                "fahrplan": "Prefix url to the main Fahrplan page without index.html or similar. Expects a schedule.json to be directly below this path.",
                "media_prefix": "Prefix url to the location of the media file. This url should present a list of available file formats.",
            },
        },
    }

    def __init__(self,file=None):
        """
        Parse the config from a file

        If file is None the defaults will be used, else the defaults will be 
        updated with the parsed data
        """

        self.__settings = config.__default_config["settings"]
        self.__events = config.__default_config["events"]
        if file is not None:
            if isinstance(file,str):
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
                eventdate = datetime.date(*map(int,event["starts"].split("-")))
            except ValueError as e:
                raise ValueError("Date format for starts field of event \""  +name + "\" is not valid: " + str(e))

            offset = datetime.date.today() - eventdate
            if offset < mrecent:
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

        comments = yaml.safe_dump(config.__default_config_comments,default_flow_style=False)
        # add comment symbols in front of each new line:
        string += re.sub("\n","\n# ", re.sub("^","# ", comments))
        string += "\n########\n\n"
        
        # add actual fields:
        string += yaml.safe_dump(config.__default_config,default_flow_style=False)
        string += "..."
        return string

class UnknownTalkIdError(Exception):
    """
    Thrown if a talkid is not valid or cannot be found in the internal data
    """
    def __init__(self,message):
        super(UnknownTalkIdError, self).__init__(message)

class InvalidFahrplanData(Exception):
    """
    Thrown if the downloaded Fahrplan file is not valid
    """
    def __init__(self,message):
        super(InvalidFahrplanData, self).__init__(message)

def get_format_list(media_prefix):
    """
    Check which media formats are available and return a list with them
    """
    errorstring = "Could not download list of media formats from \"" + media_prefix + "/" + "\""
    format_list=[]
    try:
        req = requests.get(media_prefix + "/")
    except IOError as e:
        raise IOError(errorstring + ": " + str(e))

    if (not req.ok):
        raise IOError(errorstring + ".")

    soup = BeautifulSoup(req.content,"lxml")
    for link in soup.find_all('a'):
        hreftext = link.get('href')
        if (hreftext.rfind("/") > 0) and link.string != "Parent Directory":
            #is a valid media format since it contains a / and is not the parent
            format_list.append(hreftext[:-1])
    return format_list

class media_url_builder:
    """ Class downloading the list of media files of the given format"""

    def __init__(self,media_prefix, video_format):
        self.cached_list=[]
        self.media_prefix = media_prefix
        self.video_format = video_format

        errorstring = "Could not download list of media files from \"" + media_prefix + "/" + video_format + "\""
        try:
            req = requests.get(media_prefix + "/" + video_format)
        except IOError as e:
            raise IOError(errorstring + ": " + str(e))
                
        if (not req.ok):
            raise IOError(errorstring + ".")

        soup = BeautifulSoup(req.content,"lxml")
        for link in soup.find_all('a'):
            hreftext = link.get('href')
            if (hreftext.rfind(".") > 0):
                #is a valid media link since it contains a .
                self.cached_list.append(hreftext)

    def get_url(self,talkid):
        """
        Get the media url from the talkid

        raises a UnknownTalkIdError if the file was not found on the server
        """
        for link in self.cached_list:
            if (link.find("-"+str(talkid)+"-") > 0):
                return self.media_prefix+"/" + self.video_format + "/"  + link
        raise UnknownTalkIdError(talkid)

class fahrplan_data:
    """
    Get json data from Fahrplan and extract relevant part.
    
    fahrplan_string can be an url or a file on the local disk 
    """

    def __get_fahrplan_as_text(self,fahrplan_json):
        if os.path.exists(fahrplan_json):
            try:
                with open(fahrplan_json) as f:
                    return f.read()
            except IOError as e:
                raise IOError("Could not get the Fahrplan from \"" + fahrplan_json + "\": "  +str(e))
        else:
            errorstring = "Could not get the Fahrplan from \"" + fahrplan_json + "\""
            try:
                    req = requests.get(fahrplan_json)
            except IOError as e:
                raise IOError(errorstring + ": " + str(e))
                
            if (not req.ok):
                raise IOError(errorstring + ".")

            return req.text

    def __init__(self,fahrplan_page):
        self.__location = fahrplan_page + "/schedule.json"
        self.base_page = fahrplan_page
        fahrplan_raw = json.loads(self.__get_fahrplan_as_text(self.location))

        try:
            schedule = fahrplan_raw['schedule']

            # extract some meta data:
            self.meta = dict()
            self.meta['version'] = schedule['version']
            self.meta['conference'] = schedule['conference']['title']
            self.meta['start'] = schedule['conference']['start']
            self.meta['end'] = schedule['conference']['end']

            # extract the lecture data:
            self.lectures = {}

            days = schedule['conference']['days']
            for day in days:
                # iterator over all talks on that day
                all_talks = itertools.chain(*day['rooms'].values())

                # insert them into the dictionary:
                self.lectures.update({ talk['id'] : talk for talk in all_talks })

        except KeyError as e:
            raise InvalidFahrplanData("Fahrplan file \"" + self.location + "\" is not in the expected format: Key \"" + str(e) + "\" is missing")

    @property
    def location(self):
        """
        Get the json file from which the fahrplan data in this object has been extracted.
        """
        return self.__location

def wget(url,folder=".",out=None):
    """
    Use wget to download an url into a specific folder.

    if out is not none, this output filename is used.
    """
    # TODO do this internally with requests or so.

    args = [ "wget", "--continue", "--show-progress" ]
    if out is not None:
        args.append("--output-document=" + str(out))
    args.append(url)

    return subprocess.call( args, cwd=folder )

class lecture_downloader:
    def __init__(self,fahrplan_data, media_url_builders):
        """
        Initialise a lecture downloader. It requires a Fahrplan_data object and a media_url_builder for each media type to be
        downloaded. The latter is supplied in the list media_url_builders
        """

        self.fahrplan_data = fahrplan_data
        self.media_url_builders = media_url_builders

    def info_text(self,talkid):
        try:
            # the fahrplan lecture object:
            lecture = self.fahrplan_data.lectures[talkid]
        except KeyError as e:
            raise UnknownTalkIdError(talkid)

        try:
            ret  = lecture['title'] + '\n'
            ret += lecture['subtitle'] + '\n\n'

            ret += "########################\n"
            ret += "#--     Abstract     --#\n"
            ret += "########################\n\n"
            ret += textwrap.fill(lecture['abstract'], width=80)
            ret += "\n\n"

            ret += "########################\n"
            ret += "#--    Description   --#\n"
            ret += "########################\n\n"
            ret += textwrap.fill(lecture['description'], width=80)

            if len(lecture['links']) == 0:
                return ret

            ret += "\n\n"
            ret += "########################\n"
            ret += "#--       Links      --#\n"
            ret += "########################\n\n"

            #maximum length of description string:
            maxlength = max( [ len(x['title']) for x in lecture['links'] ])  
            maxlength = min(maxlength,37)

            for link in lecture['links']:
                ret += ("  - {0:" + str(maxlength) + "s}   {1}\n").format(link['title'],link['url'])

            return ret
        except KeyError as e:
            raise InvalidFahrplanData("Fahrplan file \"" + fahrplan_data.location + "\" is not in the expected format: Key \"" + str(e) + "\" is missing")

        return ret

    def download(self,talkid):
        try:
            # the fahrplan lecture object:
            lecture = self.fahrplan_data.lectures[talkid]
        except KeyError as e:
            raise UnknownTalkIdError(talkid)

        try:
            # folder into which to download everything:
            folder = lecture['slug']
        except KeyError as e:
            raise InvalidFahrplanData("Fahrplan file \"" + self.fahrplan_data.location + "\" is not in the expected format: Key \"" + str(e) + "\" is missing")

        # make dir
        if not os.path.isdir("./" + folder + "/"):
            os.mkdir("./" + folder + "/")

        # write info page:
        with open(folder+"/info_"+str(talkid)+".txt","w") as f:
            f.write( self.info_text(talkid))

        had_errors = False

        # download all media files:
        for builder in self.media_url_builders:
            try:
                url = builder.get_url(talkid)

                # TODO this is not ideal, do this with exceptions
                ret = wget(url,folder=folder)
                if ret != 0:
                    print("Could not download media file \"" + url + "\".")
                    had_errors = True

            except UnknownTalkIdError as e:
                print("Could not download format \"" + builder.video_format + "\" for talkid \"" + str(talkid) + "\".")
                had_errors = True


        # download attachments
        for att in lecture['attachments']:
            # build full url to file:
            url = self.fahrplan_data.base_page + "/"  + att['url']

            if url.find("attachments/original/missing.png") != -1:
                # marker file that the original attachment file has gone missing
                continue

            # download
            outfile = url[url.rfind("/")+1:]          # basename of the url
            outfile = outfile[:outfile.rfind("?")]    # ignore the tailling ?..... stuff
            ret = wget(url, folder=folder, out=outfile)
            if ret != 0:
                print("Could not download attachment \"" + att + "\" to file \"" + outfile 
                      + "\" in folder \""+ folder + "\".")
                had_errors = True

        #TODO go through links and download them if there are of a certain mime type

        if had_errors:
            raise UnknownTalkIdError(str(talkid))

def surround_text(text):
    no_hash = 8+len(text)
    string = no_hash * "#" + "\n"
    string += "#-- " + text + " --#\n"
    string += no_hash * "#"
    return string

def domain_from_url(url):
    # url should be of the form http://user:pass@domain/file

    split = url.split("/")
    if split[1] != "":
        raise ValueError("Not a valid url: \"" + url + "\"")

    return url.split("/")[2].split("@")[-1]

class errorlog:
    def __init__(self,path):
        self.ferr = None
        self.ferr = open(path,"a")
        self.ferr.write(surround_text(str(datetime.datetime.now())) + "\n")
        self.ferr.write("# List of talks not properly downloaded last run:\n")
        self.ferr.write("#    (use this file as listfile via\n")
        self.ferr.write("#     --listfile \"" + path + "\"\n")
        self.ferr.write("#    to rerun the download process with only the failed videos.)\n")

    def log(self,text):
        self.ferr.write(text + "\n")

    def __del__(self):
        if self.ferr is not None:
            self.ferr.close()

class idlist_reader:
    def __init__(self,path):
            if not os.path.exists(path):
                raise IOError("Path \"" + path + "\" does not exist.")

            with open(path) as f:
                try:
                    self.idlist = [ int(line.strip()) for line in f.readlines() if not line.startswith("#") ]
                except ValueError as e:
                    raise ValueError("Invalid idlist file \""+path+"\": " + str(e))

class timebarrier:
    """
    Class that makes sure (by using time.sleep) that there is a minimum
    time span of secs_delay between its construction and destruction
    """

    def __init__(self,secs_delay):
        """ Initialise the timebarrier class"""
        # The minimum time required at destrution:
        self.__req_endtime = secs_delay + time.time()

    @property
    def required_endtime():
        return self.__req_endtime

    def __del__(self):
        # calc sleep time in seconds, at least 0
        sleeptime = max(0,self.__req_endtime - time.time())
        time.sleep(sleeptime)

def do_list_events(conf):
    print("The following events are configured:")

    if len(conf.events) == 0:
        return
    
    # maximum length of all events:
    maxlen = max(map(len,conf.events))

    # print events:
    for name, event in sorted(conf.events.items()):
        extra = ""
        if name == conf.most_recent_event["name"]:
            extra = " -- most recent"
        print(("  - {0:" + str(maxlen) + "s} (started on {1}{2})").format(name,event["starts"],extra))

def add_args_to_parser(parser):
    """
    Add all required arguments to the parser object
    """
    # configuration:
    parser.add_argument("--config", metavar="config_file", type=str, default="~/.mfhBin/down_chaos_videos.yaml",
                        help="Path to the config file used to determine the appropriate urls for the chaos events, ...")
    parser.add_argument("--event", default=None, type=str, metavar="event",
                        help="Select a specific chaos event, by default the most recent, known event is selected.")
    parser.add_argument("--format", metavar="video_format", type=str, action='append', default=None,
                        help="The format in which the videos should be downloaded. "
                        "By default it downloads the available format of highest preference in the config file, "
                        "try --list-formats to list the available formats for the selected event. "
                        "May be given multiple times to specify more than one format to download.")

    # downloading:
    parser.add_argument("--listfile", metavar="listfile", type=str, default=None, 
                        help="The path to the file containing the talkids line-by-line.")
    parser.add_argument("--mindelay", metavar="seconds", type=int, default=3, help="Minimum delay between two downloads (to not annoy the media servers that much).")

    # other modes:
    parser.add_argument("--list-formats", action='store_true', default=False, help="List the available formats for the selected chaos event and exit.")
    parser.add_argument("--list-events", action='store_true', default=False, help="List the configured chaos events and exit.")
    parser.add_argument("--dump-config", action='store_true', 
                        help="Dump the default config to the file given via --config or the default location and exit.")

def parse_args_from_parser(parser):
    """
    Parse all args from the parser object required for this module
    Return the args parsed, raise SystemExit on any error.
    """
    args = parser.parse_args()

    if not (args.dump_config  or args.list_events or args.list_formats):
        args.download_mode = True

        if args.listfile is None:
            raise SystemExit("You need to supply --listfile or one of --list-formats, --list-events, --dump-config")

        if not os.path.exists(args.listfile):
            raise SystemExit("The list file \"" + args.listfile + "\" does not exist.")

    else:
        args.download_mode = False
        if args.listfile is not None:
            print("--listfile is ignored if one of --list-formats, --list-events, --dump-config is specified,"
                  "since no download will be done it these cases.")

    return args

if __name__ == "__main__":
    # 
    # args
    #
    parser = argparse.ArgumentParser(description="Download videos from the Fahrplan and media system used for chaos events.")
    add_args_to_parser(parser)
    args = parse_args_from_parser(parser)

    #
    # config
    #
    args.config = os.path.expanduser(args.config)

    if args.dump_config:
        with open(args.config, "w") as f:
            f.write(config.default_config())
        print("Wrote config to \"" + args.config + "\".")
        sys.exit(0)

    if os.path.exists(args.config):
        # config exists --> parse it:
        conf = config(args.config)
    else:
        # use defaults:
        conf = config()

    # 
    # Events
    #
    if args.list_events:
        do_list_events(conf)
        sys.exit(0)
  
    if args.event is None:
        selected_event = conf.most_recent_event
    else:
        selected_event = conf.events[args.event]

    # 
    # Formats
    #
    available_formats = get_format_list(selected_event["media_prefix"])

    if args.list_formats:
        print("Available media formats for " + selected_event["name"] + ":")
        for f in available_formats:
            print("  - " + f)
        sys.exit(0)

    if args.format is None or len(args.format) == 0:
        selected_formats = [ f for f in conf.settings["video_preference"] if (f in available_formats) ]
        if len(selected_formats) == 0:
            raise SystemExit("None of formats accepted by the user("+str(conf.settings["video_preference"])+") could be found for "
                             "the event \"" + selected_event["name"] + "\"." 
                             "Use --list-formats to view the list of available video formats.")
        selected_formats = [ selected_formats[0] ]
    else:
        for f in args.format:
            if not f in available_formats:
                raise SystemExit("The format \"" + f + "\" could not be found for the event \"" + selected_event["name"] + "\"."
                                 "Use --list-formats to view the list of available video formats.")
        selected_formats = args.format

    # 
    # Download videos
    #
    print(surround_text("Gathering lecture data for " + selected_event["name"]))
    try:
        print("   - Info about video files from \"" + domain_from_url(selected_event["media_prefix"]) + "\"")
        builders = [ media_url_builder(selected_event["media_prefix"], format) for format in selected_formats ]
    except IOError as e:
        raise SystemExit("Could not download list of media files: " + str(e))

    try:
        print("   - Fahrplan from \"" + domain_from_url(selected_event["fahrplan"]) + "\".")
        fahrplan = fahrplan_data(selected_event["fahrplan"])
    except IOError as e:
        raise SystemExit("Could not download Fahrplan: " + str(e))
    print("   - Finished: Got \"" + fahrplan.meta['conference'] + "\", version \"" + fahrplan.meta['version'] + "\"")

    # bundle fahrplan and builders into the downloader
    downloader = lecture_downloader(fahrplan,builders)

    # read the id list:
    try:
        idreader = idlist_reader(args.listfile)
    except IOError as e:
        raise SystemExit("Error reading the list file \"" + args.listfile + "\": " + str(e))
    except ValueError as e:
        raise SystemExit("Error reading the list file \"" + args.listfile + "\": " + str(e))

    # setup the error log
    try:
        errlog = errorlog(args.listfile + ".errors")
    except IOError as e:
        raise SystemExit("Error creating the errorlog file \"" + args.listfile + ".errors\": " + str(e))

    # download the ids:
    for talkid in idreader.idlist:
        print("\n" + surround_text(str(talkid)))
        timebarrier(args.mindelay)

        try:
            downloader.download(talkid)
        except UnknownTalkIdError as e:
            print("TalkId erroneous or unknown: " + str(e))
            errlog.log(str(talkid))
        except InvalidFahrplanData as e:
            print("Invalid Fahrplan data for TalkId " + str(talkid) + ": " + str(e))
            errlog.log(str(talkid))
