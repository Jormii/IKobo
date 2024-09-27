from __future__ import annotations
import os
import re
import sqlite3
from zipfile import ZipFile
from enum import IntEnum, auto
from typing import Dict, List, Tuple
from datetime import datetime, timezone

from web import Element

# NOTE: Configure these
# --------------------------------------------------------------------------------
VOLUME = r'E:'
# --------------------------------------------------------------------------------


class KEPUB:

    class Metadata:

        def __init__(
                self,
                title: str | None,
                author: str | None,
                publisher: str | None,
                table_of_contents: List[str]
        ) -> None:
            self.title = title
            self.author = author
            self.publisher = publisher
            self.table_of_contents = table_of_contents

    def __init__(self, file: str, volume_id: str, encoding: str) -> None:
        self.file = file
        self.volume_id = volume_id
        self.encoding = encoding

        self.zip_file = ZipFile(self.file)
        self.zip_cache: Dict[str, bytes] = {}

    def read(self, zip_name: str) -> bytes:
        if zip_name not in self.zip_cache:
            self.zip_cache[zip_name] = self.zip_file.read(zip_name)

        return self.zip_cache[zip_name]

    def read_str(self, zip_name: str) -> str:
        bytes = self.read(zip_name)
        return bytes.decode(self.encoding)

    @staticmethod
    def is_kepub(volume_id: str) -> bool:
        KEPUB_REGEX = r'\.kepub\.epub$'

        file = volume_id_file(volume_id)
        search = re.search(KEPUB_REGEX, file)

        return search is not None

    @staticmethod
    def open(volume_id: str, encoding: str) -> Tuple[KEPUB, Metadata]:
        file = volume_id_file(volume_id)
        kepub = KEPUB(file, volume_id, encoding)

        content = kepub.read_str('content.opf')
        parsed_content = Element.parse_html(content)
        content_metadata = parsed_content.find('metadata')

        title = KEPUB._metadata('dc:title', content_metadata)
        author = KEPUB._metadata('dc:creator', content_metadata)
        publisher = KEPUB._metadata('dc:publisher', content_metadata)
        table_of_contents = KEPUB._table_of_contents(parsed_content)

        metadata = KEPUB.Metadata(title, author, publisher, table_of_contents)
        return kepub, metadata

    @staticmethod
    def _metadata(name: str, metadata: Element) -> str | None:
        dc = metadata.find_or_none(name)
        if dc is None:
            return None
        else:
            return dc.text

    @staticmethod
    def _table_of_contents(content: Element) -> List[str]:
        manifest_dict: Dict[str, str] = {}
        manifest = content.find('manifest')
        for item in manifest.find_all('item'):
            id = item.get_attr('id')
            href = item.get_attr('href')

            manifest_dict[id] = href

        spine = content.find('spine')
        table_of_contents: List[str] = []
        for item in spine.find_all('itemref'):
            id = item.get_attr('idref')
            if id in manifest_dict:
                href = manifest_dict[id]
                table_of_contents.append(href)

        return table_of_contents


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


class BookmarkContext:

    def __init__(
            self,
            chapter: Element,
            containers: List[Element],
            bookmark_start: Element,
            bookmark_start_offset: int,
            bookmark_end: Element,
            bookmark_end_offset: int,
    ) -> None:
        self.chapter = chapter
        self.containers = containers
        self.bookmark_start = bookmark_start
        self.bookmark_start_offset = bookmark_start_offset
        self.bookmark_end = bookmark_end
        self.bookmark_end_offset = bookmark_end_offset

        # NOTE: Provisional
        assert self.bookmark_start.name == 'span'
        assert self.bookmark_end.name == 'span'

    @staticmethod
    def extract(bookmark: BookmarkTable, kepub: KEPUB) -> BookmarkContext:
        CHAPTER_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

        content = ContentID.parse(bookmark.content_id)
        assert bookmark.volume_id == kepub.volume_id and content.file == kepub.file

        xhtml = kepub.read_str(content.xhtml)
        parsed_xhtml = Element.parse_html(xhtml)
        inner_div = parsed_xhtml.find_with_id('div', 'book-inner')

        bookmark_start, start_parent = BookmarkContext._extract(
            bookmark.start_container_path, inner_div, grab_first_or_last=True)
        bookmark_end, end_parent = BookmarkContext._extract(
            bookmark.end_container_path, inner_div, grab_first_or_last=False)

        containers = inner_div.children()
        while containers[0] != start_parent:
            del containers[0]

        for i in reversed(range(1, len(containers))):
            if containers[i] == end_parent:
                break
            else:
                del containers[i]

        top_container = containers[0]
        siblings = top_container.prev_siblings()
        siblings.insert(0, top_container)

        chapter: Element | None = None
        for i in range(len(siblings)):
            sibling = siblings[i]

            if sibling.name in CHAPTER_TAGS:
                chapter = sibling
                break

        assert chapter is not None

        return BookmarkContext(
            chapter,
            containers,
            bookmark_start, bookmark.start_offset,
            bookmark_end, bookmark.end_offset,
        )

    @staticmethod
    def _extract(
            container_path: str,
            inner_div: Element,
            grab_first_or_last: bool
    ) -> Tuple[Element, Element]:
        CONTAINER_PATH_REGEX = r'^(.*)#(.*)$'

        search = re.search(CONTAINER_PATH_REGEX, container_path)
        assert search is not None

        tag, id = search.groups()
        id = id.replace('\.', '.')  # NOTE: '.' are escaped as '\.'

        # NOTE: Apparently there is an odd behavior when highlights are near images
        #   Scenarios found so far:
        #       - Highlight is an image
        #       - Image and span share id

        elements = inner_div.find_all_with_id(tag, id)
        assert len(elements) != 0

        if grab_first_or_last:
            element = elements[0]
        else:
            element = elements[-1]

        container = element.parent()
        while (parent := container.parent()) != inner_div:
            container = parent

        return element, container


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
            start_container_path: str,
            start_offset: int,
            end_container_path: str,
            end_offset: int,
            text: str,
            annotation: str,
            date_created: datetime,
            chapter_progress: float,
            date_modified: datetime,
            bookmark_type: BookmarkType
    ) -> None:
        self.volume_id = volume_id
        self.content_id = content_id
        self.start_container_path = start_container_path
        self.start_offset = start_offset
        self.end_container_path = end_container_path
        self.end_offset = end_offset
        self.text = text
        self.annotation = annotation
        self.date_created = date_created
        self.chapter_progress = chapter_progress
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
                row[BookmarkTable.START_CONTAINER_PATH_COL],
                row[BookmarkTable.START_OFFSET_COL],
                row[BookmarkTable.END_CONTAINER_PATH_COL],
                row[BookmarkTable.END_OF_OFFSET_COL],
                text.strip(),
                annotation.strip() if annotation is not None else '',
                datetime.strptime(date_created, DATE_CREATED_FMT).replace(tzinfo=timezone.utc),  # nopep8
                row[BookmarkTable.CHAPTER_PROGRESS_COL],
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
