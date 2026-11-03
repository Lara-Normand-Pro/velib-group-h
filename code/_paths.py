"""
Locate the project files whatever the working directory.

Every script imports this, so running them from VS Code's Run button, from the
project root, or from inside code/ all behave the same. It looks for the files
in the submitted package first, then in the full working tree.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the folder containing code/

def find_dir(*candidates):
    for c in candidates:
        p = ROOT / c
        if p.is_dir():
            return p
    return None

def find_file(*candidates):
    for c in candidates:
        hits = sorted(ROOT.glob(c))
        if hits:
            return hits[-1]
    return None

# raw captures: the full archive is only in the working tree, not in the package
RAW_STATUS = find_dir("snapshot_2909/raw/status", "raw/status")

# one complete day of untouched captures, shipped in the package (288 files)
FULL_DAY = None
_fd = ROOT / "raw_sample"
if _fd.is_dir():
    for d in sorted(_fd.glob("full_day_*")):
        if d.is_dir() and any(d.glob("*.json.gz")):
            FULL_DAY = d
            break

# the few untouched captures shipped in the package, enough to check the transformation
SAMPLE_STATUS = sorted((ROOT / "raw_sample").glob("status_*.json.gz")) \
    if (ROOT / "raw_sample").is_dir() else []

# hourly station lists: the full archive only in the working tree; in the package, the
# untouched list of 20.09 and the one archived on 29.09
RAW_INFO = find_dir("snapshot_2909/raw/info", "raw/info")
INFO_FILES = sorted((ROOT / "raw_sample").glob("info_*.json.gz")) + \
             sorted((ROOT / "data").glob("station_information_*.json.gz"))

# the HTTP log: shipped in the package
HTTP_LOG = find_file("raw_sample/http_log.csv", "snapshot_2909/raw/http_log.csv",
                     "**/http_log.csv")

# the station list: shipped in the package
STATION_INFO = find_file("data/station_information*.json.gz",
                         "data/station_information*.json",
                         "raw_sample/info_*.json.gz",
                         "snapshot_2909/raw/info/*/*.json.gz",
                         "station_information.json")

# Where the scripts write.
# With the full archive (our own working tree) they write into data/, which is how the
# submitted files were produced. Without it, i.e. when someone runs this package, they
# write into data/rebuilt/ instead, so the submitted files are never overwritten and the
# two can be compared.
PACKAGE_MODE = RAW_STATUS is None
DATA_OUT = (ROOT / "data" / "rebuilt") if PACKAGE_MODE else (ROOT / "data")

NO_RAW = (
    "No raw captures found.\n"
    "The full archive (2,631 files, 99 MB) is not included in this package, and\n"
    "raw_sample/ is empty too. See README.md."
)

NO_FULL = (
    "This script groups every capture of a day into one file, so it needs raw captures.\n"
    "Expected either the full archive, or raw_sample/full_day_<date>/ in this package.\n"
    "See README.md."
)

FULL_DAY_NOTE = (
    "The full archive is not included, so this run uses the complete day shipped in\n"
    "raw_sample/: all 288 untouched captures of that day. The output should match the\n"
    "file we submitted, which is how you can check this code against our figures.\n"
)

SAMPLE_NOTE = (
    "The full raw archive is not included in this package, so this run uses the\n"
    "untouched captures in raw_sample/. That is enough to check that the code really\n"
    "produces the submitted tables, not to rebuild the whole dataset.\n"
)
