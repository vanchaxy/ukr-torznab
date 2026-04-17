"""Shared XML primitives and constants for the Torznab API."""

from fastapi.responses import Response
from lxml import etree

_TORZNAB_NS = "http://torznab.com/schemas/2015/feed"


def xml_response(root: etree._Element, media_type="application/xml; charset=utf-8") -> Response:
    body = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    return Response(content=body, media_type=media_type)


def error_xml(code: int, description: str) -> Response:
    root = etree.Element("error")
    root.set("code", str(code))
    root.set("description", description)
    return xml_response(root)


def torznab_attr(parent: etree._Element, name: str, value: str) -> None:
    el = etree.SubElement(parent, f"{{{_TORZNAB_NS}}}attr")
    el.set("name", name)
    el.set("value", value)
