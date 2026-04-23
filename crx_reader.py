import struct
import json
import hashlib
import argparse
import sys
import zipfile
import tempfile
from pathlib import Path
import re
from unidecode import unidecode

# Protobuf message definitions (replicated from crx3_pb2.py)
from google.protobuf import descriptor_pool, message_factory

_pb2_serialized = (
    b'\n'
    b'\ncrx3.proto\x12\x08crx_file"\xb7\x01\n'
    b'\rCrxFileHeader\x125\n'
    b'\x0fsha256_with_rsa\x18\x02 \x03(\x0b2\x1c.crx_file.AsymmetricKeyProof\x127\n'
    b'\x11sha256_with_ecdsa\x18\x03 \x03(\x0b2\x1c.crx_file.AsymmetricKeyProof\x12\x19\n'
    b'\x11verified_contents\x18\x04 \x01(\x0c\x12\x1b\n'
    b'\x12signed_header_data\x18\x90N \x01(\x0c";\n'
    b'\x12AsymmetricKeyProof\x12\x12\n'
    b'\npublic_key\x18\x01 \x01(\x0c\x12\x11\n'
    b'\tsignature\x18\x02 \x01(\x0c"\x1c\n'
    b'\nSignedData\x12\x0e\n'
    b'\x06crx_id\x18\x01 \x01(\x0cB\x02H\x03'
)

pool = descriptor_pool.DescriptorPool()
pool.AddSerializedFile(_pb2_serialized)
CrxFileHeader = message_factory.MessageFactory(pool).GetPrototype(
    pool.FindMessageTypeByName('crx_file.CrxFileHeader')
)
SignedData = message_factory.MessageFactory(pool).GetPrototype(
    pool.FindMessageTypeByName('crx_file.SignedData')
)

def sanitize_debian_package_name(name):
    name = unidecode(str(name).lower())
    name = re.sub(r'[^a-z0-9+\-.]+', '-', name.replace(' ', '-').replace('_', '-'))
    name = re.sub(r'[-.]+', '-', name).strip('-')
    if not name or not name[0].isalnum():
        name = 'pkg-' + name.lstrip('-')
    if not name:
        name = 'unknown-package'
    return name[:64].rstrip('-.')

def read_crx_v3(filepath, sanitize = False):
    """Read CRX v3 file and extract extension info."""
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'Cr24':
            raise ValueError("Not a valid CRX file")

        version = struct.unpack('<I', f.read(4))[0]
        if version != 3:
            raise ValueError(f"Expected CRX v3, got v{version}")

        header_size = struct.unpack('<I', f.read(4))[0]
        header_bytes = f.read(header_size)

        crx_header = CrxFileHeader()
        crx_header.ParseFromString(header_bytes)

        # Parse SignedData to get the expected crx_id
        signed_data = SignedData()
        signed_data.ParseFromString(crx_header.signed_header_data)
        expected_crx_id_bytes = signed_data.crx_id

        if not crx_header.sha256_with_rsa:
            raise ValueError("No RSA proof found in CRX header")

        # Find the proof whose public key produces the expected crx_id
        public_key = None
        for proof in crx_header.sha256_with_rsa:
            derived_id_bytes = hashlib.sha256(proof.public_key).digest()[:16]
            if derived_id_bytes == expected_crx_id_bytes:
                public_key = proof.public_key
                break

        if public_key is None:
            raise ValueError("No RSA proof matches the declared crx_id")

        # Calculate extension ID string
        extension_id = calculate_extension_id(public_key)

        zip_data = f.read()
        manifest = extract_manifest(zip_data)

        if not manifest:
            raise ValueError("Could not find manifest.json")

        name = manifest.get('name', 'Unknown')
        if sanitize: name = sanitize_debian_package_name(name)
        version_str = manifest.get('version', 'Unknown')

        return {
            'extension_id': extension_id,
            'name': name,
            'version': version_str,
            'xml': generate_xml(extension_id, name, version_str)
        }


def calculate_extension_id(public_key):
    sha256_hash = hashlib.sha256(public_key).digest()
    truncated_hash = sha256_hash[:16]
    hex_str = truncated_hash.hex()

    mapping = {
        **{str(i): chr(ord('a') + i) for i in range(10)},
        **{chr(ord('a') + i): chr(ord('a') + 10 + i) for i in range(6)}
    }
    return ''.join(mapping[ch] for ch in hex_str)


def extract_manifest(zip_data):
    if not zip_data.startswith(b'PK\x03\x04'):
        return None

    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        tmp.write(zip_data)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            if 'manifest.json' in zf.namelist():
                return json.loads(zf.read('manifest.json').decode('utf-8'))
    finally:
        Path(tmp_path).unlink()
    return None


def generate_xml(extension_id, name, version):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
    <app appid="{extension_id}">
        <updatecheck codebase="https://clients2.google.com/service/update2/crx"
                     version="{version}"/>
        <manifest version="{version}">
            <package name="{name}.crx" hash_sha256="" required_version="{version}"/>
        </manifest>
    </app>
</gupdate>'''


def main():
    parser = argparse.ArgumentParser(description='Extract info from a CRX v3 file.')
    parser.add_argument('crx_file', help='Path to the .crx file.')
    parser.add_argument('--id', action='store_true', help='Output extension ID only')
    parser.add_argument('--version', action='store_true', help='Output version only')
    parser.add_argument('--name', action='store_true', help='Output extension name only')
    parser.add_argument('--xml', action='store_true', help='Output XML update manifest only')
    parser.add_argument('--json', action='store_true', help='Output JSON object with all fields')
    parser.add_argument('--sanitize', action='store_true', help='Sanitize package name')

    args = parser.parse_args()

    crx_path = Path(args.crx_file)
    if not crx_path.exists():
        print(f"Error: File '{crx_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        info = read_crx_v3(crx_path, args.sanitize)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    output_flags = [args.id, args.version, args.name, args.xml, args.json]
    if any(output_flags):
        lines = []
        if args.id:
            lines.append(info['extension_id'])
        if args.version:
            lines.append(info['version'])
        if args.name:
            lines.append(info['name'])
        if args.xml:
            lines.append(info['xml'])
        if args.json:
            json_out = json.dumps(
                {k: v for k, v in info.items() if k != 'xml'},
                indent=2, ensure_ascii=False
            )
            lines.append(json_out)
        if lines:
            print('\n'.join(lines))
        sys.exit(0)

    print(f"Reading: {crx_path}\n")
    print(f"Extension ID: {info['extension_id']}")
    print(f"Extension Name: {info['name']}")
    print(f"Version: {info['version']}")
    print(f"\nXML:\n{info['xml']}")


if __name__ == "__main__":
    main()
