from __future__ import annotations
import os
import re
import sqlite3
from zipfile import ZipFile
from typing import Dict, List
from enum import IntEnum, auto
from datetime import datetime, timezone


# NOTE: Configure these
# --------------------------------------------------------------------------------
VOLUME = r'E:'
# --------------------------------------------------------------------------------


class KEPUB:

    def __init__(self, file: str, zip_file: ZipFile) -> None:
        self.file = file
        self.zip_file = zip_file

        self.zip_bytes: Dict[str, bytes] = {}

    def read(self, zip_name: str) -> bytes:
        if zip_name not in self.zip_bytes:
            self.zip_bytes[zip_name] = self.zip_file.read(zip_name)

        return self.zip_bytes[zip_name]

    @staticmethod
    def open(volume_id: str) -> KEPUB:
        file = volume_id_file(volume_id)
        zip_file = ZipFile(file)

        return KEPUB(file, zip_file)


class ContentID:

    def __init__(self, file: str, xhtml: str, element: str | None) -> None:
        self.file = file
        self.xhtml = xhtml
        self.element = element

    @staticmethod
    def parse(content_id: str) -> ContentID:
        CONTENT_ID_REGEX = r'^/mnt/onboard/(.*)!!(.*?)(?:#(.*))?$'

        search = re.search(CONTENT_ID_REGEX, content_id)
        assert search is not None

        rel_file = search.group(1)
        xhtml = search.group(2)
        element = search.group(3)

        file = _format_path(rel_file)
        return ContentID(file, xhtml, element)


class BookmarkTable:

    class BookmarkType(IntEnum):
        NOTE = 0
        HIGHLIGHT = auto()

    TYPE_MAPPING: Dict[str, BookmarkType] = {
        'note': BookmarkType.NOTE,
        'highlight': BookmarkType.HIGHLIGHT,
    }

    TABLE = 'Bookmark'

    BOOKMARK_ID_COL = 'BookmarkID'
    VOLUME_ID_COL = 'VolumeID'
    CONTENT_ID_COL = 'ContentID'
    START_CONTAINER_PATH_COL = 'StartContainerPath'
    START_CONTAINER_CHILD_INDEX_COL = 'StartContainerChildIndex'
    START_OFFSET_COL = 'StartOffset'
    END_CONTAINER_PATH_COL = 'EndContainerPath'
    END_CONTAINER_CHILD_INDEX_COL = 'EndContainerChildIndex'
    END_OF_OFFSET_COL = 'EndOffset'
    TEXT_COL = 'Text'
    ANNOTATION_COL = 'Annotation'
    EXTRA_ANNOTATION_DATA_COL = 'ExtraAnnotationData'
    DATE_CREATED_COL = 'DateCreated'
    CHAPTER_PROGRESS_COL = 'ChapterProgress'
    HIDDEN_COL = 'Hidden'
    VERSION_COL = 'Version'
    DATE_MODIFIED_COL = 'DateModified'
    CREATOR_COL = 'Creator'
    UUID_COL = 'UUID'
    USER_ID_COL = 'UserID'
    SYNC_TIME_COL = 'SyncTime'
    PUBLISHED_COL = 'Published'
    CONTEXT_STRING_COL = 'ContextString'
    TYPE_COL = 'Type'
    COLOR_COL = 'Color'

    def __init__(
            self,
            volume_id: str,
            content_id: str,
            text: str,
            annotation: str,
            date_created: datetime,
            date_modified: datetime,
            bookmark_type: BookmarkType
    ) -> None:
        self.volume_id = volume_id
        self.content_id = content_id
        self.text = text
        self.annotation = annotation
        self.date_created = date_created
        self.date_modified = date_modified
        self.bookmark_type = bookmark_type

    @staticmethod
    def select_all() -> List[BookmarkTable]:
        DATE_CREATED_FMT = '%Y-%m-%dT%H:%M:%S.%f'
        DATE_MODIFIED_FMT = '%Y-%m-%dT%H:%M:%S%z'

        cursor = CONNECTION.execute(f'SELECT * FROM {BookmarkTable.TABLE};')

        rows: List[BookmarkTable] = []
        for row in cursor.fetchall():
            text: str = row[BookmarkTable.TEXT_COL]
            annotation: str | None = row[BookmarkTable.ANNOTATION_COL]
            date_created: str = row[BookmarkTable.DATE_CREATED_COL]
            date_modified: str = row[BookmarkTable.DATE_MODIFIED_COL]
            bookmark_type: str = row[BookmarkTable.TYPE_COL]

            rows.append(BookmarkTable(
                row[BookmarkTable.VOLUME_ID_COL],
                row[BookmarkTable.CONTENT_ID_COL],
                text.strip(),
                annotation.strip() if annotation is not None else '',
                datetime.strptime(date_created, DATE_CREATED_FMT).replace(tzinfo=timezone.utc),  # nopep8
                datetime.strptime(date_modified, DATE_MODIFIED_FMT).replace(tzinfo=timezone.utc),  # nopep8
                BookmarkTable.TYPE_MAPPING[bookmark_type]
            ))

        return rows


class WordListTable:

    TABLE = 'WordList'

    TEXT_COL = 'Text'
    VOLUME_ID_COL = 'VolumeId'
    DICT_SUFFIX_COL = 'DictSuffix'
    DATE_CREATED_COL = 'DateCreated'

    def __init__(self, text: str, volume_id: str, dict_suffix: str, date_created: datetime) -> None:
        self.text = text
        self.volume_id = volume_id
        self.dict_suffix = dict_suffix
        self.date_created = date_created

    @staticmethod
    def select_all() -> List[WordListTable]:
        DATE_CREATED_FMT = '%Y-%m-%dT%H:%M:%S%z'

        cursor = CONNECTION.execute(f'SELECT * FROM {WordListTable.TABLE};')

        rows: List[WordListTable] = []
        for row in cursor.fetchall():
            date_created: str = row[WordListTable.DATE_CREATED_COL]

            rows.append(WordListTable(
                row[WordListTable.TEXT_COL],
                row[WordListTable.VOLUME_ID_COL],
                row[WordListTable.DICT_SUFFIX_COL],
                datetime.strptime(date_created, DATE_CREATED_FMT).replace(tzinfo=timezone.utc),  # nopep8
            ))

        return rows


KOBO_DIR = '.kobo'
DB_FILE = os.path.join(VOLUME, KOBO_DIR, 'KoboReader.sqlite')

assert os.path.isfile(DB_FILE)

CONNECTION = sqlite3.connect(DB_FILE)
CONNECTION.row_factory = sqlite3.Row


def volume_id_file(volume_id: str) -> str:
    VOLUME_ID_REGEX = r'^file:///mnt/onboard/(.*)$'

    search = re.search(VOLUME_ID_REGEX, volume_id)
    assert search is not None

    rel_file = search.group(1)
    file = _format_path(rel_file)

    return file


def _format_path(rel_path: str) -> str:
    SEP = '/'

    if os.name == 'posix':
        path = os.path.join(VOLUME, rel_path)
    else:
        path = os.path.join(VOLUME, *rel_path.split(SEP))

    return path
