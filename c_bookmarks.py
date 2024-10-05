import os
from datetime import datetime
from typing import List, Callable
from urllib import parse as urllib_parse

from bs4 import PageElement, Tag

from kobo import KEPUB, BookmarkContext, BookmarkTable
from web import Element


class KEPUBBookmarks:

    class Pair:

        def __init__(self, bookmark: BookmarkTable, context: BookmarkContext) -> None:
            self.bookmark = bookmark
            self.context = context

    def __init__(self, kepub: KEPUB, metadata: KEPUB.Metadata) -> None:
        self.kepub = kepub
        self.metadata = metadata

        self.pairs: List[KEPUBBookmarks.Pair] = []


class IFormatter:

    class FormattingParams:

        def __init__(
                self,
                pairs: List[KEPUBBookmarks.Pair],
                containers: List[Element],
                kepub: KEPUB,
                metadata: KEPUB.Metadata,
                output_dir: str,
        ) -> None:
            self.pairs = pairs
            self.containers = containers
            self.kepub = kepub
            self.metadata = metadata
            self.output_dir = output_dir

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
            self.unquoted_pair_indices = set(range(len(self.args.pairs)))

        def indentation(self) -> str:
            return self.indentation_level * ' '

        def get_bookmark(self) -> KEPUBBookmarks.Pair | None:
            if len(self.unquoted_pair_indices) == 0:
                return None

            pair_idx = min(self.unquoted_pair_indices)
            return self.args.pairs[pair_idx]

    def __init__(
            self,
            indent: int,
            timestamp_fmt: str,
            created_str: str,
            modified_str: str,
            annotation_str: str,
    ) -> None:
        self.indent = indent
        self.timestamp_fmt = timestamp_fmt
        self.created_str = created_str
        self.modified_str = modified_str
        self.annotation_str = annotation_str

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
        context = args.pairs[0].context
        formatting = MarkdownFormatter.Formatting(args, self)

        headings_md = [context.title]
        for level in sorted(context.headings.keys()):
            heading = context.headings[level]

            heading_md = self._format_children(heading, formatting)
            headings_md.append(heading_md)

        markdown = f'## {" / ".join(headings_md)}\n'
        return markdown

    def format_note(self, args: IFormatter.FormattingParams) -> str:
        markdown = self._quote_bookmark(args)
        return markdown

    def format_highlight(self, args: IFormatter.FormattingParams) -> str:
        markdown = self._quote_bookmark(args)
        return markdown

    def _quote_bookmark(self, args: IFormatter.FormattingParams) -> str:
        containers = args.containers
        containers_md = self.format_args(args)

        markdown = ''

        _zip = zip(containers, containers_md, strict=True)
        for i, (container, container_md) in enumerate(_zip):
            splitted = container_md.split('\n')
            lines = [line for line in splitted if len(line) != 0]

            if container.name != 'table':
                container_md = '\n'.join(lines)
                container_md = f'> {container_md}'
            else:
                rows_md = [f'> {line}' for line in lines]
                container_md = '\n'.join(rows_md)

            if (i + 1) != len(containers):
                newline = '\n>\n'
            else:
                newline = '\n'

            markdown += f'{container_md}{newline}'

        for i, pair in enumerate(args.pairs):
            bookmark = pair.bookmark
            is_note = bookmark.bookmark_type == BookmarkTable.BookmarkType.NOTE

            footnote_md = f'IK.{i + 1}'
            bookmark_endl = ' \\\n' if is_note else '\n'

            markdown += '> ___\n'
            markdown += f'>> {footnote_md} \\\n'
            markdown += f'>> **{self.created_str}**: {self.timestamp_str(bookmark.date_created)} \\\n'
            markdown += f'>> **{self.modified_str}**: {self.timestamp_str(bookmark.date_modified)}{bookmark_endl}'

            if is_note:
                markdown += ''
                markdown += f'>> **{self.annotation_str}**: {bookmark.annotation}\n'

        markdown += '\n'
        return markdown

    def timestamp_str(self, timestamp: datetime) -> str:
        timestamp = timestamp.astimezone(self.local_tz)
        timestamp_str = timestamp.strftime(self.timestamp_fmt)

        return timestamp_str

    def format_args(self, args: IFormatter.FormattingParams) -> List[str]:
        containers_md: List[str] = []

        formatting = MarkdownFormatter.Formatting(args, self)
        for element in args.containers:
            container_md = self._format_fp(element)(element, formatting)
            containers_md.append(container_md)

        assert len(formatting.unquoted_pair_indices) == 0

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
            case 'img':
                return self._format_img
            case 'table':
                return self._format_table
            case 'span':
                return self._format_span
            case 'div':
                return self._format_div
            case 'em' | 'small' | 'sup' | 'sub' | 'cite':
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
            return ''

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
        kepub = formatting.args.kepub
        metadata = formatting.args.metadata
        output_dir = formatting.args.output_dir
        pair = formatting.get_bookmark()

        assert pair is not None
        content_id = pair.context.content_id

        src = element.get_attr('src')
        xhtml_dir, _ = os.path.split(content_id.xhtml)
        zip_name = os.path.normpath(os.path.join(xhtml_dir, src))
        if os.name == 'nt':
            zip_name = '/'.join(zip_name.split(os.sep))

        dirname = f'{self.filename(kepub, metadata)}.imgs'
        imgs_dir = os.path.join(output_dir, dirname)
        os.makedirs(imgs_dir, exist_ok=True)

        _, img_filename = os.path.split(src)
        file = os.path.join(imgs_dir, img_filename)
        with open(file, 'wb') as fd:
            bytes = kepub.read(zip_name)
            fd.write(bytes)

        markdown_path = f'{dirname}/{img_filename}'
        markdown_path = urllib_parse.quote(markdown_path)
        markdown = f'![{img_filename}]({markdown_path})'

        return markdown

    def _format_table(self, element: Element, formatting: Formatting) -> str:
        headers: List[str] = []
        rows: List[List[str]] = []

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
                dst_row.append(cell_md)

        width = max(
            len(headers),
            max((len(r) for r in rows))
        )

        def fill(_row: List[str]) -> None:
            _n = width - len(_row)
            _row.extend(_n * [''])

        fill(headers)
        for row in rows:
            fill(row)

        markdown = ''

        markdown += '| ' + ' | '.join(headers) + ' |\n'
        markdown += '| ' + ' | '.join(width * ['---']) + ' |\n'

        for row in rows:
            markdown += '| ' + ' | '.join(row) + ' |\n'

        return markdown

    def _format_th(self, element: Element, formatting: Formatting) -> str:
        return self._format_td(element, formatting)

    def _format_td(self, element: Element, formatting: Formatting) -> str:
        children_md = self._format_children(element, formatting)
        return children_md

    def _format_span(self, element: Element, formatting: Formatting) -> str:
        markdown = self._format_children(element, formatting)

        pairs = formatting.args.pairs
        in_span_indices: List[int] = []
        for pair_idx in formatting.unquoted_pair_indices:
            pair = pairs[pair_idx]

            context = pair.context
            if element == context.bookmark_start or element == context.bookmark_end:
                in_span_indices.append(pair_idx)

        for pair_idx in sorted(in_span_indices, reverse=True):
            pair = pairs[pair_idx]
            context = pair.context

            if element == context.bookmark_end:
                idx = context.bookmark_end_offset

                sup_md = f'<sup>[IK.{pair_idx + 1}]</sup>'
                markdown = f'{markdown[:idx]}</b></u>{sup_md}{markdown[idx:]}'

                formatting.unquoted_pair_indices.remove(pair_idx)

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
