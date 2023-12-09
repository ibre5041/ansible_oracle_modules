#!/usr/bin/env python3

__metaclass__ = type

DOCUMENTATION = r"""
---
module: describe_patchset
short_description: Parse .xml metadata in oracle patch directory
description:
  - This is not ansible module, this is standalone commandline tool
  - See EXAMPLES
author:
  - Ivan Brezina
"""

EXAMPLES = r"""
describe_patchset.py -h
usage: describe_patchset.py [-h] -d DIRECTORY

Describe patches in Oracle PatchSet

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY

./describe_patchset.py -d /install/
PATCHSET:/install/35742441:COMBO OF OJVM RU COMPONENT 19.21.0.0.231017 + GI RU 19.21.0.0.231017
PATCHSET:/install/35742441/35648110:OJVM RELEASE UPDATE 19.21.0.0.0
BUNDLEPART:/install/35742441/35642822/35655527:(cluster,rac_database,oracle_database,has)
BUNDLEPART:/install/35742441/35642822/35652062:(cluster,has)
BUNDLEPART:/install/35742441/35642822/33575402:(cluster,has)
BUNDLEPART:/install/35742441/35642822/35553096:(cluster,has)
BUNDLEPART:/install/35742441/35642822/35643107:(cluster,rac_database,oracle_database,has)
ONE-OFF:/install/35638318:JDK BUNDLE PATCH 19.0.0.0.231017:()
ONE-OFF:/install/35742441/35642822/35655527:OCW RELEASE UPDATE 19.21.0.0.0 (35655527):(cluster,rac_database,oracle_database,has)
ONE-OFF:/install/35742441/35642822/35643107:Database Release Update : 19.21.0.0.231017 (35643107):(cluster,rac_database,oracle_database,has)
ONE-OFF:/install/35742441/35642822/35652062:ACFS RELEASE UPDATE 19.21.0.0.0 (35652062):(cluster,has)
ONE-OFF:/install/35742441/35642822/35553096:TOMCAT RELEASE UPDATE 19.0.0.0.0 (35553096):(cluster,has)
ONE-OFF:/install/35742441/35642822/33575402:DBWLM RELEASE UPDATE 19.0.0.0.0 (33575402):(cluster,has)
ONE-OFF:/install/35742441/35648110:OJVM RELEASE UPDATE: 19.21.0.0.231017 (35648110):()

./describe_patchset.py -d $ORACLE_HOME/inventory
ONE-OFF:/oracle/product/19.21.0.0/db1/inventory/oneoffs/35655527:OCW RELEASE UPDATE 19.21.0.0.0 (35655527):(cluster,rac_database,oracle_database,has)
ONE-OFF:/oracle/product/19.21.0.0/db1/inventory/oneoffs/35648110:OJVM RELEASE UPDATE: 19.21.0.0.231017 (35648110):()
ONE-OFF:/oracle/product/19.21.0.0/db1/inventory/oneoffs/35643107:Database Release Update : 19.21.0.0.231017 (35643107):(cluster,rac_database,oracle_database,has)
ONE-OFF:/oracle/product/19.21.0.0/db1/inventory/oneoffs/29585399:OCW RELEASE UPDATE 19.3.0.0.0 (29585399):(cluster,rac_database,oracle_database,has)
ONE-OFF:/oracle/product/19.21.0.0/db1/inventory/oneoffs/29517242:Database Release Update : 19.3.0.0.190416 (29517242):(cluster,rac_database,oracle_database,has)
ONE-OFF:/oracle/product/19.21.0.0/db1/inventory/oneoffs/35638318:JDK BUNDLE PATCH 19.0.0.0.231017:()

"""

import os
import argparse
import glob
import xml.etree.ElementTree as ET


def parse_patchset(path):
    try:
        root = ET.parse(path).getroot()
        patch_number = root.findall("./patch/bug")[0].findall('number')[0].text
        description = root.findall("./patch/bug")[0].findall('abstract')[0].text

        d = os.path.dirname(path)
        d = os.path.join(d, patch_number)
        if os.path.isdir(d):
            print('PATCHSET:%s:%s' % (d, description))
            return d
    except:
        return None


def parse_bundle_patch(path):
    try:
        retval = []
        root = ET.parse(path).getroot()
        base_dir = os.path.dirname(path)
        for subpatch in root.findall("./subpatches/subpatch"):
            targets = []
            for t in subpatch.findall("./target_types/target_type"):
                targets.append(t.attrib['type'])
            d = os.path.join(base_dir, subpatch.attrib['location'])
            if os.path.isdir(d):
                retval.append(d)
                print('BUNDLEPART:%s:(%s)' % (d, ','.join(targets)))
        return retval
    except:
        return []


def parse_oneoff_patch(path):
    try:
        root = ET.parse(path).getroot()
        description = root.findall("./patch_description")[0].text
        base_dir = os.path.dirname(path)
        base_dir = os.path.dirname(base_dir)
        base_dir = os.path.dirname(base_dir)
        targets = []
        for t in root.findall("./targets/target"):
            targets.append(t.attrib['type'])
        print("ONE-OFF:%s:%s:(%s)" % (base_dir, description, ','.join(targets)))
    except:
        pass


def main(path):
    for f in glob.glob('%s/**/PatchSearch.xml' % path, recursive=True):
        parse_patchset(f)

    for f in glob.glob('%s/**/bundle.xml' % path, recursive=True):
        parse_bundle_patch(f)

    for f in glob.glob('%s/**/etc/config/inventory.xml' % path, recursive=True):
        parse_oneoff_patch(f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='Describe patches in Oracle PatchSet',
        epilog='Text at the bottom of help')

    parser.add_argument('-d', '--directory', required=True)
    args = parser.parse_args()

    main(os.path.abspath(args.directory))
