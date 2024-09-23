from __future__ import annotations
import time
from typing import List, Set

from bs4 import BeautifulSoup, Tag
from selenium import webdriver  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.remote.webelement import WebElement  # type: ignore


class Element:

    def __init__(self, tag: Tag, parsed_html: BeautifulSoup) -> None:
        self.tag = tag
        self.parsed_html = parsed_html

        self.name = self.tag.name
        self.text = self.tag.text.strip()

    def cls(self) -> str:
        cls = self.cls_or_none()
        assert cls is not None

        return cls

    def cls_or_none(self) -> str | None:
        classes = self.tag.get('class')
        if classes is None:
            return None

        assert isinstance(classes, List) and len(classes) == 1
        return classes[0]

    def xpath(self) -> str:
        tag = self.tag
        paths: List[str] = []
        while tag.name != '[document]':
            n_prev = 0
            for sibling in tag.previous_siblings:
                n_prev += isinstance(sibling, Tag) and sibling.name == tag.name

            n_next = 0
            for sibling in tag.next_siblings:
                n_next += isinstance(sibling, Tag) and sibling.name == tag.name

            if (n_prev + n_next) == 0:
                paths.append(tag.name)
            else:
                paths.append(f'{tag.name}[{n_prev + 1}]')

            assert tag.parent is not None
            tag = tag.parent

        xpath = '/'.join(reversed(paths))
        return f'/{xpath}'

    def children(self) -> List[Element]:
        children: List[Element] = []
        for element in self.tag.children:
            if isinstance(element, Tag):
                children.append(Element(element, self.parsed_html))

        return children

    def next_siblings(self) -> List[Element]:
        assert (parent := self.tag.parent) is not None

        next: List[Element] = []
        element = self.tag.nextSibling
        while element is not None:
            assert (e_parent := element.parent) is not None
            if e_parent != parent:
                break

            if isinstance(element, Tag):
                next.append(Element(element, self.parsed_html))

            element = element.nextSibling

        return next

    def find(self, name: str, classes: Set[str] = set(), recursive: bool = True) -> Element:
        tags = self.find_all(name, classes=classes, recursive=recursive)
        assert len(tags) == 1

        return tags[0]

    def find_all(self, name: str, classes: Set[str] = set(), recursive: bool = True) -> List[Element]:  # noqa: E501
        tags = self.tag.find_all(name, recursive=recursive)

        for i in reversed(range(len(tags))):
            tag = tags[i]
            delete = len(classes) != 0
            if 'class' in tag.attrs:
                icls_set = set(tag.attrs['class'])
                delete = not icls_set.issuperset(classes)

            if delete:
                del tags[i]

        elements: List[Element] = []
        for tag in tags:
            elements.append(Element(tag, self.parsed_html))

        return elements

    def __repr__(self) -> str:
        return repr(self.tag)

    @staticmethod
    def parse_html(html: str) -> Element:
        parsed_html = BeautifulSoup(html, features='html.parser')

        return Element(parsed_html, parsed_html)


class Selenium:

    DEFAULT_WAIT = 1

    def __init__(self) -> None:
        self.driver = webdriver.Firefox()

    def url(self) -> str:
        return self.driver.current_url  # type: ignore[no-any-return]

    def html(self) -> str:
        return self.driver.page_source  # type: ignore[no-any-return]

    def find(self, xpath: str) -> WebElement:
        elements = self.driver.find_elements(By.XPATH, xpath)
        assert len(elements) == 1

        return elements[0]

    def quit(self) -> None:
        self.driver.quit()

    def close_tab(self) -> None:
        self.driver.close()
        self.switch_to_active_tab()

    def switch_to_active_tab(self) -> None:
        handle = self.driver.window_handles[-1]
        self.driver.switch_to.window(handle)

    def get(self, url: str, wait_after_get: float = DEFAULT_WAIT) -> str:
        self.driver.get(url)
        self.wait(wait_after_get)

        html = self.html()
        return html

    def wait(self, seconds: float = DEFAULT_WAIT) -> None:
        time.sleep(seconds)
