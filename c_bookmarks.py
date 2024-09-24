from kobo import KEPUB, BookmarkTable


class IBookmarks:

    def filename(self, kepub_filename_no_ext: str) -> str:
        raise NotImplementedError(type(self))

    def new_chapter(self, chapter: str) -> str:
        raise NotImplementedError(type(self))

    def format_note(self, bookmark: BookmarkTable, chapter: str, kepub: KEPUB) -> str:
        raise NotImplementedError(type(self))

    def format_highlight(self, bookmark: BookmarkTable, chapter: str, kepub: KEPUB) -> str:
        raise NotImplementedError(type(self))


class BasicBookmarks(IBookmarks):

    def filename(self, kepub_filename_no_ext: str) -> str:
        return f'{kepub_filename_no_ext}.txt'

    def new_chapter(self, chapter: str) -> str:
        return f'----- {chapter} -----\n'

    def format_note(self, bookmark: BookmarkTable, chapter: str, kepub: KEPUB) -> str:
        return f'NOTE: {bookmark.text} || {bookmark.annotation}\n'

    def format_highlight(self, bookmark: BookmarkTable, chapter: str, kepub: KEPUB) -> str:
        return f'HIGHLIGHT: {bookmark.text}\n'
