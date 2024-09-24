from __future__ import annotations
import json
import pprint
import urllib.request
from typing import Dict, List, Any
from urllib.request import Request

ANKI_CONNECT_VERSION = 6
ANKI_CONNECT_HTTP_ADDRESS = 'http://127.0.0.1:8765'


class Note:

    def __init__(self, type: str, fields: Dict[str, str]) -> None:
        self.type = type
        self.fields = fields

    def __repr__(self) -> str:
        return pprint.pformat(f'{self.type}: {self.fields}')


def get_decks() -> List[str]:
    return request('deckNames', {})  # type: ignore[no-any-return]


def add_note(note: Note, deck: str) -> int:
    params = {
        'note': {
            'deckName': deck,
            'modelName': note.type,
            'fields': note.fields,
        },
    }

    return request('addNote', params)  # type: ignore[no-any-return]


def update_note(note: Note, note_id: int) -> int:
    params = {
        'note': {
            'id': note_id,
            'fields': note.fields,
        },
    }

    return request('updateNoteFields', params)  # type: ignore[no-any-return]


def find_notes(deck: str, query: str) -> List[int]:
    params = {
        'query': f'"deck:{deck}" {query}'
    }

    return request('findNotes', params)  # type: ignore[no-any-return]


def request(action: str, params: Dict[str, Any], version: int = ANKI_CONNECT_VERSION, http_address: str = ANKI_CONNECT_HTTP_ADDRESS) -> Any:
    ERROR_KEY = 'error'
    RESULT_KEY = 'result'

    json_request = json.dumps({
        'action': action,
        'params': params,
        'version': version
    }).encode('utf-8')

    request = Request(http_address, json_request)
    response = json.load(urllib.request.urlopen(request))

    failed = False
    if len(response) != 2:
        failed = True
        print('ANKI_CONNECT: Unexpected number of fields')
    for key in [ERROR_KEY, RESULT_KEY]:
        if key not in response:
            failed = True
            print(f'ANKI_CONNECT: {key} key missing')

    if ERROR_KEY in response and response[ERROR_KEY] is not None:
        failed = True
        print(f'ANKI_CONNECT (error): {response[ERROR_KEY]}')

    if failed:
        pprint.pp(response)

    return response[RESULT_KEY]
