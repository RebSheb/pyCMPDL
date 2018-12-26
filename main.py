import os
import sys
import requests
import threading
import logging
import json
import zipfile
import time
import queue


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(threadName)s: %(message)s", datefmt="%I:%M:%S")
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


curseAPI = "https://cursemeta.nikky.moe/"


def main():
    """
    Here we get projectID from the user for the program to then download that file,
    extract it to get the manifest.json and then continue from there.
    :return: None
    """
    print("Rob's MT'd downloader because the other downloader's aren't")
    numthreads = input("Enter the amount of threads you'd like to use to download: ")
    if numthreads.isdigit() is not True:
        logging.error("ERR: Number of threads entered was not a number, defaulting to 4")
        numthreads = 4
    if int(numthreads) < 1:
        logging.error("ERR: Cannot have lower than 1 threads, resorting to 1")
        numthreads = 1

    prjid = input("Input a projectID to download: ")
    # prjid = "269708"
    if prjid.isdigit() is not True:
        logging.error("ERR: Not a project ID..")
        sys.exit(0)

    listfiles(prjid)
    print("Using the ID on the far left, pick one: ")
    idtodl = input()
    if idtodl.isdigit() is not True:
        logging.error("ERR: Not an ID from list")
        sys.exit(0)

    downloadurl = APIHelper.getdownloadurl(prjid, idtodl)
    logging.debug("Download URL for selected ID is %s", downloadurl)

    createfolderandchdir("mcdl")

    logging.debug("Now working in %s", os.getcwd())
    downloadpackzip(downloadurl)
    logging.info("Successfully downloaded pack zip, extracting...")
    b = getmanifestfromzip(Downloader.format_name(downloadurl))

    createfolderandchdir(b["name"] + " " + b["version"])
    logging.debug("Now working in %s", os.getcwd())
    createfolderandchdir("minecraft")
    logging.debug("Now working in %s", os.getcwd())
    createfolderandchdir("mods")
    logging.debug("Now working in %s", os.getcwd())

    fileQueue = queue.Queue()

    logging.info("Grabbing all the mod file URLs. This might take a while as there are %s", len(b["files"]))
    for x in range(0, len(b["files"])):
        fileQueue.put(APIHelper.getmodfileurl(b["files"][x]["projectID"], b["files"][x]["fileID"]))

    logging.info("Added all mod urls to queue, time to spawn threads")
    for x in range(0, int(numthreads)):
        b[x] = Downloader(fileQueue)
        b[x].start()

    while not fileQueue.empty():
        if fileQueue.empty():
            for x in range(0, int(numthreads)):
                b[x].join(timeout=4.0)

    # Extract overrides
    zfile = zipfile.ZipFile("../../../" + Downloader.format_name(downloadurl))
    xtractfiles = ["scripts/", "resources/", "resourcepacks/", "mods/", "config/"]
    for x in xtractfiles:
        logging.debug("Extracting %s from %s", x, zfile.filename)
        zfile.extract("overrides/" + x, path="../../../")

    logging.info("Where the overrides folder was extracted, you'll need to copy each folder"
                 " inside of it into the minecraft/ folder.")
    logging.info("The recommended forge version for this is {forgeVer}".format(
        forgeVer=b["minecraft"]["modLoaders"]["id"]))

    """try:
        print("Begin")
        if os.path.isdir("../../../overrides"):
            for x in xtractfiles:
                print(x)
                for y in os.listdir(os.path.join("../../../overrides/", x)):
                    print(x + y)
                    if os.path.isfile("../" + x) is not True:
                        print("If os.path")
                        try:
                            os.mkdir("../" + x)
                            print("Making dir " + x)
                        except Exception as e:
                            shutil.move("../../../overrides/" + x + "/" + y, "../" + x + "/")
                            print(e)
                            pass
    except Exception as e:
        print("Exception " + e)
        pass
"""


def createfolderandchdir(path):
        try:
            if not os.path.exists(path):
                os.mkdir(path)
                time.sleep(3)
                os.chdir(path)
            else:
                os.chdir(path)
        except Exception as e:
            logging.error("Failed to create %s folder or cd into it.", path)
            sys.exit(0)


def downloadpackzip(url):
    fname = Downloader.format_name(url)
    logging.info("Downloading %s", fname)
    try:
        with open(fname, "wb") as zfile:
            req = requests.get(url, stream=True)
            file_len = req.headers.get("content-length")
            if file_len is None:
                zfile.write(req.content)

            else:
                dl = 0
                total_length = int(file_len)
                for chunk in req.iter_content(chunk_size=1024):
                    if chunk:
                        dl += len(chunk)
                        zfile.write(chunk)
                        done = int(50 * dl / total_length)
                        sys.stdout.write("\r[{curProg}{leftProg}]".format(curProg=('=' * done), leftProg=(' ' * (50-done))))
                        sys.stdout.flush()
    except Exception as e:
        logging.error("Error in downloading file %s | %s", fname, e)
        sys.exit(0)


def getmanifestfromzip(filename: str):
    zfile = zipfile.ZipFile(filename, mode="r")
    try:
        b = zfile.read("manifest.json")
        return APIHelper.jsonify(b)
    except Exception as e:
        logging.error("Error in getmanifestfromzip %s", e)
        sys.exit(0)


def listfiles(prjid: str):
    retdata = APIHelper.getaddon(prjid)
    if retdata is False:
        logging.error("Error occurred in listfiles, retdata is false. Bad request perhaps?")
        return

    for x in range(0, len(retdata)): # For each bit of data in JSon array, extract needed bits.
        formatmsg = "{id}: {fileName} {releaseType} {gameVersion}".format(id=str(x), fileName=retdata[x]["fileName"],
                                                                          releaseType=retdata[x]["releaseType"],
                                                                          gameVersion=retdata[x]["gameVersion"][0])
        print(formatmsg)


class Downloader(threading.Thread):
    def __init__(self, myqueue:queue.Queue):
        threading.Thread.__init__(self, args=myqueue)
        self.filesqueue = myqueue

    def run(self):
        logging.debug("New Downloader spawned")
        while not self.filesqueue.empty():
            fileurl = self.filesqueue.get()
            logging.info("Downloading %s", Downloader.format_name(fileurl))
            self.downloadfile(fileurl)

        return

    @staticmethod
    def format_name(url):
        if type(url) is str:
            an = url.split("/")[-1]
            return an

    def downloadfile(self, url):
        fname = Downloader.format_name(url)
        if os.path.isfile(fname):
            logging.info("%s already downloaded, skipping...", fname)
            self.filesqueue.task_done()
            return

        req = requests.get(url, stream=True)
        try:
            with open(fname, "wb") as jarfile:
                for chunk in req.iter_content(chunk_size=8192):
                    if chunk:
                        jarfile.write(chunk)
            self.filesqueue.task_done()
            return
        except Exception as e:
            logging.error("ERR: FAILED TO DOWNLOAD %s | %s", url, fname)
            self.filesqueue.task_done()
            pass


class APIHelper:
    api = "https://cursemeta.nikky.moe/api/"

    def __init__(self):
        pass

    @staticmethod
    def jsonify(data):
        try:
            a = json.loads(data)
            return a
        except Exception as e:
            logging.error("Exception occured %s", e)
            return None

    @staticmethod
    def sort_by_date_response(response):
        """
        This method reorders the JSON passed into it by date order
        using the [id]["fileDate"] attribute. <--- It's EPOCH time.
        Gonna use bubble sort because I can
        :param response:
        :return response but sorted:
        """
        sorted_by_date = sorted(response, key=lambda x: x["fileDate"])
        return sorted_by_date

        # For each X, we want to check if Y is bigger, if so, rearrange.
        # for x in range(0, len(sorted)):
        # for y in range(0, len(sorted)):
        # if sorted[x]["fileDate"] > sorted[y]["fileDate"]:
        # Swap them around as Y is newer than X
        # temp_var = sorted[x]
        # sorted[x] = sorted[y]
        # sorted[y] = temp_var

    @staticmethod
    def getaddon(addonid: str):
        """
        Get all the addon files in a JSon response
        And return it in formatted JSon
        :return: False on Fail or JSon Data on Success
        """
        if addonid.isdigit() is not True:
            return False

        req = requests.get(APIHelper.api + "/addon/" + str(addonid) + "/files")
        if req.status_code is 200:
            #logging.debug(APIHelper.jsonify(req.text)[0])
            ret_json = APIHelper.jsonify(req.text)
            if ret_json is None:
                return False
            return APIHelper.sort_by_date_response(ret_json)

    @staticmethod
    def getdownloadurl(addonid: str, addonfileid=None):
        if addonfileid is not None:
            # This is probably fetching a Pack Download URL
            # Need to get the download URL using addonfileid
            # in the response from getaddon
            retdata = APIHelper.getaddon(addonid)
            if retdata is False:
                logging.error("ERR: getdownloadurl for addonID %s | fileID %s", addonid, addonfileid)
                sys.exit(0)

            if int(addonfileid) > len(retdata):
                logging.error("ERR: The ID inputted was bigger than the amount displayed, max: %s | entered: %s", str(len(retdata)), addonfileid)
                sys.exit(0)

            downloadurl = retdata[int(addonfileid)]["downloadURL"]

            return downloadurl



    @staticmethod
    def getmodfileurl(projectid, fileid):
        req = requests.get(APIHelper.api + "/addon/" + str(projectid) + "/file/" + str(fileid))
        if req.status_code is 200:
            reqjson = APIHelper.jsonify(req.text)
            if reqjson is None:
                logging.error("Error in getmodfileurl, bad json")
                sys.exit(0)

            return reqjson["downloadURL"]


main()