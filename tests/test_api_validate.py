# -*- coding: utf-8 -*-
import re
import unittest
from xml.etree.ElementTree import Element

import six

from streamlink.plugin.api.validate import (
    all, any, attr, endswith, filter, get, getattr, hasattr,
    length, map, optional, startswith, text, transform, union, union_get, url,
    validate, xml_element, xml_find, xml_findall, xml_findtext
)


class TestPluginAPIValidate(unittest.TestCase):
    def test_basic(self):
        assert validate(1, 1) == 1

        assert validate(int, 1) == 1

        assert validate(transform(int), "1") == 1

        assert validate(text, "abc") == "abc"
        assert validate(text, u"日本語") == u"日本語"
        assert validate(transform(text), 1) == "1"

        assert validate(list, ["a", 1]) == ["a", 1]
        assert validate(dict, {"a": 1}) == {"a": 1}

        assert validate(lambda n: 0 < n < 5, 3) == 3

    def test_all(self):
        assert validate(all(int, lambda n: 0 < n < 5), 3) == 3

        assert validate(all(transform(int), lambda n: 0 < n < 5), 3.33) == 3

    def test_any(self):
        assert validate(any(int, dict), 5) == 5
        assert validate(any(int, dict), {}) == {}

        assert validate(any(int), 4) == 4

    def test_union(self):
        assert validate(union((get("foo"), get("bar"))), {"foo": "alpha", "bar": "beta"}) == ("alpha", "beta")

    def test_union_get(self):
        assert validate(union_get("foo", "bar"), {"foo": "alpha", "bar": "beta"}) == ("alpha", "beta")
        assert validate(union_get("foo", "bar", seq=list), {"foo": "alpha", "bar": "beta"}) == ["alpha", "beta"]
        assert validate(union_get(("foo", "bar"), ("baz", "qux")),
                        {"foo": {"bar": "alpha"}, "baz": {"qux": "beta"}}) == ("alpha", "beta")

    def test_list(self):
        assert validate([1, 0], [1, 0, 1, 1]) == [1, 0, 1, 1]
        assert validate([1, 0], []) == []
        assert validate(all([0, 1], lambda l: len(l) > 2), [0, 1, 0]) == [0, 1, 0]

    def test_list_tuple_set_frozenset(self):
        assert validate([int], [1, 2])
        assert validate(set([int]), set([1, 2])) == set([1, 2])
        assert validate(tuple([int]), tuple([1, 2])) == tuple([1, 2])

    def test_dict(self):
        assert validate({"key": 5}, {"key": 5}) == {"key": 5}
        assert validate({"key": int}, {"key": 5}) == {"key": 5}
        assert validate({"n": int, "f": float}, {"n": 5, "f": 3.14}) == {"n": 5, "f": 3.14}

    def test_dict_keys(self):
        assert validate({text: int}, {"a": 1, "b": 2}) == {"a": 1, "b": 2}
        assert validate({transform(text): transform(int)}, {1: 3.14, 3.14: 1}) == {"1": 3, "3.14": 1}

    def test_nested_dict_keys(self):
        assert validate({text: {text: int}}, {"a": {"b": 1, "c": 2}}) == {"a": {"b": 1, "c": 2}}

    def test_dict_optional_keys(self):
        assert validate({"a": 1, optional("b"): 2}, {"a": 1}) == {"a": 1}
        assert validate({"a": 1, optional("b"): 2}, {"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_filter(self):
        assert validate(filter(lambda i: i > 5), [10, 5, 4, 6, 7]) == [10, 6, 7]

    def test_map(self):
        assert validate(map(lambda v: v[0]), [(1, 2), (3, 4)]) == [1, 3]

    def test_map_dict(self):
        assert validate(map(lambda k, v: (v, k)), {"foo": "bar"}) == {"bar": "foo"}

    def test_get(self):
        assert validate(get("key"), {"key": "value"}) == "value"
        assert validate(get("key"), re.match(r"(?P<key>.+)", "value")) == "value"
        assert validate(get("invalidkey"), {"key": "value"}) is None
        assert validate(get("invalidkey", "default"), {"key": "value"}) == "default"
        assert validate(get(3, "default"), [0, 1, 2]) == "default"

        if six.PY2:
            with six.assertRaisesRegex(self, ValueError, "'NoneType' object has no attribute '__getitem__'"):
                validate(get("key"), None)
        else:
            with six.assertRaisesRegex(self, ValueError, "'NoneType' object is not subscriptable"):
                validate(get("key"), None)

        data = {"one": {"two": {"three": "value1"}}, ("one", "two", "three"): "value2"}
        assert validate(get(("one", "two", "three")), data) == "value1", "Recursive lookup"
        assert validate(get(("one", "two", "three"), strict=True), data) == "value2", "Strict tuple-key lookup"
        assert validate(get(("one", "two", "invalidkey")), data) is None, "Default value is None"
        assert validate(get(("one", "two", "invalidkey"), "default"), data) == "default", "Custom default value"

        with six.assertRaisesRegex(
            self, ValueError, "Object \"{'two': {'three': 'value1'}}\" does not have item \"invalidkey\""
        ):
            validate(get(("one", "invalidkey", "three")), data)
        if six.PY2:
            with six.assertRaisesRegex(self, ValueError, "'NoneType' object has no attribute '__getitem__'"):
                validate(all(get("one"), get("invalidkey"), get("three")), data)
        else:
            with six.assertRaisesRegex(self, ValueError, "'NoneType' object is not subscriptable"):
                validate(all(get("one"), get("invalidkey"), get("three")), data)

    def test_get_re(self):
        m = re.match(r"(\d+)p", "720p")
        assert validate(get(1), m) == "720"

    def test_getattr(self):
        el = Element("foo")

        assert validate(getattr("tag"), el) == "foo"
        assert validate(getattr("invalid", "default"), el) == "default"

    def test_hasattr(self):
        el = Element("foo")

        assert validate(hasattr("tag"), el) == el

    def test_length(self):
        assert validate(length(1), [1, 2, 3]) == [1, 2, 3]

        def invalid_length():
            validate(length(2), [1])

        self.assertRaises(ValueError, invalid_length)

    def test_xml_element(self):
        el = Element("tag", attrib={"key": "value"})
        el.text = "test"

        assert validate(xml_element("tag"), el).tag == "tag"
        assert validate(xml_element(text="test"), el).text == "test"
        assert validate(xml_element(attrib={"key": text}), el).attrib == {"key": "value"}

    def test_xml_find(self):
        el = Element("parent")
        el.append(Element("foo"))
        el.append(Element("bar"))

        assert validate(xml_find("bar"), el).tag == "bar"

    def test_xml_findtext(self):
        el = Element("foo")
        el.text = "bar"

        assert validate(xml_findtext("."), el) == "bar"

    def test_xml_findall(self):
        el = Element("parent")
        children = [Element("child") for i in range(10)]
        for child in children:
            el.append(child)

        assert validate(xml_findall("child"), el) == children

    def test_attr(self):
        el = Element("foo")
        el.text = "bar"

        assert validate(attr({"text": text}), el).text == "bar"

    def test_url(self):
        url_ = "https://google.se/path"

        assert validate(url(), url_)
        assert validate(url(scheme="http"), url_)
        assert validate(url(path="/path"), url_)

    def test_startswith(self):
        assert validate(startswith("abc"), "abcedf")

    def test_endswith(self):
        assert validate(endswith(u"åäö"), u"xyzåäö")
