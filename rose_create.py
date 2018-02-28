#!/usr/bin/env python

"""
rose_input.py
Python script for creating rose diagrams from survex (.3d) files in Inkscape

Based on library to handle Survex 3D files (*.3d) 
Copyright (C) 2008-2012 Thomas Holder, http://sf.net/users/speleo3/

Modifications to compute rose diagram Copyright (C) 2018 Patrick B Warren

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
import math as m
from struct import unpack
import inkex

def fancyround(x):
  b = m.pow(10, m.floor(m.log10(x)));
  c = m.floor(x / b + 0.5);
  if (c == 1.0 and x/b > 1.25) or (c == 2.0 and x/b < 1.75):
      c = 1.5;
  if (c == 2.0 and x/b > 2.25) or (c == 3.0 and x/b < 2.75):
      c = 2.5;
  return c * b

def fancyfloor(x):
  b = m.pow(10, m.floor(log10(x)));
  c = m.floor(x / b);
  if (c == 1.0 and x/b > 1.25) or (c == 2.0 and x/b < 1.75):
      c = 1.5;
  if (c == 2.0 and x/b > 2.25) or (c == 3.0 and x/b < 2.75):
      c = 2.5;
  return c * b

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

# Start of main code

e = inkex.Effect()

e.OptionParser.add_option('--title', action = 'store',
                          type = 'string', dest = 'title', default = '',
                          help = 'Set title (default fetch from file)')

e.OptionParser.add_option('--nsector', action = 'store',
                          type = 'string', dest = 'nsector', default = '16',
                          help = 'number of sectors (default 16)')

e.OptionParser.add_option('--bw', action = 'store',
                          type = 'string', dest = 'bw', default = '0',
                          help = 'render in black and white (1) or colour (0) (default colour)')

e.getoptions()

ns = int(e.options.nsector)
bw = e.options.bw == 'true'
FILE = sys.argv[-1]

try: # catch IOErrors below

    with open(FILE, 'rb') as fp:
    
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

        title = e.options.title if e.options.title else line.split(b'\x00')[0].decode('utf-8')

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
	        lhoriz = m.sqrt(dx*dx + dy*dy);
	        len = m.sqrt(dx*dx + dy*dy + dz*dz);
	        if flag & 0x01: # SURFACE
                    tsurf += len
                    nsurf += 1
                elif flag & 0x02: # DUPLICATE
                    tdup += len
                    ndup += 1
                elif flag & 0x04: # SPLAY
                    tsplay += len
                    nsplay += 1
                else: # UNDERGROUND
	            tlegs += len
                    nlegs += 1
	            if lhoriz > 0.0:
	                thoriz += lhoriz
                        nhoriz += 1

	                # Calculate the bearing in ang, given that x is
	                # east and y is north.  Add len to the sectors
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

    # .3d file closes automatically, with open(FILE, 'rb') as fp:

except IOError, msg:
    
    inkex.errormsg(str(msg))
    sys.exit(1)

# Construct a string with the SVG rose diagram

rad_circle = 420

string  = "<?xml version=\"1.0\" standalone=\"no\"?>\n"
string += "<!DOCTYPE svg PUBLIC \"-//W3C//DTD SVG 1.1//EN\"\n"
string += "\"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd\">\n"
string += "<svg width=\"12cm\" height=\"12cm\" viewBox=\"0 0 1200 1200\"\n"
string += "     xmlns=\"http://www.w3.org/2000/svg\" version=\"1.1\">\n"
string += "  <g transform=\"translate(600,610)\">\n"

tmax = max(tsector)
tmean = 2 * thoriz / ns

for i in range(ns):
    alo = 2 * m.pi * (i - 0.5) / ns
    ahi = 2 * m.pi * (i + 0.5) / ns
    rad = rad_circle * tsector[i] / tmax
    xx0 = rad * m.sin(alo)
    yy0 = - rad * m.cos(alo)
    xx1 = rad * m.sin(ahi)
    yy1 = - rad * m.cos(ahi)
    if i == 0:
        string += "    <path d=\"M %7.2f, %7.2f " % (xx0, yy0)
    else:
        string += "             L %7.2f, %7.2f " % (xx0, yy0)
    string += "A %6.2f, %6.2f 0 0,1 %7.2f, %7.2f" % (rad, rad, xx1, yy1)
    if i < ns-1:
        string += "\n"
    else:
        string += " z\"\n" 

string += "          fill=\"%s\" stroke=\"black\" stroke-width=\"2\" />\n" % ('none' if bw else 'yellow')

rad = fancyround(tmean)

if rad > tmax:
    rad = fancyfloor(tmean)

string += "    <circle%s r=\"%0.2f\" fill=\"none\" stroke=\"%s\" stroke-width=\"2\" />\n" % (' stroke-dasharray="10 10"' if bw else '',
                                                                                             rad_circle * rad / tmax,
                                                                                             'black' if bw else 'blue')

string += "    <path d=\"M-450,0 h900\" fill=\"none\" stroke=\"black\" stroke-width=\"2\" />\n"
string += "    <path d=\"M0,-450 v900\" fill=\"none\" stroke=\"black\" stroke-width=\"2\" />\n"
string += "    <path d=\"M-318.2,-318.2 L318.2,318.2\" fill=\"none\" stroke=\"black\" stroke-width=\"2\" />\n"
string += "    <path d=\"M318.2,-318.2 L-318.2,318.2\" fill=\"none\" stroke=\"black\" stroke-width=\"2\" />\n"

string += "    <text x=\"-480\" y=\"0\" font-family=\"Verdana\" font-size=\"50\" \n"
string += "          fill=\"black\" dy=\"0.35em\" text-anchor=\"middle\">W</text>\n"
string += "    <text x=\"480\" y=\"0\" font-family=\"Verdana\" font-size=\"50\" \n"
string += "          fill=\"black\" dy=\"0.35em\" text-anchor=\"middle\">E</text>\n"
string += "    <text x=\"0\" y=\"-480\" dy=\"0.35em\" font-family=\"Verdana\" font-size=\"50\"\n"
string += "          fill=\"black\" text-anchor=\"middle\">N</text>\n"
string += "    <text x=\"0\" y=\"480\" dy=\"0.35em\" font-family=\"Verdana\" font-size=\"50\"\n"
string += "          fill=\"black\" text-anchor=\"middle\">S</text>\n"
    
string += "    <text x=\"344.4\" y=\"344.4\" dy=\"0.35em\" font-family=\"Verdana\" font-size=\"50\"\n" 
string += "          fill=\"black\" text-anchor=\"middle\">SE</text>\n"

string += "    <text x=\"-344.4\" y=\"344.4\" dy=\"0.35em\" font-family=\"Verdana\" font-size=\"50\"\n"
string += "          fill=\"black\" text-anchor=\"middle\">SW</text>\n"

string += "    <text x=\"344.4\" y=\"-344.4\" dy=\"0.3em\" font-family=\"Verdana\" font-size=\"50\"\n"
string += "          fill=\"black\" text-anchor=\"middle\">NE</text>\n"

string += "    <text x=\"-344.4\" y=\"-344.4\" dy=\"0.3em\" font-family=\"Verdana\" font-size=\"50\"\n"
string += "          fill=\"black\" text-anchor=\"middle\">NW</text>\n"

string += "  </g>\n"

string += "    <text x=\"600\" y=\"70\" font-family=\"Verdana\" font-size=\"60\"\n"
string += "          fill=\"black\" text-anchor=\"middle\">%s</text>\n" % title

string += "    <text x=\"600\" y=\"1190\" font-family=\"Verdana\" font-size=\"50\"\n"

string += "          fill=\"black\" text-anchor=\"middle\">"
string += "length %g %s, " % ((round(thoriz/100)/10, "km") if thoriz > 10000 else (round(thoriz), "m"))
string += "circle radius is %g %s</text>\n" % ((rad/1000, "km") if rad > 1000 else (rad, "m"))
        
string += "</svg>\n"

sys.stdout.write(string)

sys.exit(0)
