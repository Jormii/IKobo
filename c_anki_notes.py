from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Type

from bs4 import Tag

from web import Element, Selenium


class Deck:

    def __init__(self, name: str, inote_cls: Type[INote]) -> None:
        self.name = name
        self.inote_cls = inote_cls


class INote:

    class CreateParams:

        def __init__(self, text: str, selenium: Selenium) -> None:
            self.text = text
            self.selenium = selenium

    def __init__(self, type: str) -> None:
        self.type = type

    def format(self) -> Dict[str, str]:
        raise NotImplementedError(type(self))

    @classmethod
    def create(cls, args: CreateParams) -> Dict[str, INote]:
        raise NotImplementedError(cls)


class RAENote(INote):

    @dataclass(slots=True, frozen=True)
    class Article:
        word: str
        element: Element
        sections: List[Element]

        @staticmethod
        def create(element: Element) -> RAENote.Article:
            assert element.name == 'article'

            word = element.find('h1')
            sections = element.find_all('section')

            article = RAENote.Article(word.text, element, sections)
            return article

    def __init__(self, url: str, h1: Element, article: Article) -> None:
        super().__init__('RAE')

        self.url = url
        self.h1 = h1
        self.article = article

    def format(self) -> Dict[str, str]:
        return {
            'h1': self._format_rec(self.h1),
            'html': '\n'.join((self._format_rec(s) for s in self.article.sections)),  # nopep8
        }

    def _format_rec(self, element: Element) -> str:
        children = element.children()
        if len(children) == 0:
            text = element.text
        else:
            children_html: List[str] = []
            for child in element.tag.contents:
                if isinstance(child, str):
                    child_html: str = child
                else:
                    assert isinstance(child, Tag)
                    child_html = self._format_rec(Element(child, element.parsed_html))  # nopep8

                children_html.append(child_html)

            text = ''.join(children_html)

        html = f'<{element.name}>{text}</{element.name}>'
        return html

    @classmethod
    def create(cls, args: INote.CreateParams) -> Dict[str, INote]:
        # NOTE: https://dle.rae.es/contenido/ayuda#IG2

        url = f'https://dle.rae.es/{args.text}'
        html = Element.parse_html(args.selenium.get(url))

        h1s = html.find_all('h1')
        if len(h1s) == 0:
            return {}

        notes: Dict[str, INote] = {}
        articles = html.find_all('article')
        for h1, html_article in zip(h1s, articles):
            article = RAENote.Article.create(html_article)
            notes[article.word] = RAENote(url, h1, article)

        return notes
