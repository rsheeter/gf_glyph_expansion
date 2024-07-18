# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import setup, find_packages


setup_args = dict(
    name="gf_glyph_expansion",
    use_scm_version={"write_to": "src/gf_glyph_expansion/_version.py"},
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "gf_glyph_expansion=gf_glyph_expansion.main:main",
        ],
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "absl-py>=2",
        "fontTools>=4",
        "gflanguages>=0.6",
        "gftools>=0.9",  # this is insanely heavy, depends on all the things. Ideally remove.
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-clarity",
            "black",
        ],
    },
    python_requires=">=3.8",
    # metadata to display on PyPI
    author="Rod S",
    author_email="rsheeter@google.com",
    description=(
        "Exploratory utility to see where glyph expansion might make sense",
    ),
)


if __name__ == "__main__":
    setup(**setup_args)