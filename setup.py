import setuptools

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

with open("VERSION", encoding="utf-8") as fh:
    version = fh.read().strip()

setuptools.setup(
    name="toppingmaker",
    version=version,
    author="Dave Signer",
    author_email="david@opengis.ch",
    description="Package to create parameterized QGIS projects and dump it into a YAML structure.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/opengisch/toppingmaker",
    classifiers=[
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    packages=setuptools.find_packages(exclude=["tests"]),
)
