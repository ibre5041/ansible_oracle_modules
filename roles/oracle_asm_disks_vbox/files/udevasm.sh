#!/bin/bash

echo "================================================================================" >> /tmp/udevtest2.out
echo >> /tmp/udevtest2.out
echo "Major is: $1" >> /tmp/udevtest2.out
echo "Minor is: $2" >>  /tmp/udevtest2.out
echo "ATTR{manufacturer} is: $3" >>  /tmp/udevtest2.out

env >> /tmp/udevtest2.out

if [[ "${DEVTYPE}" == "partition" && "${DEVNAME}" =~ /dev/[a-z]+([0-9]) ]]; then
PART="p"${BASH_REMATCH[1]}
else
PART=""
fi

# SCSI Target NUMBERS do not seem to be persistent
#[[ $DEVPATH =~ /target([1-9]):[0-9]:([0-9]) ]] && printf '%s => ASMNAME=asmshared%02d%02d%s\n' ${DEVPATH} ${BASH_REMATCH[1]} ${BASH_REMATCH[2]} "${PART}" >> /tmp/udevtest2.out
#[[ $DEVPATH =~ /target([1-9]):[0-9]:([0-9]) ]] && printf  '     ASMNAME=asmshared%02d%02d%s\n'            ${BASH_REMATCH[1]} ${BASH_REMATCH[2]} "${PART}"

# [[ $DEVPATH =~ /target([1-9]):[0-9]:([0-9]) ]] && printf '%s => ASMNAME=asmshared%02d%02d%s\n' ${DEVPATH} "1"                 ${BASH_REMATCH[2]} "${PART}" >> /tmp/udevtest2.out
# [[ $DEVPATH =~ /target([1-9]):[0-9]:([0-9]) ]] && printf       'ASMNAME=asmshared%02d%02d%s\n'            "1"                 ${BASH_REMATCH[2]} "${PART}"

if [[ $DEVPATH =~ /target([1-9]):[0-9]:([0-9]+) ]]; then
    # LUNs 0-3 are reserved for OS, 4-6,8-15 are DATA disks
    if [[ "${BASH_REMATCH[1]}" -ge 2 ]]; then
	printf '%s => ASMNAME=asmshared%02d%02d%s\n' ${DEVPATH} "1"                 ${BASH_REMATCH[2]} "${PART}" >> /tmp/udevtest2.out
	printf       'ASMNAME=asmshared%02d%02d%s\n'            "1"                 ${BASH_REMATCH[2]} "${PART}"
    fi	
fi

exit 0
