#!/bin/bash

echo "================================================================================" >> /tmp/udevtest2.out
echo >> /tmp/udevtest2.out
echo "Major is: \"$1\"" >> /tmp/udevtest2.out
echo "Minor is: \"$2\"" >>  /tmp/udevtest2.out
echo "ATTR{manufacturer} is: \"$3\"" >>  /tmp/udevtest2.out
 
# Try to match PCI device path of nvme disk
if [[ $DEVPATH =~ /devices/pci0000:00/0000:00:1[d-z].0/nvme/nvme([0-9]{1,2})/nvme.n.$ ]]; then
    # NVME disk 0-1 are reserved for OS, 2-3-4-... are DATA disks
    if [[ "${BASH_REMATCH[1]}" -ge 2 ]]; then
	printf '%s => ASMNAME=asmshared0%02d\n' ${DEVPATH}     ${BASH_REMATCH[1]} >> /tmp/udevtest2.out
	printf       'ASMNAME=asmshared0%02d\n'                ${BASH_REMATCH[1]}
    fi	
fi

# Try to match PCI device path of nvme disk partition
if [[ $DEVPATH =~ /devices/pci0000:00/0000:00:1[d-z].0/nvme/nvme([0-9]{1,2})/nvme([0-9]{1,2})n./nvme.n.p1$ ]]; then
    # NVME disk 0-1 are reserved for OS, 2-3-4-... are DATA disks
    if [[ "${BASH_REMATCH[1]}" -ge 2 ]]; then
        #export V=`/usr/sbin/nvme id-ctrl ${DEVNAME} | grep ^sn | cut -d: -f2 | tr -d ' ' `
        export V=`/usr/bin/lsblk -o serial -d -n ${DEVNAME}`
        export S=`/bin/lsblk ${DEVNAME} --output SIZE -n | tr -d ' '`
        printf '%s => ASMNAME=asmshared0%02dp1-%s-%s\n' "${DEVPATH}"    "${BASH_REMATCH[1]}" "${V}" "${S}" >> /tmp/udevtest2.out
        printf       'ASMNAME=asmshared0%02dp1-%s-%s\n'                 "${BASH_REMATCH[1]}" "${V}" "${S}"
    fi
fi

env >> /tmp/udevtest2.out

exit 0

