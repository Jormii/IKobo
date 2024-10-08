from __future__ import annotations
import time
from typing import Dict, List, Set

from bs4 import BeautifulSoup, PageElement, Tag
from selenium import webdriver  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.remote.webelement import WebElement  # type: ignore


class Element:

    class FindIdCacheKey:

        def __init__(self, name: str, id: str) -> None:
            self.name = name
            self.id = id

        def __hash__(self) -> int:
            return hash((self.name, self.id))

        def __eq__(self, __value: object) -> bool:
            assert isinstance(__value, Element.FindIdCacheKey)
            return hash(self) == hash(__value)

    def __init__(self, tag: Tag, parsed_html: BeautifulSoup) -> None:
        self.tag = tag
        self.parsed_html = parsed_html

        self.name = self.tag.name
        self.text = self.tag.text.strip()

        self.find_id_cache: Dict[Element.FindIdCacheKey, List[Element]] = {}

    def cls(self) -> str:
        return self.get_attr('class')

    def cls_or_none(self) -> str | None:
        return self.get_attr_or_none('class')

    def get_attr(self, key: str) -> str:
        attribute = self.get_attr_or_none(key)
        assert attribute is not None

        return attribute

    def get_attr_or_none(self, key: str) -> str | None:
        attributes = self.tag.get(key)
        if attributes is None:
            return None

        if isinstance(attributes, str):
            attribute = attributes
        else:
            assert len(attributes) == 1
            attribute = attributes[0]

        return attribute

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

    def parent(self) -> Element:
        tag = self.tag.parent
        assert tag is not None

        return Element(tag, self.parsed_html)

    def children(self) -> List[Element]:
        children: List[Element] = []
        for element in self.tag.children:
            if isinstance(element, Tag):
                children.append(Element(element, self.parsed_html))

        return children

    def prev_siblings(self, add_self: bool = False) -> List[Element]:
        siblings = self._siblings(previous_or_next=True, add_self=add_self)
        return siblings

    def next_siblings(self, add_self: bool = False) -> List[Element]:
        siblings = self._siblings(previous_or_next=False, add_self=add_self)
        return siblings

    def _siblings(self, previous_or_next: bool, add_self: bool = False) -> List[Element]:

        def _next(_tag: PageElement) -> PageElement | None:
            if previous_or_next:
                return _tag.previousSibling
            else:
                return _tag.nextSibling

        assert (parent := self.tag.parent) is not None

        siblings: List[Element] = []
        if add_self:
            siblings.append(self)

        element = _next(self.tag)
        while element is not None:
            assert (e_parent := element.parent) is not None
            if e_parent != parent:
                break

            if isinstance(element, Tag):
                siblings.append(Element(element, self.parsed_html))

            element = _next(element)

        return siblings
        pass

    def find(self, name: str, classes: Set[str] = set(), recursive: bool = True) -> Element:
        elements = self.find_all(name, classes=classes, recursive=recursive)
        assert len(elements) == 1

        return elements[0]

    def find_or_none(self, name: str, classes: Set[str] = set(), recursive: bool = True) -> Element | None:
        elements = self.find_all(name, classes=classes, recursive=recursive)
        assert len(elements) <= 1

        if len(elements) == 0:
            return None
        else:
            return elements[0]

    def find_all(self, name: str, classes: Set[str] = set(), recursive: bool = True) -> List[Element]:
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

    def find_with_id(self, name: str, id: str) -> Element:
        elements = self.find_all_with_id(name, id)
        assert len(elements) == 1

        return elements[0]

    def find_with_id_or_none(self, name: str, id: str) -> Element | None:
        elements = self.find_all_with_id(name, id)
        assert len(elements) <= 1

        if len(elements) == 0:
            return None
        else:
            return elements[0]

    def find_all_with_id(self, name: str, id: str) -> List[Element]:
        cache_key = Element.FindIdCacheKey(name, id)
        if cache_key in self.find_id_cache:
            elements = self.find_id_cache[cache_key]
        else:
            tags = self.tag.find_all(name, {'id': id})
            elements = [Element(tag, self.parsed_html) for tag in tags]

            self.find_id_cache[cache_key] = elements

        return elements

    def __hash__(self) -> int:
        return hash(self.tag)

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, Element):
            return False

        return self.tag == __value.tag

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
