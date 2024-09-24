import os
from typing import Dict, List

from kobo import KEPUB, BookmarkTable
from c_bookmarks import BasicBookmarks


# NOTE: Configure these
# --------------------------------------------------------------------------------
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

    kepubs: Dict[str, KEPUBBookmarks] = {}
    for bookmark_row in bookmark_rows:
        volume_id = bookmark_row.volume_id

        if volume_id not in kepubs:
            kepubs[volume_id] = KEPUBBookmarks(KEPUB.open(volume_id))

        kepubs[volume_id].bookmark_rows.append(bookmark_row)

    for volume_id, kepub in kepubs.items():
        # TODO
        # kepub.bookmark_rows.sort()

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
