#!/usr/bin/env python

import sys
import os
import shutil
import subprocess
import re

import configfile

# This script is supposed to be run in the ./dev directory as ./release.py
# It's possible to build only some components by specifying them as arguments
# for the command

ROOT_DIR = '..'
DEST_DIR = '.'
SRC_DIR = os.path.join(ROOT_DIR, 'src')
BASE_DIR = os.path.join(SRC_DIR, 'outspline')
DEPS_DIR = os.path.join(BASE_DIR, 'dbdeps')
PACKAGES = {
    'main': 'outspline',
    'development': 'outspline-development',
    'organism': 'outspline-organism',
    'experimental': 'outspline-experimental',
}

def main():
    if len(sys.argv) > 1:
        for cname in sys.argv[1:]:
            cfile = cname + '.component'
            make_component_package(cfile, cname)
            make_pkgbuild_package(cname)

    else:
        for cfile in os.listdir(BASE_DIR):
            cname, ext = os.path.splitext(cfile)

            if ext == '.component':
                make_component_package(cfile, cname)
                make_pkgbuild_package(cname)


def make_component_package(cfile, cname):
    component = configfile.ConfigFile(os.path.join(BASE_DIR, cfile),
                                                        inherit_options=False)
    pkgname = PACKAGES[cname]
    pkgver = component['version']
    pkgdirname = pkgname + '-' + pkgver
    pkgdir = os.path.join(DEST_DIR, pkgdirname)
    maindir = os.path.join(pkgdir, 'outspline')
    depsdir = os.path.join(maindir, 'dbdeps')

    os.makedirs(maindir)
    shutil.copy2(os.path.join(ROOT_DIR, 'LICENSE'), pkgdir)
    shutil.copy2(os.path.join(SRC_DIR, pkgname + '.setup.py'),
                                            os.path.join(pkgdir, 'setup.py'))
    shutil.copy2(os.path.join(BASE_DIR, cfile), maindir)
    shutil.copy2(os.path.join(BASE_DIR, '__init__.py'), maindir)

    os.makedirs(depsdir)
    shutil.copy2(os.path.join(DEPS_DIR, '__init__.py'), depsdir)

    if component.get_bool('provides_core', fallback='false'):
        for src, dest, sd in ((SRC_DIR, pkgdir, 'data'),
                              (BASE_DIR, maindir, 'static'),
                              (BASE_DIR, maindir, 'core'),
                              (BASE_DIR, maindir, 'coreaux')):
            shutil.copytree(os.path.join(src, sd), os.path.join(dest, sd),
                            ignore=shutil.ignore_patterns('*.pyc', '*.pyo'))

        for file_ in ('core_api.py', 'coreaux_api.py', 'outspline.conf'):
            shutil.copy2(os.path.join(BASE_DIR, file_), maindir)

        shutil.copy2(os.path.join(DEPS_DIR, '_core.py'), depsdir)

    addons = find_addons(component)

    for type_ in addons:
        typedir = os.path.join(maindir, type_)
        os.mkdir(typedir)
        shutil.copy2(os.path.join(BASE_DIR, type_, '__init__.py'), typedir)

        for caddon in addons[type_]:
            addon, version = caddon

            shutil.copy2(os.path.join(BASE_DIR, type_, addon + '.conf'),
                                                                    typedir)

            try:
                shutil.copy2(os.path.join(BASE_DIR, type_, addon + '_api.py'),
                                                                    typedir)
            except FileNotFoundError:
                pass

            if type_ == 'extensions':
                try:
                    shutil.copy2(os.path.join(DEPS_DIR, addon + '.py'),
                                                                    depsdir)
                except FileNotFoundError:
                    pass

            shutil.copytree(os.path.join(BASE_DIR, type_, addon),
                            os.path.join(typedir, addon),
                            ignore=shutil.ignore_patterns('*.pyc', '*.pyo'))

    shutil.make_archive(pkgdir, 'bztar', base_dir=pkgdirname)
    shutil.rmtree(pkgdir)


def find_addons(component):
    addons = {}

    for o in component:
        if o[:9] == 'extension':
            try:
                addons['extensions']
            except KeyError:
                addons['extensions'] = [component[o].split(' '), ]
            else:
                addons['extensions'].append(component[o].split(' '))
        elif o[:9] == 'interface':
            try:
                addons['interfaces']
            except KeyError:
                addons['interfaces'] = [component[o].split(' '), ]
            else:
                addons['interfaces'].append(component[o].split(' '))
        elif o[:6] == 'plugin':
            try:
                addons['plugins']
            except KeyError:
                addons['plugins'] = [component[o].split(' '), ]
            else:
                addons['plugins'].append(component[o].split(' '))

    return addons


def make_pkgbuild_package(cname):
    pkgname = PACKAGES[cname]
    pkgbuild = os.path.join(DEST_DIR, pkgname + '.PKGBUILD')

    subprocess.call(["updpkgsums", pkgbuild])

    tmppkgbuild = os.path.join(DEST_DIR, 'PKGBUILD')
    shutil.copy2(pkgbuild, tmppkgbuild)

    subprocess.call(["mkaurball", ])
    # Don't call makepkg --clean or errors will happen

    os.remove(tmppkgbuild)


if __name__ == '__main__':
    main()
