from __future__ import annotations
import pprint
from typing import Dict, List

import anki
from anki import Note
from kobo import WordListTable
from web import Selenium

from c_anki_notes import Deck, INote

# NOTE: Configure these
# --------------------------------------------------------------------------------
from c_anki_notes import RAENote

DICT_SUFFIX_DECK: Dict[str, Deck] = {
    '-es': Deck('RAE', RAENote),
}

# --------------------------------------------------------------------------------


KOBO_KEY_FIELD = 'kobo_key'


def main() -> int:
    exit_code = 0
    selenium = Selenium()

    anki_decks = anki.get_decks()
    for deck in DICT_SUFFIX_DECK.values():
        if deck.name not in anki_decks:
            exit_code = 1
            print(f'Deck {deck} not present in Anki')
            pprint.pp(f'Anki decks: {anki_decks}')

    if exit_code != 0:
        return exit_code

    word_rows = WordListTable.select_all()
    word_rows_by_dict: Dict[str, List[WordListTable]] = {}
    for word_row in word_rows:
        if word_row.dict_suffix not in word_rows_by_dict:
            word_rows_by_dict[word_row.dict_suffix] = []
        word_rows_by_dict[word_row.dict_suffix].append(word_row)

    delete: List[WordListTable] = []
    notes: Dict[str, List[Note]] = {}
    for dict_suffix in word_rows_by_dict.keys():
        if dict_suffix not in DICT_SUFFIX_DECK:
            pprint.pp(f'{dict_suffix} not present in {DICT_SUFFIX_DECK}')
            continue

        deck = DICT_SUFFIX_DECK[dict_suffix]

        notes[deck.name] = []
        rows = word_rows_by_dict[dict_suffix]
        for i, word_row in enumerate(rows):
            print(
                f'{dict_suffix}: {i+1}/{len(rows)}',
                end='\r' if (i+1) != len(rows) else '\n',
            )

            args = INote.CreateParams(word_row.text, selenium)
            inotes = deck.inote_cls.create(args)

            if len(inotes) != 0:
                delete.append(word_row)

            for key, inote in inotes.items():
                fields = inote.format()
                fields[KOBO_KEY_FIELD] = key

                notes[deck.name].append(Note(inote.type, fields))

    for deck_name in notes.keys():
        for note in notes[deck_name]:
            text = note.fields[KOBO_KEY_FIELD]
            query = f'"{KOBO_KEY_FIELD}:{text}"'
            note_ids = anki.find_notes(deck_name, query)

            assert len(note_ids) <= 1

            if len(note_ids) == 0:
                anki.add_note(note, deck_name)
            else:
                note_id = note_ids[0]
                anki.update_note(note, note_id)

    selenium.quit()
    WordListTable.delete_all(delete)

    return exit_code


if __name__ == '__main__':
    exit(main())
