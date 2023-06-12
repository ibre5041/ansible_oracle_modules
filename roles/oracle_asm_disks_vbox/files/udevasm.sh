#!/bin/bash

echo "================================================================================" >> /tmp/udevasm.out

# Try to match PCI device path of nvme disk
if [[ $DEVPATH =~ /devices/pci0000:00/0000:00:...0/nvme/nvme[0-9]{1,2}/nvme([0-9]{1,2})n([0-9]{1,2})$ ]]; then
    # All NVME disks 0-1 are reserved for database data
    if [[ "${BASH_REMATCH[2]}" -ge 0 ]]; then
        printf '%s => ASMNAME=asmshared0%02d%02d\n' ${DEVPATH}     ${BASH_REMATCH[1]} ${BASH_REMATCH[2]} >> /tmp/udevasm.out
        printf       'ASMNAME=asmshared0%02d%02d\n'                ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}
    fi
fi

# Try to match PCI device path of nvme disk partition
if [[ $DEVPATH =~ /devices/pci0000:00/0000:00:...0/nvme/nvme[0-9]{1,2}/nvme([0-9]{1,2})n([0-9]{1,2})/nvme.n.p1$ ]]; then
    # All NVME disks 0-1 are reserved for database data
    if [[ "${BASH_REMATCH[2]}" -ge 0 ]]; then
        #export V=`/usr/sbin/nvme id-ctrl ${DEVNAME} | grep ^sn | cut -d: -f2 | tr -d ' ' `
        export V=`/usr/bin/lsblk -o serial -d -n ${DEVNAME}`
        export S=`/bin/lsblk ${DEVNAME} --output SIZE -n | tr -d ' '`
        printf '%s => ASMNAME=asmshared0%02d%02d-%s-%s-p1\n' "${DEVPATH}"   "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${V}" "${S}" >> /tmp/udevasm.out
        printf       'ASMNAME=asmshared0%02d%02d-%s-%s-p1\n'                "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${V}" "${S}"
    fi
fi

env >> /tmp/udevasm.out

exit 0
