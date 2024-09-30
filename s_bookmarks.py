import os
from typing import Dict, List, Set

import kobo
from kobo import KEPUB, BookmarkContext, BookmarkTable
from web import Element

from c_bookmarks import IFormatter, KEPUBBookmarks

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

FORMATTER = MarkdownFormatter(
    INDENT,
    TIMESTAMP_FMT,
    CREATED_STR,
    MODIFIED_STR,
    ANNOTATION_STR,
)
# --------------------------------------------------------------------------------

# TODO: Improve chapters


class GroupedBookmarks:

    def __init__(self, pairs: List[KEPUBBookmarks.Pair], containers: List[Element]) -> None:
        self.pairs = pairs
        self.containers = containers


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
        kepubs[volume_id].pairs.append(KEPUBBookmarks.Pair(bookmark_row, context))  # nopep8

    for volume_id, kepub in kepubs.items():
        print(f'{volume_id}...')

        toc = kepub.metadata.table_of_contents
        toc_indices = {k: i for i, k in enumerate(toc)}

        kepub.pairs.sort(
            key=lambda pair: (
                toc_indices[pair.context.content_id.xhtml],
                pair.context.bookmark_start.tag.sourceline,
                pair.context.bookmark_start.tag.sourcepos,
            )
        )

        grouped_pairs = _group_bookmarks(kepub.pairs)
        assert sum(len(gp.pairs) for gp in grouped_pairs) == len(kepub.pairs)

        dst_file = os.path.join(
            OUTPUT_DIR,
            FORMATTER.filename(kepub.kepub, kepub.metadata)
        )

        with open(dst_file, 'w', encoding=ENCODING) as fd:
            begin_md = FORMATTER.begin(kepub.kepub, kepub.metadata)
            fd.write(begin_md)

            # First chapter
            g_pairs = grouped_pairs[0]
            args = IFormatter.FormattingParams(
                g_pairs.pairs, g_pairs.containers, kepub.kepub, kepub.metadata, OUTPUT_DIR)

            new_chapter_md = FORMATTER.new_chapter(args)
            fd.write(new_chapter_md)
            # END: First chapter

            chapter = g_pairs.pairs[0].context.chapter
            for g_pairs in grouped_pairs:
                args = IFormatter.FormattingParams(
                    g_pairs.pairs, g_pairs.containers, kepub.kepub, kepub.metadata, OUTPUT_DIR)

                g_chapter = g_pairs.pairs[0].context.chapter
                if g_chapter != chapter:
                    chapter = g_chapter

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


def _group_bookmarks(pairs: List[KEPUBBookmarks.Pair]) -> List[GroupedBookmarks]:
    grouped_pairs: List[GroupedBookmarks] = []

    begin = 0
    while begin < len(pairs):
        begin_pair = pairs[begin]

        begin_chapter = begin_pair.context.chapter
        begin_xhtml = begin_pair.context.content_id.xhtml
        bottommost_container = begin_pair.context.containers[-1]

        end = begin + 1
        while end < len(pairs):
            end_pair = pairs[end]

            end_chapter = end_pair.context.chapter
            end_xhtml = end_pair.context.content_id.xhtml
            end_first_container = end_pair.context.containers[0]

            if end_xhtml != begin_xhtml:
                break

            if end_chapter != begin_chapter:
                break

            end_sourceline = end_first_container.tag.sourceline
            bottommost_sourceline = bottommost_container.tag.sourceline
            assert end_sourceline is not None and bottommost_sourceline is not None

            if end_sourceline > bottommost_sourceline:
                break

            end += 1
            bottommost_container = end_pair.context.containers[-1]

        g_pairs = pairs[begin:end]
        g_containers: List[Element] = []

        g_containers.extend(g_pairs[0].context.containers)
        for i in range(1, len(g_pairs)):
            pair = g_pairs[i]

            for container in pair.context.containers:
                sourceline = container.tag.sourceline
                bottommost_sourceline = g_containers[-1].tag.sourceline
                assert sourceline is not None and bottommost_sourceline is not None

                if sourceline > bottommost_sourceline:
                    g_containers.append(container)

        group = GroupedBookmarks(g_pairs, g_containers)

        begin = end
        grouped_pairs.append(group)

    return grouped_pairs


if __name__ == '__main__':
    exit(main())
