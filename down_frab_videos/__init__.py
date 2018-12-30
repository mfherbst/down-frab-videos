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

# web stuff
import requests
from bs4 import BeautifulSoup
import bs4

# date, time and language
import datetime
import time
import pycountry

# Output text formatting
import textwrap

from .config import config


__version__ = "0.5.5"
__licence__ = "GPL v3"
__authors__ = "Michael F. Herbst"
__email__ = "info@michael-herbst.com"
__package__ = "down-frab-videos"
__upstream__ = "https://github.com/mfherbst/down-frab-videos"


class UnknownTalkIdError(Exception):
    """
    Thrown if a talkid is not valid or cannot be found in the internal data
    """
    def __init__(self, message):
        super(UnknownTalkIdError, self).__init__(message)


class InvalidLanguagesError(Exception):
    """
    Thrown if a list of language ids is unknown or invalid
    """
    def __init__(self, message):
        super(InvalidLanguagesError, self).__init__(message)


class InvalidFahrplanData(Exception):
    """
    Thrown if the downloaded Fahrplan file is not valid
    """
    def __init__(self, message):
        super(InvalidFahrplanData, self).__init__(message)


class InvalidMediaPageError(Exception):
    """
    Thrown if the media page is off an unknown format
    """
    def __init__(self, short_message, long_message):
        super(InvalidMediaPageError, self).__init__(long_message)
        self.short_message = short_message
        self.long_message = long_message


def wrap_bs4(content):
    """
    Wrapper around BeautifulSoup to test multiple parsers
    """
    known_parsers = ["lxml", "html5lib", "html.parser"]
    for parser in known_parsers:
        try:
            return BeautifulSoup(content, parser)
        except bs4.FeatureNotFound:
            print("Warning: could not parse with {}, "
                  "check your installation. ".format(parser))
            if parser != known_parsers[-1]:
                print("Falling back to next known parser.")

    raise SystemExit("Could not apply any html parser")


def get_format_list(media_prefix):
    """
    Check which media formats are available and return a list with them
    """
    errorstring = "Could not download list of media formats from \"" + \
                  media_prefix + "/" + "\""
    format_list = []

    user_agent = __package__ + " " + __version__ + " (see " + __upstream__ + ")"
    try:
        req_headers = {
            'User-Agent': user_agent,
            'From': __upstream__,
        }

        req = requests.get(media_prefix + "/", headers=req_headers)
    except IOError as e:
        raise IOError(errorstring + ": " + str(e))

    if (not req.ok):
        raise IOError(errorstring + ".")

    soup = wrap_bs4(req.content)
    for link in soup.find_all('a'):
        hreftext = link.get('href')
        if (hreftext.rfind("/") > 0) and hreftext[:-1] != "..":
            # is a valid media format since it contains a / and is not the parent
            format_list.append(hreftext[:-1])
    return format_list


# TODO Rewrite this class. It has actually become some sort of parser for the
#      media.ccc.de page. We could easily generalise it to contain a parsed version
#      of the full page or all media files for the event or so ...
#      and it should really go to a separate file.
class media_url_builder:
    """Class parsing the list of media files of the given file format

        We assume that all of the links have the form
            event-id-lang1-lang2-...-Title_format.extension
        where
            event   String describing the event
            id      TalkId
            lang1, lang2 ...
                    ISO 639-1 or ISO 639-3 language codes which describe the language
                    of the audio tracks on this file
            Title   Capitalised title of the talk
            format  The file format
            extension  The extension of the file format
        The precise language code differs for various chaos events (sigh)
        and is auto-determined.

        raise_on_error    If the script detects that the media page is erroneous or
                          inconsistent, should it skip the entries which cannot be
                          parsed (False, default) or raise an InvalidMediaPageError
                          (True)
    """

    def __init__(self, media_prefix, video_format, raise_on_error=False):
        self.media_prefix = media_prefix
        self.video_format = video_format

        user_agent = __package__ + " " + __version__ + " (see " + __upstream__ + ")"
        errorstring = "Could not download list of media files from \"" + media_prefix + \
                      "/" + video_format + "\""
        try:
            req_headers = {
                'User-Agent': user_agent,
                'From': __upstream__,
            }

            req = requests.get(media_prefix + "/" + video_format, headers=req_headers)
        except IOError as e:
            raise IOError(errorstring + ": " + str(e))

        if (not req.ok):
            raise IOError(errorstring + ".")

        # dictionary which contains a parsed version of the media page.
        # roughly follows
        # { talkid : {
        #       "event":       "32c3"
        #       # langs for which audio tracks exist in ISO 639-3 format
        #       "languages":   [ "lang1", "lang2", "lang3" ],
        #       "langmap":      {
        #                        "deu-eng":  {
        #                                     "url": "http:// .... ",
        #                                     "languages": [ "deu", "eng" ]
        #                                    },
        #                        "eng":      {
        #                                     "url": "http:// .... ",
        #                                     "languages": [ "eng" ],
        #                                    },
        #                      }
        #       }
        # }
        self.cached = dict()

        errors = False
        soup = wrap_bs4(req.content)
        for link in soup.find_all('a'):
            hreftext = link.get('href')
            if hreftext.rfind(".") > 0 and len(hreftext) > 5:
                # is a valid media link since it contains a . and a -
                try:
                    self.__parse_link(hreftext, self.cached)
                except InvalidMediaPageError as e:
                    # TODO It feels a little wrong to have print statements in this class
                    #      Clean this up later ...
                    if not raise_on_error:
                        errors = True
                        print("      ... skipping \"" + hreftext + "\" (" +
                              e.short_message + ")")
                    else:
                        raise

        if errors:
            print("\n      Note: The skipped files could not be parsed and will not be "
                  "available")
            print("            for download. Either patch this script or download them "
                  "manually.\n")

        del soup

    def __list_to_langmap_key(li):
        """Take a list and return the key needed for lookup
           into the langmap dictionaries of the talks, which returns
           the file which contains those languages.
        """
        li.sort()
        return "-".join(li)

    def __determine_iso_639_3_key():
        """ Determine the key needed for accessing ISO 639-3
            language codes using pycountry.
        """
        # Different version of pycountry seem to use different keys.
        # Try a couple (Note: all ISO639-2T codes are ISO639-3 codes
        # as well)
        for key3 in ["alpha_3", "iso639_3_code", "terminology", "iso639_2T_code", ]:
            try:
                ret = pycountry.languages.get(**{key3: "deu"})
                if ret is None:
                    continue
                return key3
            except KeyError:
                continue
        raise SystemExit("Could not determine pycountry iso_639_3 key")

    def __determine_iso_639_1_key():
        """ Determine the key needed for accessing ISO 639-1
            language codes using pycountry.
        """
        # Different version of pycountry seem to use different keys.
        # Try a couple (Note: all ISO639-2T codes are ISO639-3 codes
        # as well)
        for key2 in ["alpha_2", "alpha2", "iso639_1_code", ]:
            try:
                ret = pycountry.languages.get(**{key2: "de"})
                if ret is None:
                    continue
                return key2
            except KeyError:
                continue
        raise SystemExit("Could not determine pycountry iso_639_1 key")

    def __parse_languages(link, splitted):
        """ Take a splitted link and return the parsed
            language set.
        """
        languages = set()  # The parsed language list

        # The parameters for parsing the language codes for
        # this talk.
        # Yes in some events the language code standard used
        # changes from talk to talk ...
        if len(splitted[2]) == 2:
            lang_standard = "iso639_1"
            lang_inkey = media_url_builder.__determine_iso_639_1_key()
            lang_outkey = media_url_builder.__determine_iso_639_3_key()
            lang_len = 2
        elif len(splitted[2]) == 3:
            lang_standard = "iso639_3"
            lang_inkey = media_url_builder.__determine_iso_639_3_key()
            lang_outkey = lang_inkey
            lang_len = 3
        else:
            raise InvalidMediaPageError("invalid language code",
                                        "Could not determine language code from "
                                        + "language string \"" + splitted[2] + "\""
                                        + " in link \"" + link + "\".")

        for part in splitted[2:]:
            if part[0].isupper() or part[0].isdigit():
                # We found an upper case or a number
                # i.e. we found the title.
                break

            errormsg = ("encountered in link \"" + link + "\": \"" + part +
                        "\". We expect that the languages follow the talkid and "
                        "that the title follows the languages. The title "
                        "should be indicated by an upper case or a number. "
                        "Please check that this is the case.")

            if not part[0].islower():
                raise InvalidMediaPageError("invalid language code",
                                            "Language code which does not start with "
                                            "a lower case character " + errormsg)

            # Language code remapping ... the VOC is really not consistent
            lang_remap = {"chi": "zhn"}
            if part in lang_remap:
                part = lang_remap[part]

            try:
                langobject = pycountry.languages.get(**{lang_inkey: part})
            except KeyError:
                langobject = None

            if langobject is not None:
                languages.add(getattr(langobject, lang_outkey))
            else:
                if len(part) > lang_len and len(languages) > 0:
                    # Probably this is a title which is lower-cased
                    # (Yes those actually do exist as well ... )
                    # So we will silently ignore it and break out
                    break
                else:
                    raise InvalidMediaPageError("invalid language code",
                                                "Invalid " + lang_standard +
                                                " language code \"" +
                                                part + "\" " + errormsg)

        if len(languages) == 0:
            raise InvalidMediaPageError("no languages found",
                                        "Did not find a single language for link \"" +
                                        link + "\"")

        return languages

    def __parse_link(self, link, outdict):
        """Parses a link and adds the appropriate entry to the
           output dictionary outdict
        """
        splitted = link.split("-")
        talkdict = {}

        if len(splitted) < 4:
            raise InvalidMediaPageError("failed to parse link",
                                        "Could not split link: \"" + link + "\"")

        # event-id-lang1-lang2-...-Title_format.extension
        try:
            talkid = int(splitted[1])
            talkdict = outdict.setdefault(talkid, dict())
            talkdict["talkid"] = talkid
        except ValueError:
            raise InvalidMediaPageError("invalid talkid", "Could not determine talkid "
                                        "in link: \"" + link + "\"")

        if splitted[0] != talkdict.setdefault("event", splitted[0]):
            raise InvalidMediaPageError("inconsistent information",
                                        "The event string of multiple files of the "
                                        + "talkid "+str(talkid)
                                        + "do not agree. Once we had \""
                                        + splitted[0] + "\" and once we had \""
                                        + talkdict["event"] + "\"")

        # Update the languages
        languages = media_url_builder.__parse_languages(link, splitted)
        talkdict.setdefault("languages", set()).update(languages)

        # Join again to give the key in the langmap:
        key = media_url_builder.__list_to_langmap_key(list(languages))

        langmap = talkdict.setdefault("langmap", dict())

        if key in langmap:
            raise InvalidMediaPageError("duplicated language set",
                                        "Found the language key \"" + key +
                                        "\" twice in the language map. " +
                                        "It was generated from both the links \"" +
                                        link + "\" as well as \"" +
                                        langmap[key]["url"] + "\".")

        langmap[key] = {
            "languages": languages,
            "url": self.media_prefix + "/" + self.video_format + "/" + link
        }

    def get_languages(self, talkid):
        """
        Get a set of ISO 639-3 language codes for which audio tracks exist for this
        talkid. Not neccessarily a file with exactly this audio track or all combinations
        of audio tracks might exist.

        For example. If a file with deu, eng and rus exists as well as a file with spa
        and deu the result will be the set { deu, eng, spa, rus }.
        """
        try:
            return self.cached[talkid]["languages"]
        except KeyError:
            raise UnknownTalkIdError(talkid)

    def get_url(self, talkid, language="ALL"):
        """
        Get the media url from the talkid

        lang:  A list of ISO 639-3 language codes (as strings), which should be
               contained as the audio tracks of the file.
               Examples are "[deu]" or "[deu,eng]". For a list of available languages
               for this file, see the returned values of the function get_languages()

               The option also understands the special value "ALL", which returns the
               url of the file with the most audio tracks.

        If the talkid was not found on the server an UnknownTalkIdError is raised.
        If the list of language codes is invalid, an InvalidLanguagesError is raised.
        """
        try:
            langmap = self.cached[talkid]["langmap"]
        except KeyError:
            raise UnknownTalkIdError(talkid)

        if language == "ALL":
            longestkey = ""
            for key in langmap.keys():
                if len(key) > len(longestkey):
                    longestkey = key
            return langmap[longestkey]["url"]
        else:
            # TODO implement
            raise InvalidLanguagesError("Not yet implemented")


class fahrplan_data:
    """
    Get json data from Fahrplan and extract relevant part.

    fahrplan_string can be an url or a file on the local disk
    """

    def __get_fahrplan_as_text(self, fahrplan_json):
        if os.path.exists(fahrplan_json):
            try:
                with open(fahrplan_json) as f:
                    return f.read()
            except IOError as e:
                raise IOError("Could not get the Fahrplan from \"" + fahrplan_json +
                              "\": " + str(e))
        else:
            errorstring = "Could not get the Fahrplan from \"" + fahrplan_json + "\""
            user_agent = __package__ + " " + __version__ + " (see " + __upstream__ + ")"
            try:
                req_headers = {
                    'User-Agent': user_agent,
                    'From': __upstream__,
                }

                req = requests.get(fahrplan_json, headers=req_headers)
            except IOError as e:
                raise IOError(errorstring + ": " + str(e))

            if (not req.ok):
                raise IOError(errorstring + ".")

            # Note: text automatically takes the resulting bytes,
            # makes a guess and spits out an encoded string

            # Request body as a unicode string
            return req.text

    def __init__(self, base_page, json_location):
        """
        Initialise a fahrplan_data object.

        base_page      Url to the base page of the fahrplan data.
        json_location  Location where json data is to be found.
        """
        self.base_page = base_page
        self.__location = json_location
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
                self.lectures.update({talk['id']: talk for talk in all_talks})

        except KeyError as e:
            raise InvalidFahrplanData("Fahrplan file \"" + self.location +
                                      "\" is not in the expected format: Key \"" +
                                      str(e) + "\" is missing")

    @property
    def location(self):
        """
        Get the json file from which the fahrplan data in this object has been extracted.
        """
        return self.__location

    def all_talkids(self):
        return [v.get("slug", k) for k, v in self.lectures.items()]


def find_os_executable(executable):
    """
    Return the full path of an executable
    or None if it could not be found
    """
    if os.path.isfile(executable):
        return executable

    psplit = os.environ['PATH'].split(os.pathsep)
    for p in psplit:
        exe_path = os.path.join(p, executable)
        if os.path.isfile(exe_path):
            return exe_path
    return None


class download_manager:
    """ Class to manage different methods to download files from the net."""
    def __init__(self):
        self.wget_path = find_os_executable("wget")
        self.curl_path = find_os_executable("curl")
        self.user_agent = __package__ + " " + __version__ + \
            " (see " + __upstream__ + ")"

        # self.automethod decides which method is chosen if
        # method="auto" is supplied to download
        self.automethod = "requests"
        if self.wget_path is not None:
            self.automethod = "wget"
        elif self.curl_path is not None:
            self.automethod = "curl"

    def _download_wget(self, url, folder=".", out=None):
        args = [self.wget_path, "--continue", "--show-progress",
                "--user-agent=\"" + self.user_agent + "\""]
        if out is not None:
            args.append("--output-document=" + str(out))
        args.append(url)
        return subprocess.call(args, cwd=folder)

    def _download_curl(self, url, folder=".", out=None):
        if out is None:
            out = os.path.basename(url)
        args = [self.curl_path, "--continue-at", "-",
                "--location", "--user-agent",
                "\"" + self.user_agent + "\"",
                "--output", out, url]
        return subprocess.call(args, cwd=folder)

    def _download_requests(self, url, folder=".", out=None):
        if out is None:
            out = os.path.basename(url)
        file_name = os.path.join(folder, out)

        req_headers = {
            'User-Agent': self.user_agent,
            'From': __upstream__,
        }

        with open(file_name, "wb") as f:
            print("Downloading file: ", file_name)
            print("from:             ", url)
            response = requests.get(url, stream=True, headers=req_headers)
            total_data_size = response.headers.get('content-length')

            if total_data_size is None:
                f.write(response.content)
            else:
                total_data_size = int(total_data_size)  # Convert from string to int

                pbar_width = 50    # Progress bar width
                sum_data_size = 0  # Size of data downloaded so far
                for data in response.iter_content(chunk_size=4096):
                    sum_data_size += len(data)
                    f.write(data)

                    n_dash = int(pbar_width * sum_data_size / total_data_size)
                    sys.stdout.write("\r   ["+"="*n_dash + " " * (pbar_width-n_dash)+"]")
                    sys.stdout.flush()

    def is_method_available(self, method):
        """Check whether the provided download method is available."""
        if method == "requests":
            return True
        if method == "wget":
            return self.wget_path is not None
        if method == "curl":
            return self.curl_path is not None
        else:
            raise ValueError("Unknown method: " + method)

    def download(self, url, folder=".", out=None, method=None):
        """Download an url into a folder.

           method:    The method/program to use for download
                      - wget       use wget
                      - curl       use curl
                      - requests   use python requests
                      - None:   choose automatically
           out:   The name of the output file. If not given
                  it is autodetermined

          If a download method is not available a ValueError
          is raised.

          Returns the return code of the program executed.
        """
        # TODO better not expose the return code and go via
        #      exceptions instead

        if method is None:
            return self.download(url, folder=folder, out=out, method=self.automethod)

        if not self.is_method_available(method):
            raise ValueError("Method not available: " + method)

        if method == "wget":
            return self._download_wget(url, folder=folder, out=out)
        elif method == "curl":
            return self._download_curl(url, folder=folder, out=out)
        elif method == "requests":
            return self._download_requests(url, folder=folder, out=out)
        else:
            raise SystemExit("We should never get to this branch. This is a bug.")


class lecture_downloader:
    def __init__(self, fahrplan_data, media_url_builders,
                 download_directory=os.getcwd()):
        """
        Initialise a lecture downloader. It requires a Fahrplan_data object and a
        media_url_builder for each media type to be downloaded.
        The latter is supplied in the list media_url_builders
        """

        self.fahrplan_data = fahrplan_data
        self.media_url_builders = media_url_builders
        self.download_directory = download_directory

    def info_text(self, talkid):
        # TODO Use markdown or offer to use markdown here
        #      => Make a pdf out of it?
        try:
            # the fahrplan lecture object:
            lecture = self.fahrplan_data.lectures[talkid]
        except KeyError:
            raise UnknownTalkIdError(talkid)

        try:
            ret = lecture['title'] + '\n'
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

            # maximum length of description string:
            maxlength = max(len(x['title']) for x in lecture['links'])
            maxlength = min(maxlength, 37)
            fmt = "  - {0:" + str(maxlength) + "s}   {1}\n"

            for link in lecture['links']:
                ret += fmt.format(link['title'], link['url'])

            return ret
        except KeyError as e:
            raise InvalidFahrplanData("Fahrplan file \"" + fahrplan_data.location +
                                      "\" is not in the expected format: Key \"" +
                                      str(e) + "\" is missing")

        return ret

    def download(self, talkid):
        """
        Download the data assoicatied with a talk.

        talkid can be an int (i.e. an actual numeric talkid)
        or a slug (like pretalx uses it)
        """
        if isinstance(talkid, int):
            try:
                # the fahrplan lecture object:
                lecture = self.fahrplan_data.lectures[talkid]

                # folder into which to download everything:
                folder = os.path.join(self.download_directory, lecture['slug'])
            except KeyError:
                raise UnknownTalkIdError(talkid)
        elif isinstance(talkid, str):
            lecture = [l for l in self.fahrplan_data.lectures.values()
                       if l["slug"] == talkid]
            if len(lecture) == 1:
                lecture = lecture[0]
            else:
                raise UnknownTalkIdError(talkid)
            title = lecture["title"]
            title = re.sub("[^a-zA-Z0-9-_]", "_", title)
            subdir = self.fahrplan_data.meta["conference"].replace(" ", "_") + \
                "-" + str(lecture["id"]) + "-" + title
            folder = os.path.join(self.download_directory, subdir)

        # make dir
        os.makedirs(folder + "/", exist_ok=True)

        # write info page:
        with open(folder+"/info_"+str(talkid)+".txt", "wb") as f:
            f.write(self.info_text(lecture["id"]).encode("utf-8"))

        had_errors = False

        # Download manager object:
        down_manag = download_manager()

        # download all media files:
        for builder in self.media_url_builders:
            try:
                url = builder.get_url(lecture["id"])

                # TODO this is not ideal, do this with exceptions
                ret = down_manag.download(url, folder=folder)
                if ret != 0:
                    print("Could not download media file \"" + url + "\".")
                    had_errors = True

            except UnknownTalkIdError:
                print("Could not download format \"" + builder.video_format +
                      "\" for talkid \"" + str(talkid) + "\".")
                had_errors = True

        # download attachments
        for att in lecture['attachments']:
            # build full url to file:
            url = self.fahrplan_data.base_page + "/" + att['url']

            if url.find("attachments/original/missing.png") != -1:
                # marker file that the original attachment file has gone missing
                continue

            # download
            outfile = url[url.rfind("/")+1:]          # basename of the url
            outfile = outfile[:outfile.rfind("?")]    # ignore the tailling ?..... stuff
            ret = down_manag.download(url, folder=folder, out=outfile)
            if ret != 0:
                print("Could not download attachment \"" + att + "\" to file \"" + outfile
                      + "\" in folder \"" + folder + "\".")
                had_errors = True

        # TODO go through links and download them if there are of a certain mime type

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
    def __init__(self, path):
        self.ferr = None
        self.ferr = open(path, "a")
        self.ferr.write(surround_text(str(datetime.datetime.now())) + "\n")
        self.ferr.write("# List of talks not properly downloaded last run:\n")
        self.ferr.write("#    (use this file as listfile via\n")
        self.ferr.write("#     --input-file \"" + path + "\"\n")
        self.ferr.write("#    to rerun the download process with only the failed videos."
                        ")\n")

    def log(self, text):
        self.ferr.write(text + "\n")

    def __del__(self):
        if self.ferr is not None:
            self.ferr.close()


class idlist_reader:
    def __init__(self, path):
            if not os.path.exists(path):
                raise IOError("Path \"" + path + "\" does not exist.")

            self.idlist = []
            with open(path) as f:
                try:
                    idlist = [line.split('#')[0].strip() for line in f.readlines()
                              if not line.startswith("#")]
                    for val in idlist:
                        if len(val) == 0:
                            continue
                        try:
                            self.idlist.append(int(val))
                        except ValueError:
                            self.idlist.append(val)
                except ValueError as e:
                    raise ValueError("Invalid idlist file \""+path+"\": " + str(e))


class timebarrier:
    """
    Class that makes sure (by using time.sleep) that there is a minimum
    time span of secs_delay between its construction and destruction
    """

    def __init__(self, secs_delay):
        """ Initialise the timebarrier class"""
        # The minimum time required at destrution:
        self.__req_endtime = secs_delay + time.time()

    @property
    def required_endtime(self):
        return self.__req_endtime

    def __del__(self):
        # calc sleep time in seconds, at least 0
        sleeptime = max(0, self.__req_endtime - time.time())
        time.sleep(sleeptime)


def do_list_events(conf):
    print("The following events are configured:")

    if len(conf.events) == 0:
        return

    # maximum length of all events:
    maxlen = max(map(len, conf.events))
    fmt = "  - {0:" + str(maxlen) + "s} (started on {1}{2})"

    # print events:
    for name, event in sorted(conf.events.items()):
        extra = ""
        if name == conf.most_recent_event["name"]:
            extra = " -- most recent"
        print(fmt.format(name, event["starts"], extra))


def add_args_to_parser(parser):
    """
    Add all required arguments to the parser object
    """
    # configuration:
    parser.add_argument("--config", metavar="config_file", type=str,
                        default="~/.config/down-frab-videos/config.yaml",
                        help="Path to the config file used to determine the appropriate "
                        "urls for the chaos events, ...")
    parser.add_argument("--event", default=None, type=str, metavar="event",
                        help="Select a specific chaos event, by default the most recent, "
                        "known event is selected.")
    parser.add_argument("--format", metavar="video_format", type=str, action='append',
                        default=None,
                        help="The format in which the videos should be downloaded. "
                        "By default it downloads the available format of highest "
                        "preference in the config file, try --list-formats to list the "
                        "available formats for the selected event. May be given multiple "
                        "times to specify more than one format to download.")

    # downloading:
    parser.add_argument("-i", "--input-file",
                        metavar="listfile", type=str, default=None, dest="file",
                        help="A file which contains the talkids to download line "
                        "by line.")
    parser.add_argument("--mindelay", metavar="seconds", type=int, default=3,
                        help="Minimum delay between two downloads (to not annoy the "
                        "media servers that much).")
    parser.add_argument("ids", nargs='*', default=[], type=str,
                        help="Talk ids to download. These will be added to any of the "
                        "ids, which are found in a listfile provided by --input-file")
    parser.add_argument("-a", "--all", action="store_true", default=False,
                        help="Download all talks of the selected event into a "
                        "folder named like the event")

    # other modes:
    parser.add_argument("--list-formats", action='store_true', default=False,
                        help="List the available formats for the selected chaos event "
                        "and exit.")
    parser.add_argument("--list-events", action='store_true', default=False,
                        help="List the configured chaos events and exit.")
    parser.add_argument("--dump-config", action='store_true',
                        help="Dump the default config to the file given via --config "
                        "or the default location and exit.")
    parser.add_argument("-v", "--version", action='store_true', default=False,
                        help="Print version information and exit.")

    # behaviour:
    parser.add_argument("--strict", action='store_true', default=False,
                        help="Be more strict about the parsed data, "
                        "e.g. abort on any error encountered.")


def parse_args_from_parser(parser):
    """
    Parse all args from the parser object required for this module
    Return the args parsed, raise SystemExit on any error.
    """
    args = parser.parse_args()

    if not (args.dump_config or args.list_events or args.list_formats or args.version):
        args.download_mode = True

        if args.file is None and len(args.ids) == 0 and not args.all:
            raise SystemExit("You need to supply some talk ids or one of "
                             "--all, --input-file, --list-formats, "
                             "--list-events, --dump-config")

        if args.file is not None and not os.path.exists(args.file):
            raise SystemExit("The list file \"" + args.file + "\" does not exist.")

    else:
        args.download_mode = False
        if args.file is not None or len(args.ids) > 0:
            print("--input-file and all commandline-supplied ids are ignored if one of "
                  "--list-formats, --list-events, --dump-config, --version is specified,"
                  "since no download will be done it these cases.")

    return args


def main():
    #
    # args
    #
    parser = argparse.ArgumentParser(description="Download videos from the Fahrplan and "
                                     "media system used for chaos events.")
    add_args_to_parser(parser)
    args = parse_args_from_parser(parser)

    #
    # version
    #
    if args.version:
        ret = __package__ + " " + __version__ + "\n\n"

        ret += "Copyright © 2017 " + __authors__ + ".\n"
        ret += "License GPLv3+: GNU GPL version 3 or later\n"
        ret += "<http://www.gnu.org/licenses/gpl.html>.\n\n"

        ret += "Please report bugs and suggest enhancements under\n"
        ret += "<" + __upstream__ + ">.\n"
        print(ret[:-1])
        sys.exit(0)

    #
    # config
    #
    args.config = os.path.expanduser(args.config)

    # TMP: This is for the transition to the new config name
    config_old = "~/.config/down-frab-videos/config.yaml"
    if os.path.isfile(config_old):
        import warnings
        import shutil
        config_new = "~/.config/down-frab-videos/config.yaml"

        warnings.warn("Moving config {} to new location {}"
                      "".format(config_old, config_new))
        shutil.move(config_old, config_new)

        if args.config == config_old:
            args.config = config_new
    # end TMP

    if args.dump_config:
        configdir = os.path.dirname(args.config)
        os.makedirs(configdir, exist_ok=True)
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
        selected_formats = [f for f in conf.settings["video_preference"]
                            if f in available_formats]
        if len(selected_formats) == 0:
            raise SystemExit("None of formats accepted by the user(" +
                             str(conf.settings["video_preference"])+") could be found "
                             "for the event \"" + selected_event["name"] + "\". "
                             "Use --list-formats to view the list of "
                             "available video formats.")
        selected_formats = [selected_formats[0]]
    else:
        for f in args.format:
            if f not in available_formats:
                raise SystemExit("The format \"" + f + "\" could not be found for "
                                 "the event \"" + selected_event["name"] + "\". "
                                 "Use --list-formats to view the list of "
                                 "available video formats.")
        selected_formats = args.format

    #
    # Download videos
    #
    print(surround_text("Gathering lecture data for " + selected_event["name"]))
    try:
        print(" - Media file information from \"" +
              domain_from_url(selected_event["media_prefix"]) + "\" for the formats:")
        builders = []
        for form in selected_formats:
            print("    -", form)
            builders.append(media_url_builder(selected_event["media_prefix"], form,
                                              raise_on_error=args.strict))
    except IOError as e:
        raise SystemExit("Could not download list of media files: " + str(e))

    try:
        fahrplan_url = selected_event["fahrplan"]
        json_location = selected_event.get("json_location",
                                           fahrplan_url + "/schedule.json")

        print(" - Fahrplan from \"" + domain_from_url(fahrplan_url) + "\".")
        fahrplan = fahrplan_data(fahrplan_url, json_location)
    except IOError as e:
        raise SystemExit("Could not download Fahrplan: " + str(e))
    print(" - Finished: Got \"" + fahrplan.meta['conference'] + "\", "
          "version \"" + fahrplan.meta['version'] + "\"")

    download_directory = os.getcwd()
    if args.all:
        args.ids = fahrplan.all_talkids()
        download_directory = os.path.join(download_directory,
                                          selected_event["name"])

    # bundle fahrplan and builders into the downloader
    downloader = lecture_downloader(fahrplan, builders,
                                    download_directory=download_directory)

    # Initialise with the commandline talk ids:
    idlist = []
    for id in args.ids:
        try:
            idc = int(id)
        except ValueError:
            idc = id
        idlist.append(idc)

    if args.file is None:
        errorfile = "errors"
    else:
        errorfile = args.file + ".errors"
        # read the id list:
        try:
            idreader = idlist_reader(args.file)
        except (IOError, ValueError) as e:
            raise SystemExit("Error reading the list file \"" + args.file +
                             "\": " + str(e))

        idlist.extend(idreader.idlist)

    # setup the error log
    try:
        errlog = errorlog(errorfile)
        print("\nSaving an error log to the file \"" + errorfile + "\".")
    except IOError as e:
        raise SystemExit("Error creating the errorlog file \"" + errorfile +
                         "\": " + str(e))

    # download the ids:
    for talkid in sorted(set(idlist)):
        print("\n" + surround_text(str(talkid)))
        barrier = timebarrier(args.mindelay)

        try:
            downloader.download(talkid)
        except UnknownTalkIdError as e:
            print("TalkId erroneous or unknown: " + str(e))
            errlog.log(str(talkid))
        except InvalidFahrplanData as e:
            print("Invalid Fahrplan data for TalkId " + str(talkid)
                  + ": " + str(e))
            errlog.log(str(talkid))
        except InvalidLanguagesError as e:
            print("Found invalid language codes for TalkId "
                  + str(talkid) + ": " + str(e))
            errlog.log(str(talkid))
        del barrier
