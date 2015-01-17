#!/usr/bin/env python
"""Usage: dl.py [-s SUBJECT] [options] THREAD

-d --directory SAVEPATH  Save images to a directory in SAVEPATH
-s --subject SUBJECT     If set, don't ask for folder name, but directly save
                         in SUBJECT. If not set 8changrab tries the subject
                         of the thread, and asks otherwise.
--workers=<num>          # of processes to spawn [default: 10]

-h --help     Show this
-v --version  Show version
"""
from __future__ import print_function
import sys
import os
import urllib2
import shutil
from docopt import docopt
from bs4 import BeautifulSoup
from os.path import expanduser
from multiprocessing import Pool
from multiprocessing import Value

VERSION = "8changrab 0.2"
DEFAULT_SAVE_PATH = '{}/8chan'.format(expanduser("~"))

def pretty_update_progress(current, total):
    """Create a pretty progress bar by constantly updating one line"""
    progress_bar_length = 40

    percent_finished = current/float(total) # 0 -> 1

    fillers = int(percent_finished * progress_bar_length)
    empty_fillers = progress_bar_length - fillers

    progress_bar = "["
    progress_bar += fillers*"="
    progress_bar += ">"
    progress_bar += empty_fillers*" "
    progress_bar += "]"

    term = Terminal()
    with term.location(x=0):
        print("{} {}/{}".format(progress_bar, current, total), end="")
    sys.stdout.flush()

def simple_update_progress(current, total):
    """Simple update progress"""
    sys.stdout.write("|")
    sys.stdout.flush()

# Use dumb output on non-tty by default
update_progress = simple_update_progress
try:
    # If available, use pretty terminal output
    from blessings import Terminal
    TERM = Terminal()
    if TERM.is_a_tty:
        update_progress = pretty_update_progress
except ImportError: pass

HDR = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

def download_image(link, filename):
    """Download LINK to FILENAME if FILENAME doesn't already exist"""
    if os.path.exists(filename):
        return

    try:
        req = urllib2.Request(link, headers=HDR)
        response = urllib2.urlopen(req)
        with open(filename, "wb") as _file:
            _file.write(response.read())
            _file.close()
    except KeyboardInterrupt:
        # Remove unfinished download
        os.remove(filename)

def download_and_update_progress(image):
    """Spawned as a separate process to download IMAGE"""
    try:
        link, filename = image
        download_image(link, filename)
        with COUNTER.get_lock():
            COUNTER.value += 1
            update_progress(COUNTER.value, TOTAL_COUNT.value)
    except KeyboardInterrupt: pass

def main(argv):
    """Grabs images from an 8chan thread"""
    args = docopt(__doc__, argv=argv[1:], version=VERSION)

    url = args['THREAD']
    savepath = args['--directory'] or DEFAULT_SAVE_PATH

    if not "8ch.net" in url:
        print("Not an 8chan URL")
        return 1

    if not os.path.exists(savepath):
        os.makedirs(savepath)

    req = urllib2.Request(url, headers=HDR)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)

    if args['--subject']:
        topic = args['--subject']
    else:
        subject = soup.find(attrs={"class": "subject"})
        if subject:
            topic = subject.string
        else:
            topic = raw_input('Please specify folder name: ')

    workers = int(args['--workers'])

    download_path = '{}/{}'.format(savepath, topic)

    if not os.path.exists(download_path):
        os.makedirs(download_path)

    print("Downloading to {}".format(download_path))

    fileinfos = soup.find_all(attrs={"class": "fileinfo"})

    # Global values used in download_and_update_progress()
    global TOTAL_COUNT
    TOTAL_COUNT = Value('i', 0)
    global COUNTER
    COUNTER = Value('i', 0)

    TOTAL_COUNT.value = len(fileinfos)

    # Create a list of images to download
    downloads = []
    for fileinfo in fileinfos:
        for link in fileinfo.find_all('a'):
            download_link = link.get('href')
            downloads.append((download_link,'%s/%s'%(download_path, link.string)))

    # Use a pool of processes to download the images in the list
    pool = Pool(workers)
    p = pool.map_async(download_and_update_progress, downloads)

    # Wait for downloads to complete
    try:
        # Wow. Python is great. I *ABSOLUTELY ADORE* python.
        results = p.get(0xFFFF)
    except KeyboardInterrupt:
        print("Aborting")
        pool.terminate()
        pool.join()
    else:
        pool.close()
        pool.join()
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))

