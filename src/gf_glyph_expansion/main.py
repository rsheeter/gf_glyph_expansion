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
import requests
from typing import Any, Dict, Set
from typing_extensions import Self


FLAGS = flags.FLAGS


flags.DEFINE_string(
    "gf_repo",
    str(Path.home() / "oss" / "fonts"),
    "The root of a clone of the Google Fonts repo (https://github.com/google/fonts)",
)
flags.DEFINE_string(
    "cache_dir", "/tmp/gf_glyph_temp", "A place to cache outputs between runs"
)
flags.DEFINE_integer(
    "max_missing",
    1,
    "If a font has <= this many missing chars for a language it's an opportunity",
)
flags.DEFINE_string(
    "family_filter",
    None,
    "Families whose name doesn't include this pattern are skipped",
)
flags.DEFINE_bool(
    "debug",
    False,
    "Whether to print additional result info",
)


@dataclass
class Language:
    lang: str
    population: int
    required_chars: Set[chr]

    def value_multiplier(self) -> float:
        if self.population >= 10**9:
            return 10
        elif self.population >= 10**8:
            return 5
        elif self.population >= 10**7:
            return 1.5
        elif self.population >= 10**6:
            return 1.1
        elif self.population >= 10**5:
            return 1.01
        else:
            return 0.5


@dataclass
class Family:
    name: str
    num_fonts: int
    num_axes: int
    supported: Set[chr]

    def cost_multiplier(self) -> float:
        if self.num_axes > 0:
            multiplier = 1 + 2 ** (self.num_axes - 1)
            if self.num_fonts > 1:
                multiplier *= 1.5
        else:
            multiplier = 0.9 + 0.1 * self.num_fonts

        return multiplier


@dataclass
class FamilyStats:
    name: str
    popularity: int  # fully ordered starting at 0 for highest popularity

    def base_value(self) -> float:
        if self.popularity > 10:
            return 50
        elif self.popularity > 50:
            return 25
        elif self.popularity > 150:
            return 10
        elif self.popularity > 500:
            return 5
        else:
            return 1

    def default(name: str) -> Self:
        return FamilyStats(name, 9999)


@dataclass
class Opportunity:
    name: str  # the name of the family
    chars: Set[chr]
    langs: Set[str]
    value: float
    cost: float


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
            # print("Reusing", file)
            with open(file, "rb") as f:
                result = pickle.load(f)
        return result

    return do_cache


@disk_cache
def load_languages() -> Dict[str, Language]:
    langs = gflanguages.LoadLanguages()
    return {
        lang: Language(
            lang, data.population, gflanguages.parse(data.exemplar_chars.base)
        )
        for (lang, data) in gflanguages.LoadLanguages().items()
    }


@disk_cache
def load_family_stats() -> Dict[str, Family]:
    response = requests.get("https://fonts.google.com/metadata/fonts")
    response.raise_for_status()
    response = response.json()
    families = sorted(response["familyMetadataList"], key=lambda f: f["popularity"])
    return {
        family["family"]: FamilyStats(family["family"], i)
        for (i, family) in enumerate(families)
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
                metadata = google_fonts.ReadProto(
                    fonts_public_pb2.FamilyProto(), metadata_file
                )
            except Exception as e:
                print("Unable to load", metadata_file, ":", e)
                continue
            exemplar_font_file = Path(
                f"{license}/{metadata_file.parent.name}/{google_fonts.GetExemplarFont(metadata).filename}"
            )
            supported = chars_in_font(exemplar_font_file)
            result[metadata.name] = Family(
                metadata.name, len(metadata.fonts), len(metadata.axes), supported
            )
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
    languages = load_languages()
    families = load_families()
    stats = load_family_stats()

    # fill in any missing stats, such as for non-prod families, with default
    for family in families.keys():
        if family not in stats:
            stats[family] = FamilyStats.default(family)

    # (family, chars) => {langs}
    raw_opportunities = defaultdict(set)

    if FLAGS.family_filter is None:
        filter_fn = lambda _: True
    else:
        filter_fn = lambda name: re.search(FLAGS.family_filter, name) is not None

    skipped = 0
    for family_name, family in families.items():
        if not filter_fn(family_name):
            skipped += 1
            continue

        for language in languages.values():
            missing_chars = tuple(
                sorted(language.required_chars - family.supported)
            )  # sets aren't hashable
            opportunity = 0 < len(missing_chars) <= FLAGS.max_missing
            if not opportunity:
                # print(family, lang, "is NOT an opportunity, missing", missing_chars)
                continue
            raw_opportunities[(family_name, missing_chars)].add(language.lang)

    opportunities = []
    for (family, missing_chars), langs in raw_opportunities.items():
        value = stats[family].base_value()
        for lang in langs:
            value *= languages[lang].value_multiplier()
        cost = glyph_cost(len(missing_chars)) * families[family].cost_multiplier()
        opportunities.append(Opportunity(family, missing_chars, langs, value, cost))

    # Sort by= value/cost, popularity
    opportunities.sort(key=lambda o: (o.value / o.cost, stats[o.name].popularity))

    for opportunity in opportunities:
        additional = ""
        if FLAGS.debug:
            pop = ",".join(
                f"{languages[lang].population} (x{languages[lang].value_multiplier():.2f})"
                for lang in opportunity.langs
            )
            additional = (
                f"value {opportunity.value:.1f} cost {opportunity.cost:.1f} pop {pop}"
            )

        print(
            "value/cost",
            f"{opportunity.value / opportunity.cost:.1f}",
            opportunity.name,
            "needs",
            len(opportunity.chars),
            "to support",
            sorted(opportunity.langs),
            ":",
            "".join(sorted(opportunity.chars)),
            additional,
        )
    print(
        len(opportunities),
        "to add <= ",
        FLAGS.max_missing,
        "and support at least one new language",
    )

    if skipped > 0:
        print(skipped, "families skipped by --family_filter")

    return 0


def main(argv=None):
    # We don't seem to be __main__ when run as cli tool installed by setuptools
    app.run(_run, argv=argv)


if __name__ == "__main__":
    main()
