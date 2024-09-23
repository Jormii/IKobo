from __future__ import annotations
import pprint
from typing import Dict, List

import anki
from kobo import CONNECTION
from anki import Note
from anki_notes import Deck, INote
from web import Selenium


# NOTE: Configure these
# --------------------------------------------------------------------------------
from anki_notes import RAENote

DICT_SUFFIX_DECK: Dict[str, Deck] = {
    '-es': Deck('RAE', RAENote),
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
    selenium = Selenium()

    anki_decks = anki.get_decks()
    for deck in DICT_SUFFIX_DECK.values():
        if deck.name not in anki_decks:
            exit_code = 1
            print(f'Deck {deck} not present in Anki')
            pprint.pp(f'Anki decks: {anki_decks}')

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
        if dict_suffix not in DICT_SUFFIX_DECK:
            pprint.pp(f'{dict_suffix} not present in {DICT_SUFFIX_DECK}')
            continue

        deck = DICT_SUFFIX_DECK[dict_suffix]

        notes[deck.name] = []
        for word_row in word_rows_by_dict[dict_suffix]:
            args = INote.CreateParams(word_row.text, selenium)
            inotes = deck.inote_cls.create(args)

            for inote in inotes:
                fields = inote.format()
                notes[deck.name].append(Note(inote.type, fields))

    exit(exit_code)
