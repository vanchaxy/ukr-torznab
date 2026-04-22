from fastapi.responses import Response
from lxml import etree

from ukr_torznab.api.xml import xml_response

DEFAULT_LIMIT = 100
MAX_LIMIT = 100
CAT_TV = "5000"
CAT_MOVIE = "2000"


def caps_response(title: str) -> Response:
    caps = etree.Element("caps")

    server = etree.SubElement(caps, "server")
    server.set("title", title)

    limits = etree.SubElement(caps, "limits")
    limits.set("max", str(MAX_LIMIT))
    limits.set("default", str(DEFAULT_LIMIT))

    searching = etree.SubElement(caps, "searching")
    for tag, params in (
        ("search", "q,cat,imdbid,tmdbid"),
        ("tv-search", "q,cat,tvdbid,imdbid,season,ep"),
        ("movie-search", "q,cat,imdbid,tmdbid"),
    ):
        el = etree.SubElement(searching, tag)
        el.set("available", "yes")
        el.set("supportedParams", params)
    for tag in ("audio-search", "book-search"):
        el = etree.SubElement(searching, tag)
        el.set("available", "no")

    categories = etree.SubElement(caps, "categories")
    for cat_id, cat_name in ((CAT_TV, "TV"), (CAT_MOVIE, "Movies")):
        el = etree.SubElement(categories, "category")
        el.set("id", cat_id)
        el.set("name", cat_name)

    return xml_response(caps)
