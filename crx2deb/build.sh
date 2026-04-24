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

python3 debian/scripts/crx_reader.py --xml tmp/$CRX_NAME.crx > tmp/$(basename $CRX_NAME).xml
sed -i "s|$UPDATECHECK_TEMPLATE|file:///$EXTENSION_DIR/$CRX_NAME.crx|" tmp/$(basename $CRX_NAME).xml

echo "Extension: $CRX_NAME ($CRX_ID) version $CRX_VERSION"

# Export for j2
export crx_name="$CRX_NAME"
export crx_version="$CRX_VERSION"
export crx_id="$CRX_ID"
export extension_prefix="$EXTENSION_PREFIX"
export extension_dir="$EXTENSION_DIR"
export policies_file="$POLICIES_FILE"
export maintainer_name="$MAINTAINER_NAME"
export maintainer_email="$MAINTAINER_EMAIL"
export build_date="$BUILD_DATE"

j2 --import-env= debian/changelog.j2 > debian/changelog
j2 --import-env= debian/control.j2 > debian/control
j2 --import-env= debian/postinst.j2 > debian/postinst
j2 --import-env= debian/postrm.j2 > debian/postrm
