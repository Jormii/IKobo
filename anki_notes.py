from __future__ import annotations
from typing import Dict, List, Sequence, Type

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
    def create(cls, args: CreateParams) -> INote | None:
        raise NotImplementedError(cls)


class RAENote(INote):

    class Entry:

        def __init__(self, definition: str, synonyms: List[str], antonyms: List[str]) -> None:
            self.definition = definition
            self.synonyms = synonyms
            self.antonyms = antonyms

        @staticmethod
        def create(paragraph: Element) -> RAENote.Entry:
            children = paragraph.children()

            entry_number = children.pop(0)
            assert entry_number.tag.name == 'span' and entry_number.cls() == 'n_acep'

            definition = ' '.join((t.text for t in children))

            synonyms: List[str] = []
            antonyms: List[str] = []
            siblings = paragraph.next_siblings()
            if len(siblings) != 0 and siblings[0].name == 'div':
                div = siblings[0]
                tds = div.find_all('td')
                assert len(tds) != 0 and (len(tds) % 2) == 0

                for i in range(0, len(tds), 2):
                    abbr = tds[i]
                    ul = tds[i + 1]

                    match abbr.text:
                        case 'Sin.:':
                            dst_list = synonyms
                        case 'Ant.:':
                            dst_list = antonyms
                        case _:
                            raise NotImplementedError(abbr.name)

                    for span in ul.find_all('span', classes={'sin'}):
                        dst_list.append(span.text)

                    assert len(dst_list) != 0

            entry = RAENote.Entry(definition, synonyms, antonyms)
            return entry

    class Article:

        def __init__(
                self,
                headword: str,
                supplementary_info: str,
                entries: List[RAENote.Entry]
        ) -> None:
            self.headword = headword
            self.supplementary_info = supplementary_info
            self.entries = entries

        def format(self) -> str:
            entries_html = '<ol>'
            for entry in self.entries:
                syno_and_anto_html = ''
                if len(entry.synonyms) != 0 or len(entry.antonyms) != 0:
                    if len(entry.synonyms) != 0:
                        syno_and_anto_html += f'<li>Sin.: {", ".join(entry.synonyms)}</li>'

                    if len(entry.synonyms) != 0:
                        syno_and_anto_html += f'<li>Ant.: {", ".join(entry.antonyms)}</li>'

                    syno_and_anto_html = f'<ul>{syno_and_anto_html}</ul>'

                entries_html += f'<li>{entry.definition}{syno_and_anto_html}</li>'
            entries_html += '</ol>'

            return entries_html

        @staticmethod
        def create(article: Element) -> RAENote.Article:
            supplementary_info = ''
            entries: List[RAENote.Entry] = []

            header = article.find('header')
            paragraphs = article.find_all('p')
            for paragraph in paragraphs:
                p_class = paragraph.cls_or_none()
                if p_class is None:
                    assert len(paragraph.text) == 0
                    continue  # NOTE: There may be empty paragraphs

                match p_class[0]:
                    case 'n':   # Suplementary
                        supplementary_info = paragraph.text
                    case 'j':   # Entry
                        entries.append(RAENote.Entry.create(paragraph))
                    case 'k':   # Complex form headword
                        raise NotImplementedError(paragraph)
                    case 'm':   # Complex form entry
                        raise NotImplementedError(paragraph)
                    case 'l':   # Linked complex form
                        raise NotImplementedError(paragraph)
                    case _:
                        raise NotImplementedError(p_class)

            return RAENote.Article(header.text, supplementary_info, entries)

    def __init__(self, url: str, articles: List[Article]) -> None:
        super().__init__('RAE')

        self.url = url
        self.articles = articles

    def format(self) -> Dict[str, str]:
        main_article = self.articles[0]
        headword_html = f'<a href="{self.url}">{main_article.headword}</a>'

        articles_htmls = (f'<div>{a.format()}</div>' for a in self.articles)
        articles_html = '<br>'.join(articles_htmls)

        return {
            'lema': headword_html,
            'informacion_complementaria': main_article.supplementary_info,
            'acepciones_simples': articles_html,
        }

    @classmethod
    def create(cls, args: INote.CreateParams) -> INote | None:
        # NOTE: https://dle.rae.es/contenido/ayuda#IG2

        url = f'https://dle.rae.es/{args.text}'
        html = Element.parse_html(args.selenium.get(url))

        articles = html.find_all('article')
        if len(articles) == 0:
            return None

        rae_articles: List[RAENote.Article] = []
        for article in articles:
            rae_article = RAENote.Article.create(article)
            rae_articles.append(rae_article)

        note = RAENote(url, rae_articles)
        return note
