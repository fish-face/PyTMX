import logging
import os
import six
import struct
import array
from itertools import chain, product, islice
from collections import defaultdict, OrderedDict
from xml.etree import ElementTree
from six.moves import zip, map
from .constants import *

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)
logger.setLevel(logging.INFO)

__all__ = ('TiledMap', 'Tileset', 'TileLayer', 'Object', 'ObjectGroup',
           'ImageLayer')


def decode_gid(raw_gid):
    # gids are encoded with extra information
    # as of 0.7.0 it determines if the tile should be flipped when rendered
    # as of 0.8.0 bit 30 determines if GID is rotated
    flags = 0
    if raw_gid & GID_TRANS_FLIPX == GID_TRANS_FLIPX: flags += TRANS_FLIPX
    if raw_gid & GID_TRANS_FLIPY == GID_TRANS_FLIPY: flags += TRANS_FLIPY
    if raw_gid & GID_TRANS_ROT == GID_TRANS_ROT: flags += TRANS_ROT
    gid = raw_gid & ~(GID_TRANS_FLIPX | GID_TRANS_FLIPY | GID_TRANS_ROT)
    return gid, flags


def handle_bool(text):
    """properly convert strings to a bool
    """
    try:
        return bool(int(text))
    except:
        pass
    try:
        text = str(text).lower()
        if text == "true":  return True
        if text == "yes":   return True
        if text == "false": return False
        if text == "no":    return False
    except:
        pass
    raise ValueError

# used to change the unicode string returned from xml to
# proper python variable types.
types = defaultdict(lambda: str)
types.update({
    "version": float,
    "orientation": str,
    "width": int,
    "height": int,
    "tilewidth": int,
    "tileheight": int,
    "firstgid": int,
    "source": str,
    "name": str,
    "spacing": int,
    "margin": int,
    "trans": str,
    "id": int,
    "opacity": float,
    "visible": handle_bool,
    "encoding": str,
    "compression": str,
    "gid": int,
    "type": str,
    "x": float,
    "y": float,
    "value": str,
    "rotation": float,
})


def parse_properties(node):
    """
    parse a node and return a dict that represents a tiled "property"

    the "properties" from tiled's tmx have an annoying quality that "name"
    and "value" is included. here we mangle it to get that junk out.
    """


class TiledElement(object):
    """Baseclass for pytmx types
    """

    def __init__(self):
        self.properties = dict()

    @classmethod
    def from_xml(cls, node):
        """Return a TileElement object from an ElementTree XML Node
        Note: this class must be handled by the subclass
        
        :param node: ElementTree.Node object
        rtype: TiledElement subclass
        """
        raise NotImplementedError

    @classmethod
    def from_string(cls, xml_string):
        """Return a TileElement object from a xml string

        :param xml_string: string containing xml data
        rtype: TiledElement instance
        """
        new = cls()
        node = ElementTree.fromstring(xml_string)
        new.from_xml(node)
        return new

    def find(self, *properties):
        """ Find all children with the given properties set.
        """
        r = set()
        for name in properties:
            for child in self.children:
                if name in child.properties:
                    r.add(child)
        return list(r)

    def match(self, **properties):
        """ Find all children with the given properties set to the given values.
        """
        r = set()
        for name in properties:
            for child in self.children:
                if name in child:
                    val = child[name]
                elif name in self.properties:
                    val = self.properties[name]
                else:
                    continue
                if properties[name] == val:
                    r.add(child)
        return list(r)

    def set_properties(self, node):
        """
        read the xml attributes and tiled properties from a xml node and fill
        in the values into the object's "properties" dictionary.
        """
        d = dict()
        for child in node.findall('properties'):
            for subnode in child.findall('property'):
                k = subnode.get('name')
                v = subnode.get('value')
                d[k] = types[str(k)](v)
        self.properties = d

    def __repr__(self):
        return '<{0}: "{1}">'.format(self.__class__.__name__, self.name)


class TiledMap(TiledElement):
    """Contains the layers, objects, and images from a Tiled TMX map
    """

    def __init__(self):
        TiledElement.__init__(self)
        self.layers = OrderedDict()  # all layers in drawing order
        self.tilesets = list()  # TiledTileset objects
        self.tile_properties = dict()  # tiles that have metadata

        # only used tiles are actually loaded, so there will be a difference
        # between the GIDs in the Tiled map data (tmx) and the data in this
        # object and the layers.  This dictionary keeps track of that.
        self.gidmap = defaultdict(list)
        self.imagemap = dict()  # mapping of gid and trans flags to real gids
        self.maxgid = 1

        # initialize the gid mapping
        self.imagemap[(0, 0)] = 0

        # will be filled in by a loader function
        self.images = list()

        # defaults from the tmx specification
        self.version = 0.0
        self.orientation = None
        self.width = 0  # width of map in tiles
        self.height = 0  # height of map in tiles
        self.tilewidth = 0  # width of a tile in pixels
        self.tileheight = 0  # height of a tile in pixels
        self.background_color = None

    def __repr__(self):
        return '<{0}: "{1}">'.format(self.__class__.__name__, self.filename)

    @property
    def children(self):
        return iter(self.layers.values())

    @classmethod
    def parse(cls, filename):
        return cls.from_xml(ElementTree.parse(filename).getroot())

    @classmethod
    def from_xml(cls, node):
        """Parse a map from ElementTree xml node

        :param node: ElementTree xml node
        """
        elem = cls()
        elem.set_properties(node)
        elem.background_color = node.get('backgroundcolor',
                                         elem.background_color)

        # ***        do not change this load order!      *** #
        # ***  gid mapping errors will occur if changed  *** #
        for subnode in node.findall('layer'):
            elem.add_layer(TileLayer.from_xml(subnode))

        for subnode in node.findall('imagelayer'):
            elem.add_layer(ImageLayer.from_xml(subnode))

        for subnode in node.findall('objectgroup'):
            elem.add_layer(ObjectGroup.from_xml(subnode))

        for subnode in node.findall('tileset'):
            elem.add_tileset(Tileset.from_xml(subnode))

        # "tile objects", objects with a GID, have need to have their
        # attributes set after the tileset is loaded,
        # so this step must be performed last
        for o in elem.objects:
            p = elem.get_tile_properties_by_gid(o.gid)
            if p:
                o.properties.update(p)

        return elem

    def get_tile_image(self, x, y, layer):
        """Return the tile image for this location

        :param x: x coordinate
        :param y: y coordinate
        :param layer: layer number
        :rtype: pygame surface if found, otherwise 0
        """
        try:
            assert (x >= 0 and y >= 0)
        except AssertionError:
            raise ValueError

        try:
            layer = self.layers[layer]
        except IndexError:
            raise ValueError

        assert (isinstance(layer, TileLayer))

        try:
            gid = layer.data[y][x]
        except (IndexError, ValueError):
            raise ValueError
        except TypeError:
            msg = "Tiles must be specified in integers."
            print(msg)
            raise TypeError

        else:
            return self.get_tile_image_by_gid(gid)

    def get_tile_image_by_gid(self, gid):
        """Return the tile image for this location

        :param gid: GID of image
        :rtype: pygame surface if found, otherwise ValueError
        """
        try:
            assert (int(gid) >= 0)
            return self.images[gid]
        except (TypeError):
            msg = "GIDs must be expressed as a number.  Got: {0}"
            print(msg.format(gid))
            raise TypeError
        except (AssertionError, IndexError):
            msg = "Coords: ({0},{1}) in layer {2} has invalid GID: {3}"
            print(msg.format(gid))
            raise ValueError

    def get_tile_properties(self, x, y, layer):
        """Return the tile image GID for this location

        :param x: x coordinate
        :param y: y coordinate
        :param layer: layer number
        :rtype: python dict if found, otherwise None
        """
        try:
            assert (x >= 0 and y >= 0 and layer >= 0)
        except AssertionError:
            raise ValueError

        try:
            gid = self.layers[int(layer)].data[int(y)][int(x)]
        except (IndexError, ValueError):
            msg = "Coords: ({0},{1}) in layer {2} is invalid."
            print(msg.format(x, y, layer))
            raise Exception

        else:
            try:
                return self.tile_properties[gid]
            except (IndexError, ValueError):
                msg = "Coords: ({0},{1}) in layer {2} has invalid GID: {3}"
                print(msg.format(x, y, layer, gid))
                raise Exception
            except KeyError:
                return None

    def get_tile_properties_by_gid(self, gid):
        """Get the tile properties of a tile GID

        :param gid: GID
        :rtype: python dict if found, otherwise None
        """
        try:
            return self.tile_properties[gid]
        except KeyError:
            return None

    def set_tile_properties(self, gid, properties):
        """Set the tile properties of a tile GID

        :param gid: GID
        :param properties: python dict of properties for GID
        """
        self.tile_properties[gid] = properties

    def add_layer(self, layer):
        """Add a layer (TileTileLayer, TiledImageLayer, or TiledObjectGroup)

        :param layer: TileTileLayer, TiledImageLayer, TiledObjectGroup object
        """
        assert (
            isinstance(layer,
                       (TileLayer, ImageLayer, ObjectGroup)))

        self.layers.append(layer)
        self.layernames[layer.name] = layer

    def add_tileset(self, tileset):
        """ Add a tileset to the map

        :param tileset: TiledTileset
        """
        assert (isinstance(tileset, Tileset))
        self.tilesets.append(tileset)

    def get_layer_by_name(self, name):
        """Return a layer by name

        :param name: Name of layer.  Case-sensitive.
        :rtype: Layer object if found, otherwise ValueError
        """
        try:
            return self.layernames[name]
        except KeyError:
            msg = 'Layer "{0}" not found.'
            print(msg.format(name))
            raise ValueError

    def get_object_by_name(self, name):
        """Find an object

        :param name: Name of object.  Case-sensitive.
        :rtype: Object if found, otherwise ValueError
        """
        for obj in self.objects:
            if obj.name == name:
                return obj
        raise ValueError

    @property
    def objectgroups(self):
        """Return iterator of all object groups

        :rtype: Iterator
        """
        return (layer for layer in self.layers
                if isinstance(layer, ObjectGroup))

    @property
    def objects(self):
        """Return iterator of all the objects associated with this map

        :rtype: Iterator
        """
        return chain(*self.objectgroups)

    def register_gid(self, tiled_gid, flags=0):
        """Used to manage the mapping of GIDs between the tmx and pytmx

        :param tiled_gid: GID that is found in TMX data
        rtype: GID that pytmx uses for the the GID passed
        """
        if tiled_gid:
            try:
                return self.imagemap[(tiled_gid, flags)][0]
            except KeyError:
                gid = self.maxgid
                self.maxgid += 1
                self.imagemap[(tiled_gid, flags)] = (gid, flags)
                self.gidmap[tiled_gid].append((gid, flags))
                return gid

        else:
            return 0

    def map_gid(self, tiled_gid):
        """Used to lookup a GID read from a TMX file's data

        :param tiled_gid: GID that is found in TMX data
        rtype: (GID, flags) that pytmx uses for the the GID passed
        """
        try:
            return self.gidmap[int(tiled_gid)]
        except KeyError:
            return None
        except TypeError:
            msg = "GIDs must be an integer"
            print(msg)
            raise TypeError


class Tileset(TiledElement):
    """ Represents a Tiled Tileset

    External tilesets are supported.  GID/ID's from Tiled are not guaranteed to
    be the same after loaded.
    """

    def __init__(self):
        TiledElement.__init__(self)
        self.firstgid = 0
        self.source = None
        self.name = None
        self.tilewidth = 0
        self.tileheight = 0
        self.spacing = 0
        self.margin = 0
        self.trans = None
        self.width = 0
        self.height = 0

    @classmethod
    def from_xml(cls, node):
        """Parse a Tileset from ElementTree xml node

        A bit of mangling is done here so that tilesets that have external
        TSX files appear the same as those that don't

        :param node: ElementTree xml node
        """
        elem = cls()

        # if true, then node references an external tileset
        source = node.get('source', None)
        if source:
            if source[-4:].lower() == ".tsx":

                # external tilesets don't save this, store it for later
                elem.firstgid = int(node.get('firstgid'))

                # we need to mangle the path - tiled stores relative paths
                dirname = os.path.dirname(elem.parent.filename)
                path = os.path.abspath(os.path.join(dirname, source))
                try:
                    node = ElementTree.parse(path).getroot()
                except IOError:
                    msg = "Cannot load external tileset: {0}"
                    print(msg.format(path))
                    raise Exception

            else:
                msg = "Found external tileset, but cannot handle type: {0}"
                print(msg.format(elem.source))
                raise Exception

        elem.set_properties(node)

        # since tile objects [probably] don't have a lot of metadata,
        # we store it separately in the parent (a TiledMap instance)
        for child in node.getiterator('tile'):
            real_gid = int(child.get("id"))
            p = parse_properties(child)
            p['width'] = elem.tilewidth
            p['height'] = elem.tileheight
            for gid, flags in elem.parent.map_gid(real_gid + elem.firstgid):
                elem.parent.set_tile_properties(gid, p)

        image_node = node.find('image')
        elem.source = image_node.get('source')
        elem.trans = image_node.get('trans', None)
        elem.width = int(image_node.get('width'))
        elem.height = int(image_node.get('height'))
        return elem


class TileLayer(TiledElement):
    """ Represents a TileLayer

    Iterate over the layer using the iterator protocol
    """

    def __init__(self):
        TiledElement.__init__(self)
        self.data = list()
        self.name = None
        self.opacity = 1.0
        self.visible = True
        self.height = 0
        self.width = 0

    def __iter__(self):
        return self.iter_tiles()

    def iter_tiles(self):
        for y, x in product(range(self.height), range(self.width)):
            yield x, y, self.data[y][x]

    @classmethod
    def from_xml(cls, node):
        """Parse a Tile Layer from ElementTree xml node

        :param node: ElementTree xml node
        """
        elem = cls()
        elem.set_properties(node)
        data = None
        next_gid = None
        data_node = node.find('data')

        encoding = data_node.get('encoding', None)
        if encoding == 'base64':
            from base64 import b64decode

            data = b64decode(data_node.text.strip())

        elif encoding == 'csv':
            next_gid = map(int, "".join(
                line.strip() for line in data_node.text.strip()
            ).split(","))

        elif encoding:
            msg = 'TMX encoding type: {0} is not supported.'
            print(msg.format(encoding))
            raise Exception

        compression = data_node.get('compression', None)
        if compression == 'gzip':
            import gzip

            with gzip.GzipFile(fileobj=six.BytesIO(data)) as fh:
                data = fh.read()

        elif compression == 'zlib':
            import zlib

            data = zlib.decompress(data)

        elif compression:
            msg = 'TMX compression type: {0} is not supported.'
            print(msg.format(compression))
            raise Exception

        # if data is None, then it was not decoded or decompressed, so
        # we assume here that it is going to be a bunch of tile elements
        # TODO: this will/should raise an exception if there are no tiles
        if encoding == next_gid is None:
            def get_children(parent):
                for child in parent.findall('tile'):
                    yield int(child.get('gid'))

            next_gid = get_children(data_node)

        elif data:
            if type(data) == bytes:
                fmt = struct.Struct('<L')
                iterator = (data[i:i + 4] for i in range(0, len(data), 4))
                next_gid = (fmt.unpack(i)[0] for i in iterator)
            else:
                print(type(data))
                raise Exception

        def init():
            return [0] * elem.width

        reg = elem.parent.register_gid

        # H (16-bit) may be a limitation for very detailed maps
        elem.data = tuple(array.array('H', init()) for i in range(elem.height))
        for (y, x) in product(range(elem.height), range(elem.width)):
            elem.data[y][x] = reg(*decode_gid(next(next_gid)))
        return elem


class Object(TiledElement):
    """ Represents a any Tiled Object

    Supported types: Box, Ellispe, Tile Object, Polyline, Polygon
    """

    def __init__(self):
        TiledElement.__init__(self)
        self.name = None
        self.type = None
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.rotation = 0
        self.gid = 0
        self.visible = 1

    @classmethod
    def from_xml(cls, node):
        """Parse an Object from ElementTree xml node

        :param node: ElementTree xml node
        """
        elem = cls()

        def read_points(text):
            """
            parse a text string of integer tuples and return [(x,...),...]
            """
            return tuple(tuple(map(int, i.split(','))) for i in text.split())

        elem.set_properties(node)

        # correctly handle "tile objects" (object with gid set)
        if elem.gid:
            elem.gid = elem.parent.register_gid(elem.gid)
            # tiled stores the origin of GID objects by the lower right corner
            # this is different for all other types, so i just adjust it here
            # so all types loaded with pytmx are uniform.
            # TODO: map the gid to the tileset to get the correct height
            elem.y -= elem.parent.tileheight

        points = None

        polygon = node.find('polygon')
        if polygon is not None:
            points = read_points(polygon.get('points'))
            elem.closed = True

        polyline = node.find('polyline')
        if polyline is not None:
            points = read_points(polyline.get('points'))
            elem.closed = False

        if points:
            x1 = x2 = y1 = y2 = 0
            for x, y in points:
                if x < x1: x1 = x
                if x > x2: x2 = x
                if y < y1: y1 = y
                if y > y2: y2 = y
            elem.width = abs(x1) + abs(x2)
            elem.height = abs(y1) + abs(y2)
            elem.points = tuple(
                [(i[0] + elem.x, i[1] + elem.y) for i in points])
        return elem


class ObjectGroup(TiledElement, list):
    """ Represents a Tiled ObjectGroup

    Supports any operation of a normal list.
    """

    def __init__(self):
        TiledElement.__init__(self)
        self.name = None
        self.color = None
        self.opacity = 1
        self.visible = 1

    @classmethod
    def from_xml(cls, node):
        """Parse an Object Group from ElementTree xml node

        :param node: ElementTree xml node
        """
        elem = cls()
        elem.set_properties(node)
        for child in node.findall('object'):
            o = Object(elem.parent, child)
            elem.append(o)
        return elem


class ImageLayer(TiledElement):
    """ Represents Tiled Image Layer

    The image associated with this layer will be loaded and assigned a GID.
    (pygame only)
    """

    def __init__(self):
        TiledElement.__init__(self)
        self.source = None
        self.trans = None
        self.name = None
        self.opacity = 1
        self.visible = 1

        # unify the structure of layers
        self.gid = 0

    @classmethod
    def from_xml(cls, node):
        """Parse an Image Layer from ElementTree xml node

        :param node: ElementTree xml node
        :rtype: TiledImageLayer instance
        """
        elem = cls()
        elem.set_properties(node)
        elem.name = node.get('name', None)
        elem.opacity = node.get('opacity', elem.opacity)
        elem.visible = node.get('visible', elem.visible)
        image_node = node.find('image')
        elem.source = image_node.get('source')
        elem.trans = image_node.get('trans', None)
        return elem
