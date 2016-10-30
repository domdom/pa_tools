import os
import os.path
import re
import glob

"""
Finds and returns the location of PA's user data folder
"""
def _find_data_dir():
    HOME = os.getenv('USERPROFILE')
    if HOME is None:
        HOME = os.getenv('HOME')
    if HOME is None:
        HOME = ''
    # check each possible location for PA log files.
    path = os.path.normpath(os.path.join(HOME, 'AppData/local/Uber Entertainment/Planetary Annihilation'))
    if os.path.isdir(path):
        return path

    path = os.path.normpath(os.path.join(HOME, ".local/Uber Entertainment/Planetary Annihilation"))
    if os.path.isdir(path):
        return path

    path = os.path.normpath(os.path.join(HOME, "Library/Application Support/Uber Entertainment/Planetary Annihilation"))
    if os.path.isdir(path):
        return path

    raise FileNotFoundError('Could not find the PA user data directory.')

"""
Reads PA's logs to find the last used PA media directory.
"""
def _find_media_dir():
    data_dir = _find_data_dir()
    log_dir = os.path.join(data_dir, 'log')

    if not os.path.isdir(log_dir):
        raise FileNotFoundError('Could not find the log directory.')

    log_files = glob.glob(os.path.join(log_dir,'*.txt'))
    log_files = reversed(sorted(log_files))
    log_files = map(lambda x: os.path.join(log_dir, x), log_files)

    for log_file in log_files:
        with open(log_file) as log:
            for line in log:
                m = re.search(r'INFO Coherent host dir: "([^"]*)"', line)
                if m:
                    base_path = m.group(1)

                    if not os.path.isdir(base_path): raise FileNotFoundError('Could not find PA directory.')

                    # Windows, Linux
                    path = os.path.normpath(os.path.join(base_path, '../../media'))
                    if os.path.isdir(path):
                        return path

                    # macOS (Stand-alone app)
                    path = os.path.normpath(os.path.join(base_path, '../../Resources/media'))
                    if os.path.isdir(path):
                        return path

                    # macOs (Steam version)
                    path = os.path.normpath(os.path.join(base_path, '../../../../media'))
                    if os.path.isdir(path):
                        return path

                    raise FileNotFoundError('Could not find PA media directory. You must play the game at least once for this directory to be detected.')


def _find_pa_build():
    pa_version = os.path.normpath(os.path.join(_find_media_dir(), '..', 'version.txt'))

    with open(pa_version) as version:
        return version.readline().strip()


PA_VERSION = _find_pa_build()
PA_DATA_DIR = _find_data_dir()
PA_MEDIA_DIR = _find_media_dir()





