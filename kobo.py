from __future__ import annotations
import os
import sqlite3
from typing import List

# NOTE: Configure these
# --------------------------------------------------------------------------------
VOLUME = r'E:'
# --------------------------------------------------------------------------------


class WordListTable:

    TABLE = 'WordList'

    TEXT_COL = 'Text'
    VOLUME_ID_COL = 'VolumeId'
    DICT_SUFFIX_COL = 'DictSuffix'
    DATE_CREATED_COL = 'DateCreated'

    def __init__(self, text: str, volume_id: str, dict_suffix: str, date_created: str) -> None:
        self.text = text
        self.volume_id = volume_id
        self.dict_suffix = dict_suffix
        self.date_created = date_created

    @staticmethod
    def select_all() -> List[WordListTable]:
        cursor = CONNECTION.execute(f'SELECT * FROM {WordListTable.TABLE}')

        rows: List[WordListTable] = []
        for row in cursor.fetchall():
            rows.append(WordListTable(
                row[WordListTable.TEXT_COL],
                row[WordListTable.VOLUME_ID_COL],
                row[WordListTable.DICT_SUFFIX_COL],
                row[WordListTable.DATE_CREATED_COL],
            ))

        return rows


KOBO_DIR = '.kobo'
DB_FILE = os.path.join(VOLUME, KOBO_DIR, 'KoboReader.sqlite')

assert os.path.isfile(DB_FILE)

CONNECTION = sqlite3.connect(DB_FILE)
CONNECTION.row_factory = sqlite3.Row
