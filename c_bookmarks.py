import os
from datetime import datetime
from typing import List, Callable

from bs4 import PageElement, Tag

from kobo import KEPUB, BookmarkContext, BookmarkTable
from web import Element


class IFormatter:

    class FormattingParams:

        def __init__(
                self,
                bookmark: BookmarkTable,
                context: BookmarkContext,
                kepub: KEPUB,
                metadata: KEPUB.Metadata
        ) -> None:
            self.bookmark = bookmark
            self.context = context
            self.kepub = kepub
            self.metadata = metadata

    def filename(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> str:
        raise NotImplementedError(type(self))

    def begin(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> str:
        raise NotImplementedError(type(self))

    def end(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> str:
        raise NotImplementedError(type(self))

    def new_chapter(self, args: FormattingParams) -> str:
        raise NotImplementedError(type(self))

    def format_note(self, args: FormattingParams) -> str:
        raise NotImplementedError(type(self))

    def format_highlight(self, args: FormattingParams) -> str:
        raise NotImplementedError(type(self))


class MarkdownFormatter(IFormatter):

    class Formatting:

        def __init__(self, args: IFormatter.FormattingParams, formatter: 'MarkdownFormatter') -> None:
            self.args = args
            self.formatter = formatter

            self.indentation_level = 0

        def indentation(self) -> str:
            return self.indentation_level * ' '

    def __init__(
            self,
            indent: int,
            timestamp_fmt: str,
            created_str: str,
            modified_str: str,
            annotation_str: str,
            no_chapter_str: str,
            empty_table_cell_str: str
    ) -> None:
        self.indent = indent
        self.timestamp_fmt = timestamp_fmt
        self.created_str = created_str
        self.modified_str = modified_str
        self.annotation_str = annotation_str
        self.no_chapter_str = no_chapter_str
        self.empty_table_cell_str = empty_table_cell_str

        self.local_tz = datetime.now().astimezone().tzinfo

    def filename(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> str:
        if metadata.title is None:
            assert 0, 'NOT DEBUGGED'
            _, filename = os.path.split(kepub.file)
            filename, _ = os.path.splitext(filename)
        else:
            filename = metadata.title

            if metadata.author is not None:
                filename = f'{metadata.author}. {filename}'
            if metadata.publisher is not None:
                filename = f'{filename}. {metadata.publisher}'
            if metadata.timestamp is not None:
                filename = f'{filename}. {metadata.timestamp.year}'

        return f'{filename}.md'

    def begin(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> str:
        title = metadata.title
        if title is None:
            assert 0, 'NOT DEBUGGED'
            _, title = os.path.split(kepub.file)
            title, _ = os.path.splitext(title)

        markdown = '---\n---\n'
        markdown += f'# {title}\n'
        markdown += '> [!INFO] Tags\n'
        markdown += '> - [[]]\n\n'

        return markdown

    def end(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> str:
        markdown = '# Referencias\n'
        markdown += '- [[]]'

        return markdown

    def new_chapter(self, args: IFormatter.FormattingParams) -> str:
        chapters_md: List[str] = []
        chapters = args.context.chapters
        if len(chapters) == 0:
            chapters_md.append(self.no_chapter_str)
        else:
            formatting = MarkdownFormatter.Formatting(args, self)

            for level in sorted(chapters.keys()):
                chapter = chapters[level]

                children_md = self._format_children(chapter, formatting)
                chapters_md.append(children_md)

        markdown = f'## '
        markdown += ' / '.join(chapters_md)

        markdown += f'\n'
        return markdown

    def format_note(self, args: IFormatter.FormattingParams) -> str:
        markdown = self._quote_bookmark(args)
        markdown += f'>> **{self.annotation_str}**: {args.bookmark.annotation}\n'
        markdown += '\n'

        return markdown

    def format_highlight(self, args: IFormatter.FormattingParams) -> str:
        markdown = self._quote_bookmark(args)
        markdown += '\n'

        return markdown

    def _quote_bookmark(self, args: IFormatter.FormattingParams) -> str:
        bookmark = args.bookmark
        containers = args.context.containers
        containers_md = self.format_args(args)

        markdown = ''

        _zip = zip(args.context.containers, containers_md, strict=True)
        for i, (container, container_md) in enumerate(_zip):
            splitted = container_md.split('\n')
            lines = [l for l in splitted if len(l) != 0]

            if container.name != 'table':
                container_md = '\n'.join(lines)
                container_md = f'> {container_md}'
            else:
                rows_md = [f'> {l}' for l in lines]
                container_md = '\n'.join(rows_md)

            if (i + 1) != len(containers):
                newline = '\n>\n'
            else:
                newline = '\n'

            markdown += f'{container_md}{newline}'

        markdown += '>\n'
        markdown += f'>> **{self.created_str}**: {self.timestamp_str(bookmark.date_created)} \\\n'
        markdown += f'>> **{self.modified_str}**: {self.timestamp_str(bookmark.date_modified)}\n'

        return markdown

    def timestamp_str(self, timestamp: datetime) -> str:
        timestamp = timestamp.astimezone(self.local_tz)
        timestamp_str = timestamp.strftime(self.timestamp_fmt)

        return timestamp_str

    def format_args(self, args: IFormatter.FormattingParams) -> List[str]:
        containers_md: List[str] = []

        formatting = MarkdownFormatter.Formatting(args, self)
        for element in args.context.containers:
            container_md = self._format_fp(element)(element, formatting)
            containers_md.append(container_md)

        return containers_md

    def _format_fp(self, element: Element) -> Callable[[Element, Formatting], str]:
        match element.name:
            case 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6':
                return self._format_header
            case 'i':
                return self._format_italic
            case 'a':
                return self._format_link
            case 'p':
                return self._format_paragraph
            case 'table':
                return self._format_table
            case 'span':
                return self._format_span
            case 'div':
                return self._format_div
            case 'em' | 'small' | 'sup' | 'sub':
                return self._format_html
            case _:
                raise NotImplementedError(element.name)

    def _format_header(self, element: Element, formatting: Formatting) -> str:
        level = int(element.name[1])  # 'hX'
        children_md = self._format_children(element, formatting)

        hashes = level * '#'
        markdown = f'{hashes} {children_md}'

        return markdown

    def _format_italic(self, element: Element, formatting: Formatting) -> str:
        children_md = self._format_children(element, formatting)
        markdown = f'*{children_md}*'

        return markdown

    def _format_link(self, element: Element, formatting: Formatting) -> str:
        href = element.get_attr_or_none('href')
        if href is None:
            return ''  # TODO

        # TODO: Internal links

        children_md = self._format_children(element, formatting)
        markdown = f'<a href={href}>{children_md}</a>'

        return markdown

    def _format_paragraph(self, element: Element, formatting: Formatting) -> str:
        markdown = formatting.indentation()

        for content in element.tag.contents:
            child_md = self._format_content(content, element, formatting)
            markdown += child_md

        return markdown

    def _format_img(self, element: Element, formatting: Formatting) -> str:
        # TODO
        return self._format_html(element, formatting)

    def _format_table(self, element: Element, formatting: Formatting) -> str:
        headers: List[str] = []
        rows: List[List[str]] = []
        empty_cell_str = formatting.formatter.empty_table_cell_str

        body = element.find('tbody')
        trs = body.find_all('tr', recursive=False)
        for tr in trs:
            rows.append([])

            for content in tr.tag.contents:
                if not isinstance(content, Tag):
                    assert isinstance(content, str)
                    assert len(content.strip()) == 0

                    continue

                child = Element(content, element.parsed_html)
                match content.name:
                    case 'th':
                        dst_row = headers
                        child_md = self._format_th(child, formatting)
                    case 'td':
                        dst_row = rows[-1]
                        child_md = self._format_td(child, formatting)
                    case _:
                        raise NotImplementedError(content.name)

                cell_md = child_md.strip()
                if len(cell_md) == 0:
                    cell_md = empty_cell_str

                dst_row.append(cell_md)

        width = max(
            len(headers),
            max((len(r) for r in rows))
        )

        def fill(_row: List[str]) -> None:
            _n = width - len(_row)
            _row.extend(_n * [empty_cell_str])

        fill(headers)
        for row in rows:
            fill(row)

        markdown = ''

        # NOTE: The extra pipe makes single-column tables format correctly
        #   and doesn't affect regular tables
        markdown += ' | '.join(headers) + ' | \n'
        markdown += '|'.join(width * ['---']) + '\n'

        for row in rows:
            markdown += ' | '.join(row) + '\n'

        return markdown

    def _format_th(self, element: Element, formatting: Formatting) -> str:
        return self._format_td(element, formatting)

    def _format_td(self, element: Element, formatting: Formatting) -> str:
        children_md = self._format_children(element, formatting)
        return children_md

    def _format_span(self, element: Element, formatting: Formatting) -> str:
        markdown = self._format_children(element, formatting)

        context = formatting.args.context
        if element == context.bookmark_end:
            idx = context.bookmark_end_offset
            markdown = f'{markdown[:idx]}</b></u>{markdown[idx:]}'

        if element == context.bookmark_start:
            idx = context.bookmark_start_offset
            markdown = f'{markdown[:idx]}<u><b>{markdown[idx:]}'

        return markdown

    def _format_div(self, element: Element, formatting: Formatting) -> str:
        children_md = self._format_children(element, formatting)
        return children_md

    def _format_html(self, element: Element, formatting: Formatting) -> str:
        children_md = self._format_children(element, formatting)
        markdown = f'<{element.name}>{children_md}</{element.name}>'

        return markdown

    def _format_children(self, element: Element, formatting: Formatting) -> str:
        markdown = ''

        for content in element.tag.contents:
            child_md = self._format_content(content, element, formatting)
            markdown += child_md

        return markdown

    def _format_content(self, content: PageElement, parent: Element, formatting: Formatting) -> str:
        if isinstance(content, str):
            return content

        assert isinstance(content, Tag)
        element = Element(content, parent.parsed_html)
        markdown = self._format_fp(element)(element, formatting)

        return markdown
