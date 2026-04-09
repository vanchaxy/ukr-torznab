"""Torznab capabilities response."""

from fastapi.responses import Response
from lxml import etree

from .xml import _CAT_MOVIE, _CAT_TV, _DEFAULT_LIMIT, _MAX_LIMIT, xml_response


def caps_response() -> Response:
    caps = etree.Element("caps")

    server = etree.SubElement(caps, "server")
    server.set("title", "Toloka Torznab")

    limits = etree.SubElement(caps, "limits")
    limits.set("max", str(_MAX_LIMIT))
    limits.set("default", str(_DEFAULT_LIMIT))

    searching = etree.SubElement(caps, "searching")
    for tag, params in (
        ("search", "q,cat,imdbid"),
        ("tv-search", "q,cat,tvdbid,imdbid,season,ep"),
        ("movie-search", "q,cat,imdbid"),
    ):
        el = etree.SubElement(searching, tag)
        el.set("available", "yes")
        el.set("supportedParams", params)
    for tag in ("audio-search", "book-search"):
        el = etree.SubElement(searching, tag)
        el.set("available", "no")

    categories = etree.SubElement(caps, "categories")
    for cat_id, cat_name in ((_CAT_TV, "TV"), (_CAT_MOVIE, "Movies")):
        cat_el = etree.SubElement(categories, "category")
        cat_el.set("id", cat_id)
        cat_el.set("name", cat_name)

    return xml_response(caps)
