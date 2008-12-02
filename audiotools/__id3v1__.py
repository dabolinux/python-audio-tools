#!/usr/bin/python

#Audio Tools, a module and set of tools for manipulating audio data
#Copyright (C) 2007-2008  Brian Langenberger

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

from audiotools import MetaData,Con

class ID3v1Comment(MetaData,list):
    ID3v1 = Con.Struct("id3v1",
      Con.Const(Con.String("identifier",3),'TAG'),
      Con.String("song_title",30),
      Con.String("artist",30),
      Con.String("album",30),
      Con.String("year",4),
      Con.String("comment",28),
      Con.Padding(1),
      Con.Byte("track_number"),
      Con.Byte("genre"))

    ID3v1_NO_TRACKNUMBER = Con.Struct("id3v1_notracknumber",
      Con.Const(Con.String("identifier",3),'TAG'),
      Con.String("song_title",30),
      Con.String("artist",30),
      Con.String("album",30),
      Con.String("year",4),
      Con.String("comment",30),
      Con.Byte("genre"))

    ATTRIBUTES = ['track_name',
                  'artist_name',
                  'album_name',
                  'year',
                  'comment',
                  'track_number']

    #takes an open mp3 file object
    #returns a (song title, artist, album, year, comment, track number) tuple
    #if no ID3v1 tag is present, returns a tuple with those fields blank
    #all text is in unicode
    #if track number is -1, the id3v1 comment could not be found
    @classmethod
    def read_id3v1_comment(cls, mp3filename):
        mp3file = file(mp3filename,"rb")
        try:
            mp3file.seek(-128,2)
            try:
                id3v1 = ID3v1Comment.ID3v1.parse(mp3file.read())
            except Con.adapters.PaddingError:
                mp3file.seek(-128,2)
                id3v1 = ID3v1Comment.ID3v1_NO_TRACKNUMBER.parse(mp3file.read())
                id3v1.track_number = 0
            except Con.ConstError:
                return tuple([u""] * 5 + [-1])

            field_list = (id3v1.song_title,
                          id3v1.artist,
                          id3v1.album,
                          id3v1.year,
                          id3v1.comment)

            return tuple(map(lambda t:
                             t.rstrip('\x00').decode('ascii','replace'),
                             field_list) + [id3v1.track_number])
        finally:
            mp3file.close()


    #takes several unicode strings (except for track_number, an int)
    #pads them with nulls and returns a complete ID3v1 tag
    @classmethod
    def build_id3v1(cls, song_title, artist, album, year, comment,
                    track_number):
        def __s_pad__(s,length):
            if (len(s) < length):
                return s + chr(0) * (length - len(s))
            else:
                s = s[0:length].rstrip()
                return s + chr(0) * (length - len(s))

        c = Con.Container()
        c.identifier = 'TAG'
        c.song_title = __s_pad__(song_title.encode('ascii','replace'),30)
        c.artist = __s_pad__(artist.encode('ascii','replace'),30)
        c.album = __s_pad__(album.encode('ascii','replace'),30)
        c.year = __s_pad__(year.encode('ascii','replace'),4)
        c.comment = __s_pad__(comment.encode('ascii','replace'),28)
        c.track_number = int(track_number)
        c.genre = 0

        return ID3v1Comment.ID3v1.build(c)

    #metadata is the title,artist,album,year,comment,tracknum tuple returned by
    #read_id3v1_comment
    def __init__(self, metadata):
        MetaData.__init__(self,
                          track_name=metadata[0],
                          track_number=metadata[5],
                          album_name=metadata[2],
                          artist_name=metadata[1],
                          performer_name=u"",
                          copyright=u"",
                          year=unicode(metadata[3]),
                          comment=metadata[4])
        list.__init__(self, metadata)

    #if an attribute is updated (e.g. self.track_name)
    #make sure to update the corresponding list item
    def __setattr__(self, key, value):
        self.__dict__[key] = value

        if (key in self.ATTRIBUTES):
            if (key not in ('track_number','album_number')):
                self[self.ATTRIBUTES.index(key)] = value
            else:
                self[self.ATTRIBUTES.index(key)] = int(value)

    #if a list item is updated (e.g. self[1])
    #make sure to update the corresponding attribute
    def __setitem__(self, key, value):
        list.__setitem__(self, key, value)

        if (key < len(self.ATTRIBUTES)):
            if (key != 5):
                self.__dict__[self.ATTRIBUTES[key]] = value
            else:
                self.__dict__[self.ATTRIBUTES[key]] = int(value)

    @classmethod
    def converted(cls, metadata):
        if ((metadata is None) or (isinstance(metadata,ID3v1Comment))):
            return metadata

        return ID3v1Comment((metadata.track_name,
                             metadata.artist_name,
                             metadata.album_name,
                             metadata.year,
                             metadata.comment,
                             int(metadata.track_number)))

    def __comment_name__(self):
        return u'ID3v1'

    def __comment_pairs__(self):
        return zip(('Title','Artist','Album','Year','Comment','Tracknum'),
                   self)

    def build_tag(self):
        return self.build_id3v1(self.track_name,
                                self.artist_name,
                                self.album_name,
                                self.year,
                                self.comment,
                                self.track_number)


class ID3CommentPair(MetaData):
    #id3v2 and id3v1 are ID3v2Comment and ID3v1Comment objects or None
    #values in ID3v2 take precendence over ID3v1, if present
    def __init__(self, id3v2_comment, id3v1_comment):
        self.__dict__['id3v2'] = id3v2_comment
        self.__dict__['id3v1'] = id3v1_comment

        if (self.id3v2 is not None):
            base_comment = self.id3v2
        elif (self.id3v1 is not None):
            base_comment = self.id3v1
        else:
            raise ValueError("id3v2 and id3v1 cannot both be blank")

        fields = dict([(field,getattr(base_comment,field))
                       for field in self.__FIELDS__])

        MetaData.__init__(self,**fields)

    def __setattr__(self, key, value):
        self.__dict__[key] = value

        if (self.id3v2 is not None):
            setattr(self.id3v2,key,value)
        if (self.id3v1 is not None):
            setattr(self.id3v1,key,value)

    @classmethod
    def converted(cls, metadata):
        if ((metadata is None) or (isinstance(metadata,ID3CommentPair))):
            return metadata

        if (isinstance(metadata,ID3v2Comment)):
            return ID3CommentPair(metadata,
                                  ID3v1Comment.converted(metadata))
        else:
            return ID3CommentPair(
                ID3v2_3Comment.converted(metadata),
                ID3v1Comment.converted(metadata))


    def __unicode__(self):
        if ((self.id3v2 != None) and (self.id3v1 != None)):
            #both comments present
            return unicode(self.id3v2) + \
                   (os.linesep * 2) + \
                   unicode(self.id3v1)
        elif (self.id3v2 is not None):
            #only ID3v2
            return unicode(self.id3v2)
        elif (self.id3v1 is not None):
            #only ID3v1
            return unicode(self.id3v1)
        else:
            return u''

    #ImageMetaData passthroughs
    def images(self):
        if (self.id3v2 is not None):
            return self.id3v2.images()
        else:
            return []

    def add_image(self, image):
        if (self.id3v2 is not None):
            self.id3v2.add_image(image)

    def delete_image(self, image):
        if (self.id3v2 is not None):
            self.id3v2.delete_image(image)

    @classmethod
    def supports_images(cls):
        return True
