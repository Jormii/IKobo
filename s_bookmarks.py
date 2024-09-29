import os
from typing import Dict, List, Set

import kobo
from kobo import KEPUB, BookmarkContext, BookmarkTable
from c_bookmarks import IFormatter

# NOTE: Configure these
# --------------------------------------------------------------------------------
from c_bookmarks import MarkdownFormatter

ENCODING = 'utf-8'
OUTPUT_DIR = './bookmarks'

INDENT = 4
TIMESTAMP_FMT = '%Y-%m-%d'
CREATED_STR = 'Creado'
MODIFIED_STR = 'Modificado'
ANNOTATION_STR = 'Anotación'
EMPTY_TABLE_CELL_STR = '(...)'

FORMATTER = MarkdownFormatter(
    INDENT,
    TIMESTAMP_FMT,
    CREATED_STR,
    MODIFIED_STR,
    ANNOTATION_STR,
    EMPTY_TABLE_CELL_STR
)
# --------------------------------------------------------------------------------


class KEPUBBookmarks:

    class Pair:

        def __init__(self, bookmark: BookmarkTable, context: BookmarkContext) -> None:
            self.bookmark = bookmark
            self.context = context

    def __init__(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> None:
        self.kepub = kepub
        self.metadata = metadata
        self.bookmarks: List[KEPUBBookmarks.Pair] = []


def main() -> int:
    exit_code = 0
    assert os.path.isdir(OUTPUT_DIR)

    bookmark_rows = BookmarkTable.select_all()

    not_kepubs: Set[str] = set()
    dont_exist: Set[str] = set()
    kepubs: Dict[str, KEPUBBookmarks] = {}
    for i, bookmark_row in enumerate(bookmark_rows):
        print(f'{i + 1} / {len(bookmark_rows)}...\r', end='')

        volume_id = bookmark_row.volume_id

        if not KEPUB.is_kepub(volume_id):
            if volume_id not in not_kepubs:
                print(f' ! Not a KEPUB: {volume_id}')

            not_kepubs.add(volume_id)
            continue

        file = kobo.volume_id_file(volume_id)
        if not os.path.isfile(file):
            if volume_id not in dont_exist:
                print(f' ! KEPUB does not exists: {volume_id}')

            dont_exist.add(volume_id)
            continue

        if volume_id not in kepubs:
            _kepub, metadata = KEPUB.open(volume_id, ENCODING)
            kepubs[volume_id] = KEPUBBookmarks(_kepub, metadata)

        kepub = kepubs[volume_id]
        context = BookmarkContext.extract(bookmark_row, kepub.kepub)
        kepubs[volume_id].bookmarks.append(KEPUBBookmarks.Pair(bookmark_row, context))  # nopep8

    for volume_id, kepub in kepubs.items():
        print(f'{volume_id}...')

        toc = kepub.metadata.table_of_contents
        toc_indices = {k: i for i, k in enumerate(toc)}

        kepub.bookmarks.sort(
            key=lambda pair: (
                toc_indices[pair.context.content_id.xhtml],
                pair.context.bookmark_start.tag.sourceline,
                pair.context.bookmark_start.tag.sourcepos,
            )
        )

        dst_file = os.path.join(
            OUTPUT_DIR,
            FORMATTER.filename(kepub.kepub, kepub.metadata)
        )

        with open(dst_file, 'w', encoding=ENCODING) as fd:
            begin_md = FORMATTER.begin(kepub.kepub, kepub.metadata)
            fd.write(begin_md)

            # First chapter
            pair = kepub.bookmarks[0]
            args = IFormatter.FormattingParams(
                pair.bookmark, pair.context, kepub.kepub, kepub.metadata, OUTPUT_DIR)

            new_chapter_md = FORMATTER.new_chapter(args)
            fd.write(new_chapter_md)
            # END: First chapter

            chapter = pair.context.chapter
            for pair in kepub.bookmarks:
                context = pair.context
                bookmark_row = pair.bookmark

                args = IFormatter.FormattingParams(
                    bookmark_row, context, kepub.kepub, kepub.metadata, OUTPUT_DIR)

                if context.chapter != chapter:
                    chapter = context.chapter

                    new_chapter_md = FORMATTER.new_chapter(args)
                    fd.write(new_chapter_md)

                match bookmark_row.bookmark_type:
                    case BookmarkTable.BookmarkType.NOTE:
                        bookmark_md = FORMATTER.format_note(args)
                    case BookmarkTable.BookmarkType.HIGHLIGHT:
                        bookmark_md = FORMATTER.format_highlight(args)
                    case _:
                        raise NotImplementedError(bookmark_row.bookmark_type)

                fd.write(bookmark_md)

            end_md = FORMATTER.end(kepub.kepub, kepub.metadata)
            fd.write(end_md)

    return exit_code


if __name__ == '__main__':
    exit(main())
