#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rose_input.py
Inkscape extension to make rose diagrams from survex (.3d) files

Based on library to handle Survex 3D files (*.3d)
Copyright (C) 2008-2012 Thomas Holder, http://sf.net/users/speleo3/

Modifications copyright (C) 2018, 2020 Patrick B Warren
Email: patrickbwarren@gmail.com

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see
<http://www.gnu.org/licenses/>.
"""

import sys
import inkex
import math as m
from struct import unpack

def fancy_round(x, offset=0.5):
    """Rounds a number, allowing 1.5 and 2.5 """
    b = m.pow(10, m.floor(m.log10(x)))
    c = m.floor(x / b + offset)
    if (c == 1.0 and x/b > 1.25) or (c == 2.0 and x/b < 1.75):
        c = 1.5
    if (c == 2.0 and x/b > 2.25) or (c == 3.0 and x/b < 2.75):
        c = 2.5
    return c * b

def analyse3d(filename, ns):
    """Read in a .3d file and extract leg data"""

    def read_xyz(fp):
        """Read xyz as signed integers according to .3d spec"""
        return unpack('<iii', fp.read(12))

    def read_len(fp):
        """Read a number as a length according to .3d spec"""
        byte = ord(fp.read(1))
        if byte != 0xff:
            return byte
        else:
            return unpack('<I', fp.read(4))[0]

    def read_label(fp):
        """Read a string as a label, or part thereof, according to .3d spec"""
        byte = ord(fp.read(1))
        if byte != 0x00:
            ndel = byte >> 4
            nadd = byte & 0x0f
        else:
            ndel = read_len(fp)
            nadd = read_len(fp)
        fp.read(nadd).decode('ascii')
        return

    with open(filename, 'rb') as fp:

        line = fp.readline().rstrip() # File ID
        if not line.startswith(b'Survex 3D Image File'):
            raise IOError('Not a Survex 3D File: ' + FILE)

        line = fp.readline().rstrip() # File format version
        if not line.startswith(b'v'):
            raise IOError('Unrecognised .3d version: ' + FILE)
        version = int(line[1:])
        if version < 8:
            raise IOError('Version >= 8 required: ' + FILE)

        line = fp.readline().rstrip() # Metadata (title, and coordinate system)

        title = line.split(b'\x00')[0].decode('utf-8')

        line = fp.readline().rstrip() # Timestamp
        if not line.startswith(b'@'):
            raise IOError('Unrecognised timestamp: ' + FILE)

        # System-wide flags

        flag = ord(fp.read(1))

        if flag & 0x80:
            raise IOError('Flagged as extended elevation: ' + FILE)

        # All front-end data read in, now read byte-wise according to .3d
        # spec, and process.  Note that all data fields must be scanned
        # otherwise the binary file read goes out of sync.

        current_style = 0xff
        nlegs = nsurf = ndup = nsplay = nhoriz = 0
        tlegs = tsurf = tdup = tsplay = thoriz = 0.0

        nsector = [0] * ns
        tsector = [0] * ns

        while True:

            char = fp.read(1)

            if not char: # End of file reached (prematurely?)
                raise IOError('Premature end of file: ' + FILE)

            byte = ord(char)

            if byte <= 0x05: # STYLE
                if byte == 0x00 and current_style == 0x00: # this signals end of data
                    break # escape from byte-gobbling while loop
                else:
                    current_style = byte

            elif byte <= 0x0e: # Reserved
                continue

            elif byte == 0x0f: # MOVE
                xyz = read_xyz(fp)

            elif byte == 0x10: # DATE (none)
                continue

            elif byte == 0x11: # DATE (single date)
                unpack('<H', fp.read(2))[0]

            elif byte == 0x12:  # DATE (date range, short format)
                unpack('<HB', fp.read(3))

            elif byte == 0x13: # DATE (date range, long format)
                unpack('<HH', fp.read(4))

            elif byte <= 0x1e: # Reserved
                continue

            elif byte == 0x1f:  # Error info
                unpack('<iiiii', fp.read(20))

            elif byte <= 0x2f: # Reserved
                continue

            elif byte <= 0x33: # XSECT
                read_label(fp)
                if byte & 0x02: # short or long format
                    unpack('<iiii', fp.read(16))
                else:
                    unpack('<hhhh', fp.read(8))

            elif byte <= 0x3f: # Reserved
                continue

            elif byte <= 0x7f: # LINE
                flag = byte & 0x3f
                if not (flag & 0x20):
                    read_label(fp)
                xyz_prev = xyz
                xyz = read_xyz(fp)
                dx, dy, dz = [0.01*(v[1] - v[0]) for v in zip(xyz_prev, xyz)]
                lhoriz = m.sqrt(dx*dx + dy*dy)
                lslant = m.sqrt(dx*dx + dy*dy + dz*dz)
                if flag & 0x01: # SURFACE
                    tsurf += lslant
                    nsurf += 1
                elif flag & 0x02: # DUPLICATE
                    tdup += lslant
                    ndup += 1
                elif flag & 0x04: # SPLAY
                    tsplay += lslant
                    nsplay += 1
                else: # UNDERGROUND
                    tlegs += lslant
                    nlegs += 1
                    if lhoriz > 0.0:
                        thoriz += lhoriz
                        nhoriz += 1

                        # Calculate the bearing in ang, given that x is
                        # east and y is north.  Add lhoriz to the sectors
                        # containing ang and ang + 180. */

                        bearing = m.atan2(dx, dy) * 180 / m.pi

                        for ang in [bearing, bearing + 180]:
                            while ang < 0:
                                ang += 360
                            while ang >= 360:
                                ang -= 360
                            i = int(round(ns * ang / 360)) % ns
                            nsector[i] += 1
                            tsector[i] += lhoriz

            elif byte <= 0xff: # LABEL (or NODE)
                read_label(fp)
                read_xyz(fp)

    return tsector, title

# Create a subclass and overwrite methods

class RoseDiagram(inkex.GenerateExtension):

    def add_arguments(self, pars):
        pars.add_argument('--file', help='.3d file')
        pars.add_argument('--title', default='', help='Set title, default fetch from file')
        pars.add_argument('--nsector', type=int, default=16, help='number of sectors, default 16')
        pars.add_argument('--bw', help='render in black and white')
        pars.add_argument('--size', type=float, default=100.0, help='overall size (px), default 100.0')
        pars.add_argument('--head', type=float, default=10.0, help='arrow head size (px), default 10.0')
        pars.add_argument('--width', type=float, default=1.0, help='line width (pt), default 1.0')

    def generate(self):
        
        bw = self.options.bw == 'true'
        size = self.svg.unittouu(str(self.options.size) + 'px')
        head = self.svg.unittouu(str(self.options.head) + 'px')
        width = self.svg.unittouu(str(self.options.width) + 'pt')
        medium = self.svg.unittouu('10pt') # font sizes, ...
        large = self.svg.unittouu('12pt') # ... could be options

        tsector, survey_title = analyse3d(self.options.file, self.options.nsector)

        tmax = max(tsector)
        thoriz = 0.5 * sum(tsector) # each leg is counted twice
        ns = len(tsector)
        tmean = 2 * thoriz / ns

        # Inner group to contain all the rose diagram elements

        rose_diagram = inkex.Group() 

        elements = [''] * (2*ns) # list of lines and arc elements

        for i, v in enumerate(tsector):
            alo = 2 * m.pi * (i - 0.5) / ns
            ahi = 2 * m.pi * (i + 0.5) / ns
            rad = size * tsector[i] / tmax
            xx0 = rad * m.sin(alo)
            yy0 = - rad * m.cos(alo)
            xx1 = rad * m.sin(ahi)
            yy1 = - rad * m.cos(ahi)
            elements[2*i] = ('L' if i else 'M') + '%7.2f, %7.2f ' % (xx0, yy0)
            elements[2*i+1] = 'A %6.2f, %6.2f 0 0,1 %7.2f, %7.2f' % (rad, rad, xx1, yy1)

        # Add the lines and arc elements - 'z' closes the path

        zigzag = inkex.PathElement(d=' '.join(elements) + ' z')
        zigzag.style = {'stroke': 'black', 'fill': 'none' if bw else 'yellow', 'stroke-width': width}
        rose_diagram.add(zigzag)

        # Adjust the scale circle radius, rounding down if necessary
        
        scale_rad = fancy_round(tmean)
        if scale_rad > tmax:
            scale_rad = fancy_round(tmean, offset=0.0)

        # Add the scale circle 

        circle = inkex.Circle(r=str(size * scale_rad / tmax))
        circle.style = {'stroke': 'black' if bw else 'blue', 'fill': 'none', 'stroke-width': width}
        if bw:
            circle.style['stroke-dasharray'] = '{step} {step}'.format(step=4*width)
        rose_diagram.add(circle)

        # Add N-S, E-W, NW-SE, NE-SW lines; the N has a half-arrow

        style = {'stroke': 'black', 'fill': 'none', 'stroke-width': width}
        style = str(inkex.Style(style))

        length = 1.05 * size
        rose_diagram.add(inkex.PathElement(d=f'M0,{-length+2*head} L{-head},{-length+2*head} L0,-{length} L0,{length}', style=style))
        rose_diagram.add(inkex.PathElement(d=f'M-{length},0 L{length},0', style=style))

        length = m.sqrt(0.5) * 1.05 * size
        rose_diagram.add(inkex.PathElement(d=f'M-{length},-{length} L{length},{length}', style=style))
        rose_diagram.add(inkex.PathElement(d=f'M{length},-{length} L-{length},{length}', style=style))

        # Add a 'N' to the north arrow
        
        north = inkex.TextElement(x=str(head), y=str(-1.05*size+head))
        north.style = {'font-family': 'Verdana', 'font-size': large, 'fill': 'black', 'text-anchor': 'middle', 'text-align': 'center'}        
        north.text = 'N'
        rose_diagram.add(north)

        yield rose_diagram

        # Add annotation for cave length and circle radius

        annotation = inkex.TextElement(x=str(0), y=str(1.3*size))
        annotation.style = {'font-family': 'Verdana', 'font-size': medium, 'fill': 'black', 'text-anchor': 'middle', 'text-align': 'center'}        
        cave_length = f'{round(thoriz/1000, 1)} km' if thoriz > 10000 else f'{round(thoriz)} m'
        circle_radius = f'{scale_rad/1000} km' if scale_rad > 1000 else f'{scale_rad} m'
        annotation.text = f'length {cave_length}, circle radius is {circle_radius}'
        
        yield annotation

        # Add a title
        
        title = inkex.TextElement(x=str(0), y=str(-1.3*size))
        title.style = {'font-family': 'Verdana', 'font-size': large, 'fill': 'black', 'text-anchor': 'middle', 'text-align': 'center'}        
        title.text = self.options.title or survey_title

        yield title

if __name__ == '__main__':
    RoseDiagram().run()
