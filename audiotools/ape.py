# Audio Tools, a module and set of tools for manipulating audio data
# Copyright (C) 2007-2015  Brian Langenberger

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


import sys
from audiotools import (AudioFile, MetaData)


# takes a pair of integers (or None) for the current and total values
# returns a unicode string of their combined pair
# for example, __number_pair__(2,3) returns u"2/3"
# whereas      __number_pair__(4,0) returns u"4"
def __number_pair__(current, total):
    def empty(i):
        return i is None

    unslashed_format = u"{:d}"
    slashed_format = u"{:d}/{:d}"

    if empty(current) and empty(total):
        return unslashed_format.format(0)
    elif (not empty(current)) and empty(total):
        return unslashed_format.format(current)
    elif empty(current) and (not empty(total)):
        return slashed_format.format(0, total)
    else:
        # neither current or total are empty
        return slashed_format.format(current, total)


def limited_transfer_data(from_function, to_function, max_bytes):
    """transfers up to max_bytes from from_function to to_function
    or as many bytes as from_function generates as strings"""

    BUFFER_SIZE = 0x100000
    s = from_function(BUFFER_SIZE)
    while (len(s) > 0) and (max_bytes > 0):
        if len(s) > max_bytes:
            s = s[0:max_bytes]
        to_function(s)
        max_bytes -= len(s)
        s = from_function(BUFFER_SIZE)


class ApeTagItem(object):
    """a single item in the ApeTag, typically a unicode value"""

    FORMAT = "32u 1u 2u 29p"

    def __init__(self, item_type, read_only, key, data):
        """fields are as follows:

        item_type is 0 = UTF-8, 1 = binary, 2 = external, 3 = reserved
        read_only is 1 if the item is read only
        key is a bytes object of the item's key
        data is a bytes object of the data itself
        """

        self.type = item_type
        self.read_only = read_only

        assert(isinstance(key, bytes))
        self.key = key
        assert(isinstance(data, bytes))
        self.data = data

    def __eq__(self, item):
        for attr in ["type", "read_only", "key", "data"]:
            if ((not hasattr(item, attr)) or (getattr(self, attr) !=
                                              getattr(item, attr))):
                return False
        else:
            return True

    def total_size(self):
        """returns total size of item in bytes"""

        return 4 + 4 + len(self.key) + 1 + len(self.data)

    def copy(self):
        """returns a duplicate ApeTagItem"""

        return ApeTagItem(self.type,
                          self.read_only,
                          self.key,
                          self.data)

    def __repr__(self):
        return "ApeTagItem({!r},{!r},{!r},{!r})".format(self.type,
                                                        self.read_only,
                                                        self.key,
                                                        self.data)

    def raw_info_pair(self):
        """returns a human-readable key/value pair of item data"""

        if self.type == 0:    # text
            if self.read_only:
                return (self.key.decode('ascii'),
                        u"(read only) {}".format(self.data.decode('utf-8')))
            else:
                return (self.key.decode('ascii'), self.data.decode('utf-8'))
        elif self.type == 1:  # binary
            return (self.key.decode('ascii'),
                    u"(binary) {:d} bytes".format(len(self.data)))
        elif self.type == 2:  # external
            return (self.key.decode('ascii'),
                    u"(external) {:d} bytes".format(len(self.data)))
        else:                 # reserved
            return (self.key.decode('ascii'),
                    u"(reserved) {:d} bytes".format(len(self.data)))

    if sys.version_info[0] >= 3:
        def __str__(self):
            return self.__unicode__()
    else:
        def __str__(self):
            return self.data

    def __unicode__(self):
        return self.data.rstrip(b"\x00").decode('utf-8', 'replace')

    def number(self):
        """returns the track/album_number portion of a slashed number pair"""

        import re

        unicode_value = self.__unicode__()

        int_string = re.search(r'\d+', unicode_value)
        if int_string is None:
            return None

        int_value = int(int_string.group(0))
        if (int_value == 0) and (u"/" in unicode_value):
            total_value = re.search(r'\d+',
                                    unicode_value.split(u"/")[1])
            if total_value is not None:
                # don't return placeholder 0 value
                # when a _total value is present
                # but _number value is 0
                return None
            else:
                return int_value
        else:
            return int_value

    def total(self):
        """returns the track/album_total portion of a slashed number pair"""

        import re

        unicode_value = self.__unicode__()

        if u"/" not in unicode_value:
            return None

        int_string = re.search(r'\d+', unicode_value.split(u"/")[1])

        if int_string is not None:
            return int(int_string.group(0))
        else:
            return None

    @classmethod
    def parse(cls, reader):
        """returns an ApeTagItem parsed from the given BitstreamReader"""

        (item_value_length,
         read_only,
         encoding) = reader.parse(cls.FORMAT)

        key = []
        c = reader.read_bytes(1)
        while c != b"\x00":
            key.append(c)
            c = reader.read_bytes(1)

        value = reader.read_bytes(item_value_length)

        return cls(encoding, read_only, b"".join(key), value)

    def build(self, writer):
        """writes the ApeTagItem values to the given BitstreamWriter"""

        writer.build("{} {:d}b 8u {:d}b".format(self.FORMAT,
                                                len(self.key),
                                                len(self.data)),
                     (len(self.data),
                      self.read_only,
                      self.type,
                      self.key, 0, self.data))

    @classmethod
    def binary(cls, key, data):
        """returns an ApeTagItem of binary data

        key is an ASCII string, data is a binary string"""

        return cls(1, 0, key, data)

    @classmethod
    def external(cls, key, data):
        """returns an ApeTagItem of external data

        key is an ASCII string, data is a binary string"""

        return cls(2, 0, key, data)

    @classmethod
    def string(cls, key, data):
        """returns an ApeTagItem of text data

        key is a bytes object, data is a unicode string"""

        assert(isinstance(key, bytes))
        assert(isinstance(data,
                          str if (sys.version_info[0] >= 3) else unicode))

        return cls(0, 0, key, data.encode('utf-8', 'replace'))


class ApeTag(MetaData):
    """a complete APEv2 tag"""

    HEADER_FORMAT = "8b 32u 32u 32u 1u 2u 26p 1u 1u 1u 64p"

    ITEM = ApeTagItem

    ATTRIBUTE_MAP = {'track_name': b'Title',
                     'track_number': b'Track',
                     'track_total': b'Track',
                     'album_number': b'Media',
                     'album_total': b'Media',
                     'album_name': b'Album',
                     'artist_name': b'Artist',
                     'performer_name': b'Performer',
                     'composer_name': b'Composer',
                     'conductor_name': b'Conductor',
                     'ISRC': b'ISRC',
                     'catalog': b'Catalog',
                     'copyright': b'Copyright',
                     'publisher': b'Publisher',
                     'year': b'Year',
                     'date': b'Record Date',
                     'comment': b'Comment',
                     'compilation': b'Compilation'}

    INTEGER_ITEMS = (b'Track', b'Media')
    BOOLEAN_ITEMS = (b'Compilation',)

    def __init__(self, tags, contains_header=True, contains_footer=True):
        """constructs an ApeTag from a list of ApeTagItem objects"""

        for tag in tags:
            assert(isinstance(tag, ApeTagItem))
        MetaData.__setattr__(self, "tags", list(tags))
        MetaData.__setattr__(self, "contains_header", contains_header)
        MetaData.__setattr__(self, "contains_footer", contains_footer)

    def __repr__(self):
        return "ApeTag({!r},{!r},{!r})".format(self.tags,
                                               self.contains_header,
                                               self.contains_footer)

    def total_size(self):
        """returns the minimum size of the total ApeTag, in bytes"""

        size = 0
        if self.contains_header:
            size += 32
        for tag in self.tags:
            size += tag.total_size()
        if self.contains_footer:
            size += 32
        return size

    def __eq__(self, metadata):
        if isinstance(metadata, ApeTag):
            if set(self.keys()) != set(metadata.keys()):
                return False

            for tag in self.tags:
                try:
                    if tag.data != metadata[tag.key].data:
                        return False
                except KeyError:
                    return False
            else:
                return True
        elif isinstance(metadata, MetaData):
            return MetaData.__eq__(self, metadata)
        else:
            return False

    def keys(self):
        return [tag.key for tag in self.tags]

    def __contains__(self, key):
        for tag in self.tags:
            if tag.key == key:
                return True
        else:
            return False

    def __getitem__(self, key):
        assert(isinstance(key, bytes))

        for tag in self.tags:
            if tag.key == key:
                return tag
        else:
            raise KeyError(key)

    def get(self, key, default):
        assert(isinstance(key, bytes))

        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        assert(isinstance(key, bytes))

        for i in range(len(self.tags)):
            if self.tags[i].key == key:
                self.tags[i] = value
                return
        else:
            self.tags.append(value)

    def index(self, key):
        assert(isinstance(key, bytes))

        for (i, tag) in enumerate(self.tags):
            if tag.key == key:
                return i
        else:
            raise ValueError(key)

    def __delitem__(self, key):
        assert(isinstance(key, bytes))

        new_tags = [tag for tag in self.tags if tag.key != key]
        if len(new_tags) < len(self.tags):
            self.tags = new_tags
        else:
            raise KeyError(key)

    def __getattr__(self, attr):
        if attr in self.ATTRIBUTE_MAP:
            try:
                if attr in {'track_number', 'album_number'}:
                    return self[self.ATTRIBUTE_MAP[attr]].number()
                elif attr in {'track_total', 'album_total'}:
                    return self[self.ATTRIBUTE_MAP[attr]].total()
                elif attr == 'compilation':
                    return self[self.ATTRIBUTE_MAP[attr]].__unicode__() == u"1"
                else:
                    return self[self.ATTRIBUTE_MAP[attr]].__unicode__()
            except KeyError:
                return None
        elif attr in MetaData.FIELDS:
            return None
        else:
            return MetaData.__getattribute__(self, attr)

    # if an attribute is updated (e.g. self.track_name)
    # make sure to update the corresponding dict pair
    def __setattr__(self, attr, value):
        def swap_number(unicode_value, new_number):
            import re

            return re.sub(r'\d+', u"{:d}".format(new_number), unicode_value, 1)

        def swap_slashed_number(unicode_value, new_number):
            if u"/" in unicode_value:
                (first, second) = unicode_value.split(u"/", 1)
                return u"/".join([first, swap_number(second, new_number)])
            else:
                return u"/".join([unicode_value, u"{:d}".format(new_number)])

        if attr in self.ATTRIBUTE_MAP:
            key = self.ATTRIBUTE_MAP[attr]
            if value is not None:
                if attr in {'track_number', 'album_number'}:
                    try:
                        current_value = self[key].__unicode__()
                        self[key] = self.ITEM.string(
                            key, swap_number(current_value, value))
                    except KeyError:
                        self[key] = self.ITEM.string(
                            key, __number_pair__(value, None))
                elif attr in {'track_total', 'album_total'}:
                    try:
                        current_value = self[key].__unicode__()
                        self[key] = self.ITEM.string(
                            key, swap_slashed_number(current_value, value))
                    except KeyError:
                        self[key] = self.ITEM.string(
                            key, __number_pair__(None, value))
                elif attr == 'compilation':
                    self[key] = self.ITEM.string(
                        key, u"{:d}".format(1 if value else 0))
                else:
                    self[key] = self.ITEM.string(key, value)
            else:
                delattr(self, attr)
        else:
            MetaData.__setattr__(self, attr, value)

    def __delattr__(self, attr):
        import re

        def zero_number(unicode_value):
            return re.sub(r'\d+', u"0", unicode_value, 1)

        if attr in self.ATTRIBUTE_MAP:
            key = self.ATTRIBUTE_MAP[attr]

            if attr in {'track_number', 'album_number'}:
                try:
                    tag = self[key]
                    if tag.total() is None:
                        # if no slashed _total field, delete entire tag
                        del(self[key])
                    else:
                        # otherwise replace initial portion with 0
                        self[key] = self.ITEM.string(
                            key, zero_number(tag.__unicode__()))
                except KeyError:
                    # no tag to delete
                    pass
            elif attr in {'track_total', 'album_total'}:
                try:
                    tag = self[key]
                    if tag.total() is not None:
                        if tag.number() is not None:
                            self[key] = self.ITEM.string(
                                key,
                                tag.__unicode__().split(u"/", 1)[0].rstrip())
                        else:
                            del(self[key])
                    else:
                        # no total portion, so nothing to do
                        pass
                except KeyError:
                    # no tag to delete portion of
                    pass
            else:
                try:
                    del(self[key])
                except KeyError:
                    pass
        elif attr in MetaData.FIELDS:
            pass
        else:
            MetaData.__delattr__(self, attr)

    @classmethod
    def converted(cls, metadata):
        """converts a MetaData object to an ApeTag object"""

        if metadata is None:
            return None
        elif isinstance(metadata, ApeTag):
            return ApeTag([tag.copy() for tag in metadata.tags],
                          contains_header=metadata.contains_header,
                          contains_footer=metadata.contains_footer)
        else:
            tags = cls([])

            for (field, value) in metadata.filled_fields():
                if field in cls.ATTRIBUTE_MAP.keys():
                    setattr(tags, field, value)

            for image in metadata.images():
                tags.add_image(image)

            return tags

    def raw_info(self):
        """returns the ApeTag as a human-readable unicode string"""

        from os import linesep
        from audiotools import output_table

        # align tag values on the "=" sign
        table = output_table()

        for tag in self.tags:
            row = table.row()
            (key, value) = tag.raw_info_pair()
            row.add_column(key, "right")
            row.add_column(u" = ")
            row.add_column(value)

        return (u"APEv2:" + linesep + linesep.join(table.format()))

    @classmethod
    def supports_images(cls):
        """returns True"""

        return True

    def __parse_image__(self, key, type):
        from audiotools import Image
        from io import BytesIO

        data = BytesIO(self[key].data)
        description = []
        c = data.read(1)
        while c != b'\x00':
            description.append(c)
            c = data.read(1)

        return Image.new(data.read(),
                         b"".join(description).decode('utf-8', 'replace'),
                         type)

    def add_image(self, image):
        """embeds an Image object in this metadata"""

        from audiotools import FRONT_COVER, BACK_COVER

        if image.type == FRONT_COVER:
            self[b'Cover Art (front)'] = self.ITEM.binary(
                b'Cover Art (front)',
                image.description.encode('utf-8', 'replace') +
                b"\x00" +
                image.data)
        elif image.type == BACK_COVER:
            self[b'Cover Art (back)'] = self.ITEM.binary(
                b'Cover Art (back)',
                image.description.encode('utf-8', 'replace') +
                b"\x00" +
                image.data)

    def delete_image(self, image):
        """deletes an Image object from this metadata"""

        if (image.type == 0) and b'Cover Art (front)' in self.keys():
            del(self[b'Cover Art (front)'])
        elif (image.type == 1) and b'Cover Art (back)' in self.keys():
            del(self[b'Cover Art (back)'])

    def images(self):
        """returns a list of embedded Image objects"""

        from audiotools import FRONT_COVER, BACK_COVER

        # APEv2 supports only one value per key
        # so a single front and back cover are all that is possible
        img = []
        if b'Cover Art (front)' in self.keys():
            img.append(self.__parse_image__(b'Cover Art (front)',
                                            FRONT_COVER))
        if b'Cover Art (back)' in self.keys():
            img.append(self.__parse_image__(b'Cover Art (back)',
                                            BACK_COVER))
        return img

    @classmethod
    def read(cls, apefile):
        """returns an ApeTag object from an APEv2 tagged file object

        may return None if the file object has no tag"""

        from audiotools.bitstream import BitstreamReader, parse

        apefile.seek(-32, 2)
        tag_footer = apefile.read(32)

        if len(tag_footer) < 32:
            # not enough bytes for an ApeV2 tag
            return None

        (preamble,
         version,
         tag_size,
         item_count,
         read_only,
         item_encoding,
         is_header,
         no_footer,
         has_header) = parse(cls.HEADER_FORMAT, True, tag_footer)

        if (preamble != b"APETAGEX") or (version != 2000):
            return None

        apefile.seek(-tag_size, 2)
        reader = BitstreamReader(apefile, True)

        return cls([ApeTagItem.parse(reader) for i in range(item_count)],
                   contains_header=has_header,
                   contains_footer=True)

    def build(self, writer):
        """outputs an APEv2 tag to BitstreamWriter"""

        tag_size = sum(tag.total_size() for tag in self.tags) + 32

        if self.contains_header:
            writer.build(ApeTag.HEADER_FORMAT,
                         (b"APETAGEX",               # preamble
                          2000,                      # version
                          tag_size,                  # tag size
                          len(self.tags),            # item count
                          0,                         # read only
                          0,                         # encoding
                          1,                         # is header
                          not self.contains_footer,  # no footer
                          self.contains_header))     # has header

        for tag in self.tags:
            tag.build(writer)

        if self.contains_footer:
            writer.build(ApeTag.HEADER_FORMAT,
                         (b"APETAGEX",               # preamble
                          2000,                      # version
                          tag_size,                  # tag size
                          len(self.tags),            # item count
                          0,                         # read only
                          0,                         # encoding
                          0,                         # is header
                          not self.contains_footer,  # no footer
                          self.contains_header))     # has header

    def clean(self):
        import re
        from audiotools.text import (CLEAN_REMOVE_DUPLICATE_TAG,
                                     CLEAN_REMOVE_TRAILING_WHITESPACE,
                                     CLEAN_REMOVE_LEADING_WHITESPACE,
                                     CLEAN_FIX_TAG_FORMATTING,
                                     CLEAN_REMOVE_EMPTY_TAG)

        fixes_performed = []
        used_tags = set()
        tag_items = []
        for tag in self.tags:
            if tag.key.upper() in used_tags:
                fixes_performed.append(
                    CLEAN_REMOVE_DUPLICATE_TAG %
                    {"field": tag.key.decode('ascii')})
            elif tag.type == 0:
                used_tags.add(tag.key.upper())
                text = tag.__unicode__()

                # check trailing whitespace
                fix1 = text.rstrip()
                if fix1 != text:
                    fixes_performed.append(
                        CLEAN_REMOVE_TRAILING_WHITESPACE %
                        {"field": tag.key.decode('ascii')})

                # check leading whitespace
                fix2 = fix1.lstrip()
                if fix2 != fix1:
                    fixes_performed.append(
                        CLEAN_REMOVE_LEADING_WHITESPACE %
                        {"field": tag.key.decode('ascii')})

                if tag.key in self.INTEGER_ITEMS:
                    if u"/" in fix2:
                        # item is a slashed field of some sort
                        (current, total) = fix2.split(u"/", 1)
                        current_int = re.search(r'\d+', current)
                        total_int = re.search(r'\d+', total)
                        if (current_int is None) and (total_int is None):
                            # neither side contains an integer value
                            # so ignore it altogether
                            fix3 = fix2
                        elif ((current_int is not None) and
                              (total_int is None)):
                            fix3 = u"{:d}".format(int(current_int.group(0)))
                        elif ((current_int is None) and
                              (total_int is not None)):
                            fix3 = u"{:d}/{:d}".format(
                                0, int(total_int.group(0)))
                        else:
                            # both sides contain an int
                            fix3 = u"{:d}/{:d}".format(
                                int(current_int.group(0)),
                                int(total_int.group(0)))
                    else:
                        # item contains no slash
                        current_int = re.search(r'\d+', fix2)
                        if current_int is not None:
                            # item contains an integer
                            fix3 = u"{:d}".format(int(current_int.group(0)))
                        else:
                            # item contains no integer value so ignore it
                            # (although 'Track' should only contain
                            # integers, 'Media' may contain strings
                            # so it may be best to simply ignore that case)
                            fix3 = fix2

                    if fix3 != fix2:
                        fixes_performed.append(
                            CLEAN_FIX_TAG_FORMATTING %
                            {"field": tag.key.decode('ascii')})
                else:
                    fix3 = fix2

                if len(fix3) > 0:
                    tag_items.append(ApeTagItem.string(tag.key, fix3))
                else:
                    fixes_performed.append(
                        CLEAN_REMOVE_EMPTY_TAG %
                        {"field": tag.key.decode('ascii')})
            else:
                used_tags.add(tag.key.upper())
                tag_items.append(tag)

        return (self.__class__(tag_items,
                               self.contains_header,
                               self.contains_footer),
                fixes_performed)

    def intersection(self, metadata):
        """given a MetaData-compatible object,
        returns a new MetaData object which contains
        all the matching fields and images of this object and 'metadata'
        """

        if type(metadata) is ApeTag:
            matching_keys = {key for key in
                             set(self.keys()) & set(metadata.keys())
                             if self[key] == metadata[key]}

            return ApeTag(
                [tag.copy() for tag in self.tags
                 if tag.key in matching_keys],
                contains_header=self.contains_header or
                                metadata.contains_header,
                contains_footer=self.contains_footer or
                                metadata.contains_footer)
        else:
            return MetaData.intersection(self, metadata)


class ApeTaggedAudio(object):
    """a class for handling audio formats with APEv2 tags

    this class presumes there will be a filename attribute which
    can be opened and checked for tags, or written if necessary"""

    @classmethod
    def supports_metadata(cls):
        """returns True if this audio type supports MetaData"""

        return True

    def get_metadata(self):
        """returns an ApeTag object, or None

        raises IOError if unable to read the file"""

        with open(self.filename, "rb") as f:
            return ApeTag.read(f)

    def update_metadata(self, metadata):
        """takes this track's current MetaData object
        as returned by get_metadata() and sets this track's metadata
        with any fields updated in that object

        raises IOError if unable to write the file
        """

        from audiotools.bitstream import (parse,
                                          BitstreamWriter,
                                          BitstreamReader)
        from audiotools import transfer_data

        if metadata is None:
            return
        elif not isinstance(metadata, ApeTag):
            from audiotools.text import ERR_FOREIGN_METADATA
            raise ValueError(ERR_FOREIGN_METADATA)
        elif len(metadata.keys()) == 0:
            # wipe out entire block of metadata

            from os import access, R_OK, W_OK

            if not access(self.filename, R_OK | W_OK):
                raise IOError(self.filename)

            with open(self.filename, "rb") as f:
                f.seek(-32, 2)

                (preamble,
                 version,
                 tag_size,
                 item_count,
                 read_only,
                 item_encoding,
                 is_header,
                 no_footer,
                 has_header) = BitstreamReader(f, True).parse(
                    ApeTag.HEADER_FORMAT)

            if (preamble == b'APETAGEX') and (version == 2000):
                from audiotools import TemporaryFile, transfer_data
                from os.path import getsize

                # there's existing metadata to delete
                # so rewrite file without trailing metadata tag
                if has_header:
                    old_tag_size = 32 + tag_size
                else:
                    old_tag_size = tag_size

                # copy everything but the last "old_tag_size" bytes
                # from existing file to rewritten file
                new_apev2 = TemporaryFile(self.filename)
                old_apev2 = open(self.filename, "rb")

                limited_transfer_data(
                    old_apev2.read,
                    new_apev2.write,
                    getsize(self.filename) - old_tag_size)

                old_apev2.close()
                new_apev2.close()
        else:
            # re-set metadata block at end of file

            f = open(self.filename, "r+b")
            f.seek(-32, 2)
            tag_footer = f.read(32)

            if len(tag_footer) < 32:
                # no existing ApeTag can fit, so append fresh tag
                f.close()
                with BitstreamWriter(open(self.filename, "ab"), True) as writer:
                    metadata.build(writer)
                return

            (preamble,
             version,
             tag_size,
             item_count,
             read_only,
             item_encoding,
             is_header,
             no_footer,
             has_header) = parse(ApeTag.HEADER_FORMAT, True, tag_footer)

            if (preamble == b'APETAGEX') and (version == 2000):
                if has_header:
                    old_tag_size = 32 + tag_size
                else:
                    old_tag_size = tag_size

                if metadata.total_size() >= old_tag_size:
                    # metadata has grown
                    # so append it to existing file
                    f.seek(-old_tag_size, 2)
                    writer = BitstreamWriter(f, True)
                    metadata.build(writer)
                    writer.close()
                else:
                    f.close()

                    # metadata has shrunk
                    # so rewrite file with smaller metadata
                    from audiotools import TemporaryFile
                    from os.path import getsize

                    # copy everything but the last "old_tag_size" bytes
                    # from existing file to rewritten file
                    new_apev2 = TemporaryFile(self.filename)

                    with open(self.filename, "rb") as old_apev2:
                        limited_transfer_data(
                            old_apev2.read,
                            new_apev2.write,
                            getsize(self.filename) - old_tag_size)

                    # append new tag to rewritten file
                    with BitstreamWriter(new_apev2, True) as writer:
                        metadata.build(writer)
                        # closing writer closes new_apev2 also
            else:
                # no existing metadata, so simply append a fresh tag
                f.close()
                with BitstreamWriter(open(self.filename, "ab"), True) as writer:
                    metadata.build(writer)

    def set_metadata(self, metadata):
        """takes a MetaData object and sets this track's metadata

        raises IOError if unable to write the file"""

        from audiotools.bitstream import BitstreamWriter

        if metadata is None:
            return self.delete_metadata()

        new_metadata = ApeTag.converted(metadata)
        old_metadata = self.get_metadata()

        if old_metadata is not None:
            # transfer ReplayGain tags from old metadata to new metadata
            for tag in [b"replaygain_track_gain",
                        b"replaygain_track_peak",
                        b"replaygain_album_gain",
                        b"replaygain_album_peak"]:
                try:
                    # if old_metadata has tag, shift it over
                    new_metadata[tag] = old_metadata[tag]
                except KeyError:
                    try:
                        # otherwise, if new_metadata has tag, delete it
                        del(new_metadata[tag])
                    except KeyError:
                        # if neither has tag, ignore it
                        continue

            # transfer Cuesheet from old metadata to new metadata
            if b"Cuesheet" in old_metadata:
                new_metadata[b"Cuesheet"] = old_metadata[b"Cuesheet"]
            elif b"Cuesheet" in new_metadata:
                del(new_metadata[b"Cuesheet"])

            self.update_metadata(new_metadata)
        else:
            # delete ReplayGain tags from new metadata
            for tag in [b"replaygain_track_gain",
                        b"replaygain_track_peak",
                        b"replaygain_album_gain",
                        b"replaygain_album_peak"]:
                try:
                    del(new_metadata[tag])
                except KeyError:
                    continue

            # delete Cuesheet from new metadata
            if b"Cuesheet" in new_metadata:
                del(new_metadata[b"Cuesheet"])

            if len(new_metadata.keys()) > 0:
                # no existing metadata, so simply append a fresh tag
                with BitstreamWriter(open(self.filename, "ab"), True) as writer:
                    new_metadata.build(writer)

    def delete_metadata(self):
        """deletes the track's MetaData

        raises IOError if unable to write the file"""

        if ((self.get_replay_gain() is not None) or
            (self.get_cuesheet() is not None)):
            # non-textual metadata is present and needs preserving
            self.set_metadata(MetaData())
        else:
            # no non-textual metadata, so wipe out the entire block
            from os import access, R_OK, W_OK
            from audiotools.bitstream import BitstreamReader
            from audiotools import transfer_data

            if not access(self.filename, R_OK | W_OK):
                raise IOError(self.filename)

            with open(self.filename, "rb") as f:
                f.seek(-32, 2)

                (preamble,
                 version,
                 tag_size,
                 item_count,
                 read_only,
                 item_encoding,
                 is_header,
                 no_footer,
                 has_header) = BitstreamReader(f, True).parse(
                    ApeTag.HEADER_FORMAT)

            if (preamble == b'APETAGEX') and (version == 2000):
                from audiotools import TemporaryFile
                from os.path import getsize

                # there's existing metadata to delete
                # so rewrite file without trailing metadata tag
                if has_header:
                    old_tag_size = 32 + tag_size
                else:
                    old_tag_size = tag_size

                # copy everything but the last "old_tag_size" bytes
                # from existing file to rewritten file
                new_apev2 = TemporaryFile(self.filename)
                old_apev2 = open(self.filename, "rb")

                limited_transfer_data(
                    old_apev2.read,
                    new_apev2.write,
                    getsize(self.filename) - old_tag_size)

                old_apev2.close()
                new_apev2.close()


class ApeGainedAudio(object):
    @classmethod
    def supports_replay_gain(cls):
        """returns True if this class supports ReplayGain"""

        return True

    def get_replay_gain(self):
        """returns a ReplayGain object of our ReplayGain values

        returns None if we have no values"""

        from audiotools import ReplayGain

        metadata = self.get_metadata()
        if metadata is None:
            return None

        if ({b'replaygain_track_gain', b'replaygain_track_peak',
             b'replaygain_album_gain', b'replaygain_album_peak'}.issubset(
                metadata.keys())):  # we have ReplayGain data
            try:
                return ReplayGain(
                    metadata[
                        b'replaygain_track_gain'].__unicode__()[0:-len(" dB")],
                    metadata[
                        b'replaygain_track_peak'].__unicode__(),
                    metadata[
                        b'replaygain_album_gain'].__unicode__()[0:-len(" dB")],
                    metadata[
                        b'replaygain_album_peak'].__unicode__())
            except ValueError:
                return None
        else:
            return None

    def set_replay_gain(self, replaygain):
        """given a ReplayGain object, sets the track's gain to those values

        may raise IOError if unable to read or write the file"""

        if replaygain is None:
            return self.delete_replay_gain()

        metadata = self.get_metadata()
        if metadata is None:
            metadata = ApeTag([])

        metadata[b"replaygain_track_gain"] = ApeTagItem.string(
            b"replaygain_track_gain",
            u"{:+.2f} dB".format(replaygain.track_gain))
        metadata[b"replaygain_track_peak"] = ApeTagItem.string(
            b"replaygain_track_peak",
            u"{:.6f}".format(replaygain.track_peak))
        metadata[b"replaygain_album_gain"] = ApeTagItem.string(
            b"replaygain_album_gain",
            u"{:+.2f} dB".format(replaygain.album_gain))
        metadata[b"replaygain_album_peak"] = ApeTagItem.string(
            b"replaygain_album_peak",
            u"{:.6f}".format(replaygain.album_peak))

        self.update_metadata(metadata)

    def delete_replay_gain(self):
        """removes ReplayGain values from file, if any

        may raise IOError if unable to modify the file"""

        metadata = self.get_metadata()
        if metadata is not None:
            for field in [b"replaygain_track_gain",
                          b"replaygain_track_peak",
                          b"replaygain_album_gain",
                          b"replaygain_album_peak"]:
                try:
                    del(metadata[field])
                except KeyError:
                    pass

            self.update_metadata(metadata)


class ApeAudio(ApeTaggedAudio, AudioFile):
    """a Monkey's Audio file"""

    SUFFIX = "ape"
    NAME = SUFFIX
    DEFAULT_COMPRESSION = "5000"
    COMPRESSION_MODES = tuple([str(x * 1000) for x in range(1, 6)])
    BINARIES = ("mac",)

    # FILE_HEAD = Con.Struct("ape_head",
    #                        Con.String('id', 4),
    #                        Con.ULInt16('version'))

    # #version >= 3.98
    # APE_DESCRIPTOR = Con.Struct("ape_descriptor",
    #                             Con.ULInt16('padding'),
    #                             Con.ULInt32('descriptor_bytes'),
    #                             Con.ULInt32('header_bytes'),
    #                             Con.ULInt32('seektable_bytes'),
    #                             Con.ULInt32('header_data_bytes'),
    #                             Con.ULInt32('frame_data_bytes'),
    #                             Con.ULInt32('frame_data_bytes_high'),
    #                             Con.ULInt32('terminating_data_bytes'),
    #                             Con.String('md5', 16))

    # APE_HEADER = Con.Struct("ape_header",
    #                         Con.ULInt16('compression_level'),
    #                         Con.ULInt16('format_flags'),
    #                         Con.ULInt32('blocks_per_frame'),
    #                         Con.ULInt32('final_frame_blocks'),
    #                         Con.ULInt32('total_frames'),
    #                         Con.ULInt16('bits_per_sample'),
    #                         Con.ULInt16('number_of_channels'),
    #                         Con.ULInt32('sample_rate'))

    # #version <= 3.97
    # APE_HEADER_OLD = Con.Struct("ape_header_old",
    #                             Con.ULInt16('compression_level'),
    #                             Con.ULInt16('format_flags'),
    #                             Con.ULInt16('number_of_channels'),
    #                             Con.ULInt32('sample_rate'),
    #                             Con.ULInt32('header_bytes'),
    #                             Con.ULInt32('terminating_bytes'),
    #                             Con.ULInt32('total_frames'),
    #                             Con.ULInt32('final_frame_blocks'))

    def __init__(self, filename):
        """filename is a plain string"""

        AudioFile.__init__(self, filename)

        (self.__samplespersec__,
         self.__channels__,
         self.__bitspersample__,
         self.__totalsamples__) = ApeAudio.__ape_info__(filename)

    @classmethod
    def is_type(cls, file):
        """returns True if the given file object describes this format

        takes a seekable file pointer rewound to the start of the file"""

        return file.read(4) == "MAC "

    def lossless(self):
        """returns True"""

        return True

    @classmethod
    def supports_foreign_riff_chunks(cls):
        """returns True"""

        return True

    def has_foreign_riff_chunks(self):
        """returns True"""

        # FIXME - this isn't strictly true
        # I'll need a way to detect foreign chunks in APE's stream
        # without decoding it first,
        # but since I'm not supporting APE anyway, I'll take the lazy way out
        return True

    def bits_per_sample(self):
        """returns an integer number of bits-per-sample this track contains"""

        return self.__bitspersample__

    def channels(self):
        """returns an integer number of channels this track contains"""

        return self.__channels__

    def total_frames(self):
        """returns the total PCM frames of the track as an integer"""

        return self.__totalsamples__

    def sample_rate(self):
        """returns the rate of the track's audio as an integer number of Hz"""

        return self.__samplespersec__

    @classmethod
    def __ape_info__(cls, filename):
        f = open(filename, 'rb')
        try:
            file_head = cls.FILE_HEAD.parse_stream(f)

            if file_head.id != 'MAC ':
                from audiotools.text import ERR_APE_INVALID_HEADER
                raise InvalidFile(ERR_APE_INVALID_HEADER)

            if file_head.version >= 3980:  # the latest APE file type
                descriptor = cls.APE_DESCRIPTOR.parse_stream(f)
                header = cls.APE_HEADER.parse_stream(f)

                return (header.sample_rate,
                        header.number_of_channels,
                        header.bits_per_sample,
                        ((header.total_frames - 1) *
                         header.blocks_per_frame) +
                        header.final_frame_blocks)
            else:                           # old-style APE file (obsolete)
                header = cls.APE_HEADER_OLD.parse_stream(f)

                if file_head.version >= 3950:
                    blocks_per_frame = 0x48000
                elif ((file_head.version >= 3900) or
                      ((file_head.version >= 3800) and
                       (header.compression_level == 4000))):
                    blocks_per_frame = 0x12000
                else:
                    blocks_per_frame = 0x2400

                if header.format_flags & 0x01:
                    bits_per_sample = 8
                elif header.format_flags & 0x08:
                    bits_per_sample = 24
                else:
                    bits_per_sample = 16

                return (header.sample_rate,
                        header.number_of_channels,
                        bits_per_sample,
                        ((header.total_frames - 1) *
                         blocks_per_frame) +
                        header.final_frame_blocks)

        finally:
            f.close()

    def to_wave(self, wave_filename):
        """writes the contents of this file to the given .wav filename string

        raises EncodingError if some error occurs during decoding"""

        from audiotools import BIN
        from audiotools import transfer_data
        import subprocess
        import os

        if self.filename.endswith(".ape"):
            devnull = open(os.devnull, "wb")
            sub = subprocess.Popen([BIN['mac'],
                                    self.filename,
                                    wave_filename,
                                    '-d'],
                                   stdout=devnull,
                                   stderr=devnull)
            sub.wait()
            devnull.close()
        else:
            devnull = open(os.devnull, 'ab')
            import tempfile
            ape = tempfile.NamedTemporaryFile(suffix='.ape')
            f = open(self.filename, 'rb')
            transfer_data(f.read, ape.write)
            f.close()
            ape.flush()
            sub = subprocess.Popen([BIN['mac'],
                                    ape.name,
                                    wave_filename,
                                    '-d'],
                                   stdout=devnull,
                                   stderr=devnull)
            sub.wait()
            ape.close()
            devnull.close()

    @classmethod
    def from_wave(cls, filename, wave_filename, compression=None):
        """encodes a new AudioFile from an existing .wav file

        takes a filename string, wave_filename string
        of an existing WaveAudio file
        and an optional compression level string
        encodes a new audio file from the wave's data
        at the given filename with the specified compression level
        and returns a new ApeAudio object"""

        from audiotools import BIN
        import subprocess
        import os

        if str(compression) not in cls.COMPRESSION_MODES:
            compression = cls.DEFAULT_COMPRESSION

        devnull = open(os.devnull, "wb")
        sub = subprocess.Popen([BIN['mac'],
                                wave_filename,
                                filename,
                                "-c%s" % (compression)],
                               stdout=devnull,
                               stderr=devnull)
        sub.wait()
        devnull.close()
        return ApeAudio(filename)
