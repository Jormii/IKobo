from __future__ import annotations
import pprint
from typing import Dict, List, Tuple, Callable

import anki
from kobo import CONNECTION
from anki import Note
from anki_notes import INote

# NOTE: Configure these
# --------------------------------------------------------------------------------
MakeNoteCbT = Callable[[str], INote]

DICT_SUFFIX_TO_NOTE: Dict[str, Tuple[str, MakeNoteCbT]] = {
}

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


if __name__ == '__main__':
    exit_code = 0

    decks = anki.get_decks()
    for (deck, _) in DICT_SUFFIX_TO_NOTE.values():
        if deck not in decks:
            exit_code = 1
            print(f'Deck {deck} not present in Anki')
            pprint.pp(f'Anki decks: {decks}')

    if exit_code != 0:
        exit(exit_code)

    word_rows = WordListTable.select_all()
    word_rows_by_dict: Dict[str, List[WordListTable]] = {}
    for word_row in word_rows:
        if word_row.dict_suffix not in word_rows_by_dict:
            word_rows_by_dict[word_row.dict_suffix] = []
        word_rows_by_dict[word_row.dict_suffix].append(word_row)

    notes: Dict[str, List[Note]] = {}
    for dict_suffix in word_rows_by_dict.keys():
        if dict_suffix not in DICT_SUFFIX_TO_NOTE:
            pprint.pp(f'{dict_suffix} not present in {DICT_SUFFIX_TO_NOTE}')
            continue

        deck, make_note_cb = DICT_SUFFIX_TO_NOTE[dict_suffix]

        notes[deck] = []
        for word_row in word_rows_by_dict[dict_suffix]:
            note = make_note_cb(word_row.text)

            fields = note.format()
            notes[deck].append(Note(note.type, fields))

    exit(exit_code)
