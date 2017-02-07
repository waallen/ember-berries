#!/bin/python

from os import walk, listdir, curdir, rename
from os.path import abspath, splitext, join, isdir, isfile, split, basename, normpath, dirname, relpath
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3, HeaderNotFoundError
from mutagen import File
from pprint import pprint
from difflib import SequenceMatcher
import re
import musicbrainzngs

albums = list()
error_log = open('warnings.log', 'w+')


class Album:
    def __str__(self):
        return "Album: {}\nArtist: {}\nYear: {}\nBit rate: {}\nSource: {}\nCurrent path: {}\nAfter renaming: {}\n".format(
            self.album, self.artist, self.year, self.bit_rate, self.source,
            self.current_path, self.new_path)


def get_avg_bit_rate(path):
    avg_bit_rate = 0
    cnt = 0
    for root, dirs, files in walk(path):
        for f in files:
            if splitext(f)[1] == '.mp3':
                file_path = abspath(join(path, f))
                audio = MP3(file_path, ID3=EasyID3)
                avg_bit_rate = avg_bit_rate + audio.info.bitrate
                cnt = cnt + 1
                return avg_bit_rate / cnt
                # TODO: discern MP3 exception from audio.info exception


def get_artist(path):
    artists = set()
    for root, dirs, files in walk(path):
        for f in files:
            if splitext(f)[1] == '.mp3' or splitext(f)[1] == '.flac':
                file_path = abspath(join(path, f))
                try:
                    audio = MP3(file_path, ID3=EasyID3)
                    for new_artist in audio['artist']:
                        for artist_from_set in artists:
                            if SequenceMatcher(None, artist_from_set,
                                               new_artist).ratio() > 0.7:
                                continue
                        artists.add(new_artist)
                        return 'Various Artists' if len(
                            artists) > 3 else ' & '.join(
                                map(lambda x: '%s' % x, artists)).replace(
                                    '/', '-').replace('\\', '-')
                except KeyError:
                    raise ArtistError('No artist tag in "{}"'.format(
                        join(
                            basename(dirname(file_path)),
                            basename(normpath(file_path)))))


def get_album(audio, file_path):
    try:
        album = audio['album'][0].replace('/', '-').replace('\\', '-')
        return album
    except KeyError:
        raise AlbumError('No album tag in "{}"'.format(
            join(basename(dirname(file_path)), basename(normpath(file_path)))))


def get_date(audio, file_path):
    try:
        date = audio['date'][0]
        m = re.search(r"[\(\[]19\d{2}|20\d{2}", file_path)
        if m:
            year_from_title = m.group(0).replace('(', '')
            if year_from_title != date:
                error_log.write(
                    'WARNING: Tag/from_title date mismatch for "{}" ({} != {}).\n'.
                    format(
                        join(
                            basename(dirname(file_path)),
                            basename(normpath(file_path))), year_from_title,
                        date))
                # assuming that year_from_title is more reliable than year from
                # tags
                date = year_from_title
        return date
    except:
        raise DateError('No year tag in "{}"'.format(
            join(basename(dirname(file_path)), basename(normpath(file_path)))))


def get_bit_rate(audio, file_path):
    try:
        if str(audio.info.bitrate_mode) == 'BitrateMode.VBR':
            bit_rate = 'V0' if get_avg_bit_rate(
                dirname(file_path)) >= 203 else 'V2'
        else:
            bit_rate = str(int(audio.info.bitrate / 1000))
        return bit_rate
    except:
        raise BitRateError('Could not fetch file info for "{}"'.format(
            join(basename(dirname(file_path)), basename(normpath(file_path)))))


class ArtistError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class BitRateError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class AlbumError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class DateError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def process_mp3_album(d, f):
    a = Album()
    a.format = 'mp3'
    a.current_path = d.split('/', 1)[0]
    if 'web' in d.lower():
        a.source = 'WEB'
    else:
        if 'vinyl' in d.lower():
            a.source = 'VINYL'
        else:
            a.source = 'CD'
    file_path = abspath(join(d, f))
    try:
        audio = MP3(file_path, ID3=EasyID3)
        a.artist = get_artist(d)
        a.album = get_album(audio, file_path)
        a.year = get_date(audio, file_path)
        a.bit_rate = get_bit_rate(audio, file_path)
        a.new_path = '{} - {} ({}) [{} {}]'.format(a.artist, a.album, a.year,
                                                   a.source, a.bit_rate)
        albums.append(a)
    except HeaderNotFoundError as e:
        error_log.write('SKIP_ITEM: No header found for "{}".\n'.format(
            join(basename(dirname(file_path)), basename(normpath(file_path)))))
        # audio = File(file_path, ID3=EasyID3)
        return
    except (ArtistError, AlbumError, DateError, BitRateError) as e:
        error_log.write('SKIP_ITEM: {}.\n'.format(e.msg))
        return


def main():
    musicbrainzngs.set_useragent("Folder renamer", "0.1", "egitto@gmail.com")
    for d in (d for d in listdir(curdir) if isdir(join(curdir, d))):
        files = (f for f in listdir(join(curdir, d))
                 if isfile(join(curdir, d, f)))
        for f in files:
            if f.endswith('.mp3'):
                process_mp3_album(d, f)
                break
            for subdir in (subdir for subdir in listdir(join(curdir, d))
                           if isdir(join(curdir, d, subdir))):
                error_log.write(
                    'WARNING: Subfolders detected "{}".\n'.format(d))
                files = (f for f in listdir(join(curdir, d, subdir))
                         if isfile(join(curdir, d, subdir, f)))
                for f in files:
                    if splitext(f)[1] == '.mp3':
                        process_mp3_album(join(d, subdir), f)
                    break
                break
    cnt = 0
    f = open('preview.log', 'w+')
    for e in albums:
        f.write('Item #{}\n{}\n'.format(cnt, str(e)))
        # rename(join(curdir, e.current_path), join(curdir, e.new_path))
        cnt += 1
    results = musicbrainzngs.search_releases(query="AS", limit=3, tracks=6)
    selector = 0
    print(
        'Please select an entry that matches with the album you are trying to rename ("s" to skip, "w" to whitelist):'
    )
    for res in results['release-list']:
        print("{}. {} by {}, {} tracks, released in {}, score {}".format(
            selector, res['title'], res['artist-credit-phrase'],
            res['medium-track-count'], res['date'], res['ext:score']))
        selector += 1
    # selector = input()
    # print(selector)


if __name__ == '__main__':
    main()
