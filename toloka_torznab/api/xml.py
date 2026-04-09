"""Shared XML primitives and constants for the Torznab API."""

from fastapi.responses import Response
from lxml import etree

_TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
_CT_XML = "application/xml; charset=utf-8"
_CT_RSS = "application/rss+xml; charset=utf-8"
_CT_TORRENT = "application/x-bittorrent"
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 200
_CAT_TV = "5000"
_CAT_MOVIE = "2000"


def xml_response(root: etree._Element, content_type: str = _CT_XML) -> Response:
    body = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    return Response(content=body, media_type=content_type)


def error_xml(code: int, description: str) -> Response:
    root = etree.Element("error")
    root.set("code", str(code))
    root.set("description", description)
    return xml_response(root)


def torznab_attr(parent: etree._Element, name: str, value: str) -> None:
    el = etree.SubElement(parent, f"{{{_TORZNAB_NS}}}attr")
    el.set("name", name)
    el.set("value", value)
