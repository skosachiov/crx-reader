#!/bin/bash
set -e

# Locate and decode CRX
SRC_FILE=$(find src -maxdepth 1 -type f ! -name ".*" | head -1)
if [ -z "$SRC_FILE" ]; then
    echo "Error: No file found in src/"
    exit 1
fi

mkdir -p tmp
base64 -d "$SRC_FILE" > tmp/extension.crx

# Extract metadata
CRX_NAME=$(python3 debian/scripts/crx_reader.py --name tmp/extension.crx)
CRX_ID=$(python3 debian/scripts/crx_reader.py --id tmp/extension.crx)
CRX_VERSION=$(python3 debian/scripts/crx_reader.py --version tmp/extension.crx)

echo "Extension: $CRX_NAME ($CRX_ID) version $CRX_VERSION"

# Generate debian/changelog from template
sed -e "s/@PACKAGE@/chromium-extension-custom/g" \
    -e "s/@VERSION@/$CRX_VERSION/g" \
    -e "s/@CRX_NAME@/$CRX_NAME/g" \
    -e "s/@CRX_ID@/$CRX_ID/g" \
    -e "s/@MAINTAINER_NAME@/${MAINTAINER_NAME:-Your Name}/g" \
    -e "s/@MAINTAINER_EMAIL@/${MAINTAINER_EMAIL:-your.email@example.com}/g" \
    -e "s/@BUILD_DATE@/$(date -R)/g" \
    debian/changelog.in > debian/changelog

# Generate debian/control from control.in
sed -e "s/@CRX_ID@/$CRX_ID/g" \
    -e "s/@CRX_NAME@/$CRX_NAME/g" \
    -e "s/@CRX_VERSION@/$CRX_VERSION/g" \
    debian/control.in > debian/control

# Optionally generate debian/copyright from copyright.in
# (Add appropriate sed substitutions for copyright years, author, license)
# sed ... debian/copyright.in > debian/copyright

# Now build the package
dpkg-buildpackage -us -uc -b
