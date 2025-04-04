Links, mentions, and rich text
Posts in Bluesky use rich text to handle links, mentions, and other kinds of decorated text.

A common way to handle rich text is through a markup language. For example, in HTML we might write:

Go to <a href="https://example.com">this site</a>

And in Markdown we would write:

Go to [this site](https://example.com)

Bluesky does not use a markup language (read here for more details). Instead, it uses a concept of rich text facets which point at locations in the text.

Rich text facets
Let's look at the string we want to decorate:

'Go to this site'

We can number the positions in the string as follows:

  'G  o     t  o     t  h  i  s     s  i  t  e'
// 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15

We want to turn characters 6 through 14 into a link. To do that, we assert a link with byteStart: 6 and byteEnd: 15 and a uri of https://example.com.

  'G  o     t  o     t  h  i  s     s  i  t  e'
// 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
//                   ^--------------------------^
//                  link to https://example.com

note
The range has an inclusive start and an exclusive end. That means the end number goes 1 past what you might expect.

Exclusive-end helps the math stay consistent. If you subtract the end from the start, you get the correct length of the target string. In this case, 15-6 = 9, which is the length of the "this site" string.

In a post, it looks like this:

{
  text: 'Go to this site',
  facets: [
    {
      index: {
        byteStart: 6,
        byteEnd: 15
      },
      features: [{
        $type: 'app.bsky.richtext.facet#link',
        uri: 'https://example.com'
      }]
    }
  ]
}

The facet's features establish what kind of decorations are being applied to the range. There are three supported feature types:

app.bsky.richtext.facet#link: A link to some resource. Has the uri attribute.
app.bsky.richtext.facet#mention: A mention of a user. Produces a notification for the mentioned user. Has the did attribute.
app.bsky.richtext.facet#tag: A hashtag. Has the tag attribute.
Facets can not overlap. It's recommended that renderers sort them by byteStart and discard any facets which overlap each other. The features attribute is an array to support multiple decorations on a given range.

Text encoding and indexing
Strings in the network are UTF-8 encoded. Facet ranges are indexed using byte offsets into the UTF-8 encoding.

warning
It's important to pay attention to this when working with facets. Incorrect indexing will produce bad data.

If you are using Typescript/Javascript, you cannot use .slice() or any of the native methods. It's suggested you use the official atproto API's RichText library

To understand this fully, let's look at some of the kinds of indexing that Unicode supports:

Code units. The "atom" of an encoding. In UTF-8, this is a byte. In UTF-16, this is two bytes. In UTF-32, this is four bytes.
Code points. The "atom" of a unicode string. This is the same across all encodings; that is, a code-point index in UTF-8 is the same as a code-point index in UTF-16 or UTF-32.
Graphemes. The visual "atom" of text -- what we think of as a "character". Graphemes are made of multiple code-points.
Bluesky uses UTF-8 code units to index facets. Put another way, it uses byte offsets into UTF-8 encoded strings. This means you must handle the string in UTF-8 to produce valid indexes.

Producing facets
Clients to Bluesky should produce facets using parsers. It's perfectly valid to use a syntax (including markdown or HTML) but that syntax should be stripped out of the text before publishing.

Here are two example parsers to help you understand this behavior, but do not use these. We recommend that you use one of the existing libraries in the ecosystem (TypeScript, Python, Dart, Go).


Python

import re
from typing import List, Dict

def parse_mentions(text: str) -> List[Dict]:
    spans = []
    # regex based on: https://atproto.com/specs/handle#handle-identifier-syntax
    mention_regex = rb"[$|\W](@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(mention_regex, text_bytes):
        spans.append({
            "start": m.start(1),
            "end": m.end(1),
            "handle": m.group(1)[1:].decode("UTF-8")
        })
    return spans

def parse_urls(text: str) -> List[Dict]:
    spans = []
    # partial/naive URL regex based on: https://stackoverflow.com/a/3809435
    # tweaked to disallow some training punctuation
    url_regex = rb"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(url_regex, text_bytes):
        spans.append({
            "start": m.start(1),
            "end": m.end(1),
            "url": m.group(1).decode("UTF-8"),
        })
    return spans
    
# Parse facets from text and resolve the handles to DIDs
def parse_facets(text: str) -> List[Dict]:
    facets = []
    for m in parse_mentions(text):
        resp = requests.get(
            "https://bsky.social/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": m["handle"]},
        )
        # If the handle can't be resolved, just skip it!
        # It will be rendered as text in the post instead of a link
        if resp.status_code == 400:
            continue
        did = resp.json()["did"]
        facets.append({
            "index": {
                "byteStart": m["start"],
                "byteEnd": m["end"],
            },
            "features": [{"$type": "app.bsky.richtext.facet#mention", "did": did}],
        })
    for u in parse_urls(text):
        facets.append({
            "index": {
                "byteStart": u["start"],
                "byteEnd": u["end"],
            },
            "features": [
                {
                    "$type": "app.bsky.richtext.facet#link",
                    # NOTE: URI ("I") not URL ("L")
                    "uri": u["url"],
                }
            ],
        })
    return facets