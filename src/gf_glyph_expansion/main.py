from absl import app, flags
from collections import defaultdict
from dataclasses import dataclass
from fontTools import ttLib
import functools
import gflanguages
from gftools import fonts_public_pb2
from gftools.util import google_fonts
from pathlib import Path
import pickle
import re
from typing import Any, Dict, Set


FLAGS = flags.FLAGS


flags.DEFINE_string("gf_repo", str(Path.home() / "oss" / "fonts"), "The root of a clone of the Google Fonts repo (https://github.com/google/fonts)")
flags.DEFINE_string("cache_dir", "/tmp/gf_glyph_temp", "A place to cache outputs between runs")
flags.DEFINE_integer("max_missing", 1, "If a font has <= this many missing chars for a language it's an opportunity")
flags.DEFINE_string("family_filter", None, "Families whose name doesn't include this pattern are skipped")


@dataclass
class Family:
    name: str
    num_fonts: int
    num_axes: int
    exemplar_font_file: Path

    def cost_multiplier(self) -> float:
        if self.num_axes > 0:
            multiplier = 1 + 2 ** (self.num_axes - 1)
            if self.num_fonts > 1:
                multiplier *= 1.5
        else:
            multiplier = 0.9 + 0.1 * self.num_fonts

        return multiplier


def glyph_cost(num_glyphs: int) -> float:
    return 0.9 + 0.1 * num_glyphs


def disk_cache(fn) -> Any:
    def do_cache(*args, **kwargs):
        name = fn.__name__
        if args:
            name += "_" + "_".join(str(a).replace("/", "-") for a in args)
        if kwargs:
            raise ValueError("No kwargs yet")
        file = Path(cache_dir() / (name + ".pickle"))
        if not file.is_file():
            print("Generating", file)
            result = fn(*args, *kwargs)
            with open(file, "wb") as f:
                pickle.dump(result, f)
        else:
            #print("Reusing", file)
            with open(file, "rb") as f:
                result = pickle.load(f)
        return result
    return do_cache



@disk_cache
def load_language_base_sets() -> Dict[str, Set[chr]]:
    langs = gflanguages.LoadLanguages()
    return {
        lang: gflanguages.parse(data.exemplar_chars.base)
        for (lang, data) in gflanguages.LoadLanguages().items()
    }


@disk_cache
def load_families() -> Dict[str, Family]:
    result = {}
    for license in ("ofl", "ufl", "apache"):
        license_dir = Path(FLAGS.gf_repo) / license
        if not license_dir.is_dir():
            print(f"WARN: not a dir: {license_dir}")
            continue
        for metadata_file in license_dir.rglob("METADATA.pb"):
            try:
                metadata = google_fonts.ReadProto(fonts_public_pb2.FamilyProto(), metadata_file)
            except Exception as e:
                print("Unable to load", metadata_file, ":", e)
                continue
            exemplar_font_file = Path(f"{license}/{metadata_file.parent.name}/{google_fonts.GetExemplarFont(metadata).filename}")
            result[metadata.name] = Family(metadata.name, len(metadata.fonts), len(metadata.axes), exemplar_font_file)
    return result


@disk_cache
def chars_in_font(font_file: Path) -> Set[chr]:
    font_file = Path(FLAGS.gf_repo) / font_file
    print("Get chars in", font_file)
    font = ttLib.TTFont(font_file)
    # really we should union all unicode cmaps. baby steps
    return {chr(cp) for cp in font.getBestCmap().keys()}


@functools.cache
def cache_dir() -> Path:
    d = Path(FLAGS.cache_dir)
    if not d.is_dir():
        print(f"Creating --cache_dir {d}")
        d.mkdir(exist_ok=True, parents=True)
    return d


def _run(_) -> int:
    base_sets = load_language_base_sets()
    families = load_families()

    # (family, chars) => {langs}
    opportunities = defaultdict(set)

    if FLAGS.family_filter is None:
        filter_fn = lambda _: True
    else:
        filter_fn = lambda name: re.search(FLAGS.family_filter, name) is not None

    skipped = 0
    for (family_name, family) in families.items():
        if not filter_fn(family_name):
            skipped += 1
            continue

        font_chars = chars_in_font(family.exemplar_font_file)

        for (lang, lang_chars) in base_sets.items():
            missing_chars = tuple(sorted(lang_chars - font_chars))  # sets aren't hashable
            opportunity = 0 < len(missing_chars) <= FLAGS.max_missing
            if not opportunity:
                #print(family, lang, "is NOT an opportunity, missing", missing_chars)
                continue
            opportunities[(family_name, missing_chars)].add(lang)

    for (family, missing_chars) in sorted(opportunities.keys()):
        cost = glyph_cost(len(missing_chars)) * families[family].cost_multiplier()
        print(family, "needs", len(missing_chars), "to support", sorted(opportunities[(family, missing_chars)]), ":", "".join(sorted(missing_chars)), "cost", f"{cost:.1f}")
    print(len(opportunities), "to add <= ", FLAGS.max_missing, "and support at least one new language")
    print(skipped, "families skipped by --family_filter")

    return 0


def main(argv=None):
    # We don't seem to be __main__ when run as cli tool installed by setuptools
    app.run(_run, argv=argv)


if __name__ == "__main__":
    main()
