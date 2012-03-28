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
import inspect

from cerbero.config import Platform
from cerbero.utils import shell


class FilesProvider(object):
    '''
    List files by categories using class attributes named file_$category
    '''

    LIBS_CAT = 'libs'
    BINS_CAT = 'bins'
    DEVEL_CAT = 'devel'

    EXTENSIONS = {
        Platform.WINDOWS: {'bext': '.exe', 'sext': '.dll', 'sdir': 'bin'},
        Platform.LINUX: {'bext': '', 'sext': '.so', 'sdir': 'lib'},
        Platform.DARWIN: {'bext': '', 'sext': '.dylib', 'sdir': 'lib'}}

    def __init__(self, config):
        self.platform = config.target_platform
        self.prefix = config.prefix
        self.extensions = self.EXTENSIONS[self.platform]
        self.categories = self._files_categories()
        self._searchfuncs = {self.LIBS_CAT: self._search_libraries,
                             self.BINS_CAT: self._search_binaries,
                             'default': self._search_files}

    def devel_files_list(self):
        '''
        Return the list of development files, which consists in the files and
        directories listed in the 'devel' category and the link libraries .a,
        .la and .so from the 'libs' category
        '''
        devfiles = self.files_list_by_category(self.DEVEL_CAT)
        devfiles.extend(self._search_devel_libraries())
        return sorted(list(set(devfiles)))

    def dist_files_list(self):
        '''
        Return the list of files that should be included in a distribution
        tarball, which include all files except the development files
        '''
        return self.files_list_by_categories([x for x in self.categories \
                if x != self.DEVEL_CAT])

    def files_list(self):
        '''
        Return the complete list of files
        '''
        files = self.dist_files_list()
        files.extend(self.devel_files_list())
        return sorted(list(set(files)))

    def files_list_by_categories(self, categories):
        '''
        Return the list of files in a list categories
        '''
        files = []
        for cat in categories:
            files.extend(self._list_files_by_category(cat))
        return sorted(list(set(files)))

    def files_list_by_category(self, category):
        '''
        Return the list of files in a given category
        '''
        return self.files_list_by_categories([category])

    def _files_categories(self):
        ''' Get the list of categories available '''
        categories = []
        for name, value in inspect.getmembers(self):
            if (isinstance(value, list) or isinstance(value, dict)) and \
                    name.startswith('files_'):
                categories.append(name.split('_')[1])
        return sorted(list(set(categories)))

    def _get_category_files_list(self, category):
        '''
        Get the raw list of files in a category, without pattern match nor
        extensions replacement, which should be done in the search function
        '''
        files = []
        files_attr = 'files_%s' % category
        files_plat_attr = 'files_%s_platform' % category
        if hasattr(self, files_attr):
            files.extend(getattr(self, files_attr))
        if hasattr(self, files_plat_attr):
            files.extend(getattr(self, files_plat_attr)[self.platform])
        return files

    def _list_files_by_category(self, category):
        search = self._searchfuncs.get(category, self._searchfuncs['default'])
        return search(self._get_category_files_list(category))

    def _search_files(self, files):
        '''
        Search files in the prefix, doing the extension replacements and
        listing directories
        '''
        # replace extensions
        fs = [f % self.extensions for f in files]
        # fill directories
        dirs = [x for x in fs if os.path.isdir(os.path.join(self.prefix, x))]
        for directory in dirs:
            fs.remove(directory)
            fs.exend(self._ls_dir(os.path.join(self.prefix, directory)))
        return fs

    def _search_binaries(self, files):
        '''
        Search binaries in the prefix. This function doesn't do any real serach
        like the others, it only preprend the bin/ path and add the binary
        extension to the given list of files
        '''
        binaries = []
        for f in files:
            self.extensions['file'] = f
            binaries.append('bin/%(file)s%(bext)s' % self.extensions)
        return binaries

    def _search_libraries(self, files):
        '''
        Search libraries in the prefix. Unfortunately the filename might vary
        depending on the platform and we need to match the library name and
        it's extension
        '''
        if len(files) == 0:
            return []

        pattern = '%(sdir)s/%(file)s*%(sext)s'
        if self.platform == Platform.LINUX:
            # libfoo.so.X, libfoo.so.X.Y.Z
            pattern += '.*'

        libsmatch = []
        for f in files:
            self.extensions['file'] = f
            libsmatch.append(pattern % self.extensions)
        return self._ls_files(libsmatch)

    def _search_devel_libraries(self):
        pattern = 'lib/%(f)s*.a lib/%(f)s*.la \
                   lib/%(f)s*.so'
        libsmatch = [pattern % {'f':x} for x in \
                     self._get_category_files_list(self.LIBS_CAT)]
        return self._ls_files(libsmatch)

    def _ls_files(self, files):
        # FIXME: I think's that's the fastest way of getting the list of
        # files that matches a name. glob or fnmatch+os.walk could
        # be used, but requiring a function call ')) each entry instead
        # of a single one
        sfiles = shell.check_call('ls %s' % ' '.join(files),
                self.prefix, True, False, False).split('\n')
        sfiles.remove('')
        # remove duplicates
        return list(set(sfiles))

    def _ls_dir(self, dirpath):
        files = []
        for root, dirnames, filenames in os.walk('dirpath'):
            files.extend([os.path.join(root, x) for x in filenames])
        return files