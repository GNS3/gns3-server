Symbols
*******

This directory contains symbols that you can use in GNS3.

Rules
=====

* All symbols must be a SVG file
* A file named symbol.txt should exist and contains the symbol licence
* Try to keep the file size small
* The recommended maximum width and height is 70px, please see how to resize a SVG below


Resize a SVG
============

It is possible to resize a SVG file using a software like Inkscape or any
other editor that works for SVG images.

Alternatively, you could use ImageMagick (with rsvg support) on Mac OS and Linux

Example to install ImageMagick on Mac using Homebrew:

```
brew install imagemagick --with-librsvg
```

Example to install ImageMagick on Debian or Ubuntu:

```
sudo apt-get install imagemagick
```

Example to resize to a width and height of 70px:

```
convert -background none symbols/firefox.svg -resize x70 firefox.svg
```
