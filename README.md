# gf_glyph_expansion
Exploratory hackery in search of opportunities to add glyphs to Google Fonts to expand their language coverage

## Valuing an extension

To assess ROI we need to value both cost and benefit. Both are done in magical ROI units.

### Value

Details TBD. Combination of:

* Popularity
* Ease of update
* Other value signals
   * For example, we might boost known growth areas

### Cost

Based on discussion with @davelab6, assume that:

* Getting setup to modify a font at all is expensive
   * Glyph 1 costs 1 unit
   * Glyph 2..n cost 0.1 units each
   * 1 glyph for 1 unit, 11 glyphs for 2 units, etc
* Modifying multiple static fonts or a variable font costs more than a single static font
   * For a static family, multiply cost by 0.9 + 0.1 * number of fonts
      * x 1.0 for a single static font, x 1.8 for a family with 9 static weights, etc
   * For a variable family, multiply cost by 1 + 2^(num_axes - 1)
      * If there are multiple fonts (e.g. Regular/Italic) multiply by 1.5
      * x 2.0 for weight variable, x 3.0 for weight+width variable, x 17.0 for Recursive with 5 axes
      * This makes adding glyphs to Flex fonts *very* expensive ... which is perhaps accurate?

## Usage

```python
# in a venv
$ pip install -e .
$ gf_glyph_expansion
9295 to add <=  1 and support at least one new language
$ gf_glyph_expansion --max_missing 10
319388 to add <=  10 and support at least one new language
$ gf_glyph_expansion --max_missing 10 --family_filter "^Roboto$"
180 to add <=  10 and support at least one new language
```

Note that every (family, chars) pair is counted as one so the number of results for one family can be > 1.

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