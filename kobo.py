import os
import sqlite3

# NOTE: Configure these
# --------------------------------------------------------------------------------
VOLUME = r'E:'
# --------------------------------------------------------------------------------

KOBO_DIR = '.kobo'
DB_FILE = os.path.join(VOLUME, KOBO_DIR, 'KoboReader.sqlite')

assert os.path.isfile(DB_FILE)

CONNECTION = sqlite3.connect(DB_FILE)
CONNECTION.row_factory = sqlite3.Row
