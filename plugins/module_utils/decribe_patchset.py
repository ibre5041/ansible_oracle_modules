
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

    parser.add_argument('-d', '--directory')
    args = parser.parse_args()

    main(os.path.abspath(args.directory))
