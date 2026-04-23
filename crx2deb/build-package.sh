#!/bin/bash
set -e
./build.sh
dpkg-buildpackage -us -uc -b 
