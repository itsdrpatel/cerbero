# cerbero - a multi-platform build system for Open Source software
# Copyright (C) 2012 Andoni Morales Alastruey <ylatuya@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import uuid
try:
  from lxml import etree
except ImportError:
    import xml.etree.cElementTree as etree

from cerbero.utils import shell
from cerbero.config import Platform


class MergeModule(object):
    '''
    Creates WiX merge modules from cerbero packages

    @ivar package: package with the info to build the merge package
    @type pacakge: L{cerbero.packages.package.Package}
    '''

    def __init__(self, config, package):
        self.platform = config.platform
        self._with_wine = self.platform != Platform.WINDOWS
        if self._with_wine:
            self.prefix = self._to_wine_path(config.prefix)
        else:
            self.prefix = config.prefix
        self.wix_prefix = config.wix_prefix
        self.package = package
        self.files_list = package.get_files_list()
        self._dirnodes = {}
        self.filled = False

    def fill(self):
        if self.filled:
            return
        self._add_root()
        self._add_module()
        self._add_package()
        self._add_root_dir()
        self._add_files()
        self.filled = True

    def render_xml(self):
        self.fill()
        return etree.tostring(self.root, pretty_print=True)

    def build(self, output_dir):
        sources = os.path.join(output_dir, "%s.wsx" % self.package.name)
        with open(sources, 'wb') as f:
            f.write(self.render_xml())

        wixobj = os.path.join(output_dir, "%s.wixobj" % self.package.name)

        if self._with_wine:
            wixobj = self._to_wine_path(wixobj)
            sources = self._to_wine_path(sources)

        candle = Candle(self.wix_prefix, self._with_wine)
        candle.compile(sources, output_dir)
        light = Light(self.wix_prefix, self._with_wine)
        light.compile(wixobj, self.package.name, output_dir, True)

    def _to_wine_path(self, path):
        path = path.replace('/', '\\\\')
        # wine maps the filesystem root '/' to 'z:\'
        path = 'z:\\%s' % path
        return path

    def _set(self, node, key, value):
        if value is None or value is "":
            return
        node.set(key, value)

    def _add_root(self):
        self.root = etree.Element("Wix")
        self._set(self.root, 'xmlns', 'http://schemas.microsoft.com/wix/2006/wi')

    def _add_module(self):
        self.module = etree.SubElement(self.root, "Module")
        self._set(self.module, 'Id', self._format_id(self.package.name))
        self._set(self.module, 'Version', self.package.version)
        self._set(self.module, 'Language', '1033')

    def _add_package(self):
        self.pkg = etree.SubElement(self.module, "Package")
        self._set(self.pkg, 'Id', self.package.uuid or self._get_uuid())
        self._set(self.pkg, 'Description', self.package.shortdesc)
        self._set(self.pkg, 'Comments', self.package.longdesc)
        self._set(self.pkg, 'Manufacturer', self.package.vendor)

    def _add_root_dir(self):
        self.rdir = etree.SubElement(self.module, "Directory")
        self._set(self.rdir, 'Id', 'TARGETDIR')
        self._set(self.rdir, 'Name', 'SourceDir')
        self._dirnodes[''] = self.rdir

    def _add_files(self):
        for f in self.files_list:
            self._add_file(f)

    def _add_directory(self, dirpath):
        if dirpath in self._dirnodes:
            return
        parentpath = os.path.split(dirpath)[0]
        if parentpath == []:
            parentpath = ['']

        if parentpath not in self._dirnodes:
            self._add_directory(parentpath)

        parent = self._dirnodes[parentpath]
        dirnode = etree.SubElement(parent, "Directory")
        self._set(dirnode, 'Id', self._format_id(dirpath))
        self._set(dirnode, 'Name', self._format_id(dirpath))
        self._dirnodes[dirpath] = dirnode

    def _add_file(self, filepath):
        dirpath, filename = os.path.split(filepath)
        self._add_directory(dirpath)
        dirnode = self._dirnodes[dirpath]
        component = etree.SubElement(dirnode, 'Component')
        self._set(component, 'Id', self._format_id(filepath))
        self._set(component, 'Guid', self._get_uuid())
        filenode = etree.SubElement(component, 'File')
        self._set(filenode, 'Id', self._format_id(filepath, True))
        self._set(filenode, 'Name', filename)
        self._set(filenode, 'Source', os.path.join(self.prefix, filepath))

    def _format_id(self, path, replace_dots=False):
        ret = path.replace('/', '_').replace('-', '_')
        if replace_dots:
            ret = ret.replace('.', '')
        return ret

    def _get_uuid(self):
        return "%s" % uuid.uuid1()


class Candle(object):

    cmd = '%(wine)s %(q)s%(prefix)s/candle.exe%(q)s %(source)s'

    def __init__(self, wix_prefix, with_wine):
        self.options = {}
        self.options['prefix'] = wix_prefix
        if with_wine:
            self.options['wine'] = 'wine'
            self.options['q'] = '"'
        else:
            self.options['wine'] = ''
            self.options['q'] = ''

    def compile(self, source, output_dir):
        self.options['source'] = source
        shell.call(self.cmd % self.options, output_dir)


class Light(object):

    cmd = '%(wine)s %(q)s%(prefix)s/light.exe%(q)s %(objects)s -o '\
          '%(msi)s.%(ext)s -sval'

    def __init__(self, wix_prefix, with_wine):
        self.options = {}
        self.options['prefix'] = wix_prefix
        if with_wine:
            self.options['wine'] = 'wine'
            self.options['q'] = '"'
        else:
            self.options['wine'] = ''
            self.options['q'] = ''

    def compile(self, objects, msi_file, output_dir, merge_module=True):
        self.options['objects'] = objects
        self.options['msi'] = msi_file
        if merge_module:
            self.options['ext'] = 'msm'
        else:
            self.options['ext'] = 'msi'
        shell.call(self.cmd % self.options, output_dir)
