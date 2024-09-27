import os
from typing import Dict, List, Set

import kobo
from kobo import KEPUB, ContentID, BookmarkTable


# NOTE: Configure these
# --------------------------------------------------------------------------------
from c_bookmarks import BasicBookmarks

OUTPUT_DIR = './bookmarks'

ENCODING = 'utf-8'
FORMATTER = BasicBookmarks()
# --------------------------------------------------------------------------------


class KEPUBBookmarks:

    def __init__(self, kepub: KEPUB) -> None:
        self.kepub = kepub
        self.bookmark_rows: List[BookmarkTable] = []


def main() -> int:
    exit_code = 0
    assert os.path.isdir(OUTPUT_DIR)

    bookmark_rows = BookmarkTable.select_all()

    not_kepubs: Set[str] = set()
    dont_exist: Set[str] = set()
    kepubs: Dict[str, KEPUBBookmarks] = {}
    for bookmark_row in bookmark_rows:
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
            kepubs[volume_id] = KEPUBBookmarks(KEPUB.open(volume_id, ENCODING))

        kepubs[volume_id].bookmark_rows.append(bookmark_row)

    for volume_id, kepub in kepubs.items():
        toc = kepub.kepub.table_of_contents()
        toc_indices = {k: i for i, k in enumerate(toc.keys())}
        kepub.bookmark_rows.sort(
            key=lambda bkmrk: (
                toc_indices[ContentID.parse(bkmrk.content_id).xhtml],
                bkmrk.start_container_path  # TODO: Clarify
            )
        )

        file = kepub.kepub.file
        _, filename = os.path.split(file)
        filename_no_ext, _ = os.path.splitext(filename)
        dst_file = os.path.join(
            OUTPUT_DIR,
            FORMATTER.filename(filename_no_ext)
        )

        chapters: List[str] = []
        for bookmark_row in kepub.bookmark_rows:
            chapter = bookmark_row.content_id  # TODO
            chapters.append(chapter)

        with open(dst_file, 'w', encoding=ENCODING) as fd:
            chapter = chapters[0]
            fd.write(FORMATTER.new_chapter(chapter))

            for bookmark_row, bookmark_chapter in zip(kepub.bookmark_rows, chapters, strict=True):
                if bookmark_chapter != chapter:
                    chapter = bookmark_chapter
                    fd.write(FORMATTER.new_chapter(chapter))

                match bookmark_row.bookmark_type:
                    case BookmarkTable.BookmarkType.NOTE:
                        fd.write(FORMATTER.format_note(bookmark_row, chapter, kepub.kepub))  # nopep8
                    case BookmarkTable.BookmarkType.HIGHLIGHT:
                        fd.write(FORMATTER.format_highlight(bookmark_row, chapter, kepub.kepub))  # nopep8
                    case _:
                        raise NotImplementedError(bookmark_row.bookmark_type)

    return exit_code


if __name__ == '__main__':
    exit(main())
