#!/bin/bash
set -e

EXTENSION_PREFIX="chromium-extension"
POLICIES_FILE="/etc/opt/chrome/policies/managed/extension_policy.json"
EXTENSION_DIR="usr/share/chromium/extensions"
MAINTAINER_NAME="Your Name"
MAINTAINER_EMAIL="your.email@example.com"
UPDATECHECK_TEMPLATE="https://clients2.google.com/service/update2/crx"

# Locate and decode CRX
SRC_FILE=$(find src -maxdepth 1 -type f ! -name ".*" | head -1)
if [ -z "$SRC_FILE" ]; then
    echo "Error: No file found in src/"
    exit 1
fi

mkdir -p tmp
CRX_FILE=$(basename "$SRC_FILE" .base64)
base64 -d "$SRC_FILE" > tmp/$CRX_FILE

# Extract metadata
CRX_NAME=$(python3 debian/scripts/crx_reader.py --name --sanitize tmp/$CRX_FILE)
CRX_ID=$(python3 debian/scripts/crx_reader.py --id tmp/$CRX_FILE)
CRX_VERSION=$(python3 debian/scripts/crx_reader.py --version tmp/$CRX_FILE)

mv tmp/$CRX_FILE tmp/$CRX_NAME.crx

python3 debian/scripts/crx_reader.py --xml tmp/$CRX_FILE > tmp/$(basename $CRX_NAME).xml
sed -i "s|$UPDATECHECK_TEMPLATE|file:///$EXTENSION_DIR/$CRX_FILE|" tmp/$(basename $CRX_NAME).xml

echo "Extension: $CRX_NAME ($CRX_ID) version $CRX_VERSION"

cat > debian/vars.mk <<EOF
EXTENSION_PREFIX = $EXTENSION_PREFIX
EXTENSION_DIR = $EXTENSION_DIR
POLICIES_FILE = $POLICIES_FILE
CRX_NAME = $CRX_NAME
CRX_ID = $CRX_ID
CRX_VERSION = $CRX_VERSION
MAINTAINER_NAME = ${MAINTAINER_NAME:-Your Name}
MAINTAINER_EMAIL = ${MAINTAINER_EMAIL:-your.email@example.com}
EOF

# Generate debian/changelog from template
sed -e "s/@PACKAGE@/$CRX_NAME/g" \
    -e "s/@VERSION@/$CRX_VERSION/g" \
    -e "s/@CRX_NAME@/$CRX_NAME/g" \
    -e "s/@CRX_ID@/$CRX_ID/g" \
    -e "s/@EXTENSION_PREFIX@/$EXTENSION_PREFIX/g" \
    -e "s/@MAINTAINER_NAME@/${MAINTAINER_NAME:-Your Name}/g" \
    -e "s/@MAINTAINER_EMAIL@/${MAINTAINER_EMAIL:-your.email@example.com}/g" \
    -e "s/@BUILD_DATE@/$(date -R)/g" \
    debian/changelog.in > debian/changelog

# Generate debian/control from control.in
sed -e "s/@CRX_NAME@/$CRX_NAME/g" \
    -e "s/@CRX_VERSION@/$CRX_VERSION/g" \
    -e "s/@EXTENSION_PREFIX@/$EXTENSION_PREFIX/g" \
    -e "s/@MAINTAINER_NAME@/${MAINTAINER_NAME:-Your Name}/g" \
    -e "s/@MAINTAINER_EMAIL@/${MAINTAINER_EMAIL:-your.email@example.com}/g" \
    debian/control.in > debian/control


