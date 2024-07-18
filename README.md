# gf_glyph_expansion
Exploratory hackery in search of opportunities to add glyphs to Google Fonts to expand their language coverage

## Derived from Simon's search for ẞ

```python
# Run at root of google/fonts checkout
import glob
from fontTools.ttLib import TTFont
from gflanguages import LoadLanguages, parse
from gftools import fonts_public_pb2
from gftools.util import google_fonts as fonts
import os

langs = LoadLanguages()

# All the German base exemplars without the capital eszett
cps = parse(langs["de_Latn"].exemplar_chars.base)
cps -= set("ẞ")
counter = 0

for mdfile in glob.glob("ofl/*/METADATA.pb"):
    # Find an exemplar font for this family
    try:
        family_metadata = fonts.ReadProto(fonts_public_pb2.FamilyProto(), mdfile)
        exemplar_font_fp = os.path.join(
            os.path.dirname(mdfile), fonts.GetExemplarFont(family_metadata).filename
        )
        exemplar_font = TTFont(exemplar_font_fp)
    except Exception as e:
        continue
    # All encoded codepoints in the font
    exemplar_cps = set(chr(x) for x in exemplar_font.getBestCmap().keys())
    # Does this font have all the german bases, but does not have capital eszett?
    if exemplar_cps.issuperset(cps) and "ẞ" not in exemplar_cps:
        counter += 1

print(counter)
```