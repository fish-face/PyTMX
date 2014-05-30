"""
Map loader for TMX Files
bitcraft (leif dot theden at gmail.com)
v3.17 - for python 3.3

If you have any problems or suggestions, please contact me via email.
Tested with Tiled 0.8.1 for Mac.

released under the LGPL v3

===============================================================================

New in 3.18:
    pygame: removed option for force a colorkey for a tileset
    pygame: pixelalpha is now enabled by default
     pytmx: Maps can now be loaded from pytmx.TiledMap.fromstring(xml_string)
     pytmx: pygame is no longer a required dependency (to be tested!)
      core: Sphinx documentation created

New in 3.17:
    loader: removed legacy load_tmx function: just call TiledMap() instead
    loader: added test to correct tilesheets that include non-tile graphics
     pytmx: polygon objects now return absolute coordinates in points
     pytmx: tiled properties are now available through dictionary "properties"
      core: tested with the mana world maps...it works!
      demo: simplified the demo/test for easier readability
      test: maps now render and are scaled inside the window to show entire map


New in 3.16:
    ***    jumped to version 3.x to reflect new python 3.3 compatibility    ***

       all: python 3 support
      pep8: changed method/function names to lowercase with underscore spacing
      pep8: modified various style infractions
      core: simplified file structure
      core: added __all__ to some modules for less clutter
      demo: added ability to resize preview window
      test: mouse clicks now advance the test
      test: added ability to resize preview window
      test: tile objects are drawn (previously supported, but not shown in test)
     utils: renamed buildDistributionRects to build_rects
     pytmx: bumped up gid limit from 255 to 65535 (16-bit)
     pytmx: removed get_objects(), replaces with objects property
     pytmx: removed get_draw_order(), replaced with visible_layers property
    loader: added ImageLayer support
    loader: minor documentation fixes
    loader: small optimizations
    loader: possible [ultra minor] optimization: using iterator on etree to load

New in .15:
    loader: new getTileLayerByName(name) method
    loader: python 2.6 support
    loader: fixed issue where objects with tile gid did not load properties
    loader: polygon and polyline objects
    loader: new lookup methods use iterators
    loader: loading function moved into classes
    loader: data/images can be reloaded on the fly
    loader: uses etree for faster xml parsing

New in .14:
    loader: Fixed gid lookup for "buildDistributionRects"
    loader: Added useful output to a few classes "__repr__"
    loader: Fixed a gid mapping issue that broke rotated tiles
    pygame: fixed colorkey handling
    pygame: correctly handles margins and spacing between tiles in tilesets
    pygame: b/c of changes, now correctly renders tiled's example maps
    added scrolling demo

New in .13:
    loader: Renamed "get_tile_image" to "getTileImage"
    loader: Removed duplicates returned from getTilePropertiesByLayer
    loader: Modified confusing messages for GID errors
    loader: Fixed bug where transformed tile properties are not available
    loader: No longer loads metadata for tiles that are not used
    loader: Reduced tile cache to 256 unique tiles
    loader: Removed 'visible' from list of reserved words
    loader: Added 'buildDistributionRects' and maputils module
    loader: Added some misc. functions for retrieving properties
    pygame: Smarter tile management made tile loading cache useless; removed it
    pygame: pygame.RLEACCEL flag added when appropriate

New in .12:
    loader: Fixed bug where tile properties could contain reserved words
    loader: Reduced size of image index by only allocating space for used tiles

New in .11:
    loader: Added support for tileset properties
    loader: Now checks for property names that are reserved for internal use
    loader: Added support for rotated tiles
    pygame: Only the tiles that are used in the map will be loaded into memory
    pygame: Added support for rotated tiles
    pygame: Added option to force a bitsize (depth) for surfaces
    pygame: Added option to convert alpha transparency to colorkey transparency
    pygame: Tilesets no longer load with per-pixel alphas by default
    pygame: Colorkey transparency should be correctly handled now


Includes a scrolling/zooming renderer.  They are for demonstration purposes,
and may not be suitable for all projects.  Use at your own risk.

===============================================================================

Installation:

    python setup.py install


Basic usage sample:

    >>> from pytmx import pygame_loader
    >>> tmxdata = pygame_loader.load_pygame("map.tmx")
    >>> tmxdata = pygame_loader.load_pygame("map.tmx", pixelalpha=False)


When you want to draw tiles, you simply call "getTileImage":

    >>> image = tmxdata.get_tile_image(x, y, layer)
    >>> screen.blit(image, position)

Maps, tilesets, layers, objectgroups, and objects all have a simple way to
access metadata that was set inside tiled: they are stored in an attribute
dictionary called "properties":

    >>> layer = tmxdata.layers["Background"]

    >>> print layer.tilewidth
    32
    >>> print layer.weather
    'sunny'

Tiles properties are the exception here*, and must be accessed through
"getTileProperties".  The data is a regular Python dictionary:

    >>> tile = tmxdata.get_tile_properties(x, y, layer)
    >>> tile["name"]
    'CobbleStone'

* this is compromise in the API delivers great memory saving

================================================================================
IMPORTANT FOR PYGAME USERS!!
The loader will correctly convert() or convert_alpha() each tile image, so you
shouldn't attempt to circumvent the loading mechanisms.  If you are experiencing
performance issues, you can pass "pixelalpha=False" while loading.

ALSO FOR PYGAME USERS:  Load your map after initializing your display.
================================================================================


***   Please see the TiledMap class for more api information.   ***
"""
from .pytmx import *

__version__ = (3, 18, 5)
__author__ = 'bitcraft'
__author_email__ = 'leif.theden@gmail.com'
__description__ = 'Map loader for TMX Files - Python 2 and 3'