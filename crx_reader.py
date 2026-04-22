import struct
import json
import hashlib
import argparse
import sys
import zipfile
import tempfile
from pathlib import Path

# Protobuf message definitions (replicated from crx3_pb2.py)
from google.protobuf import descriptor_pool, message_factory

_pb2_serialized = b'\n\ncrx3.proto\x12\x08crx_file\"\xb7\x01\n\rCrxFileHeader\x12\x35\n\x0fsha256_with_rsa\x18\x02 \x03(\x0b2\x1c.crx_file.AsymmetricKeyProof\x12\x37\n\x11sha256_with_ecdsa\x18\x03 \x03(\x0b2\x1c.crx_file.AsymmetricKeyProof\x12\x19\n\x11verified_contents\x18\x04 \x01(\x0c\x12\x1b\n\x12signed_header_data\x18\x90N \x01(\x0c\";\n\x12AsymmetricKeyProof\x12\x12\n\npublic_key\x18\x01 \x01(\x0c\x12\x11\n\tsignature\x18\x02 \x01(\x0c\"\x1c\n\nSignedData\x12\x0e\n\x06crx_id\x18\x01 \x01(\x0cB\x02H\x03'

pool = descriptor_pool.DescriptorPool()
pool.AddSerializedFile(_pb2_serialized)
CrxFileHeader = message_factory.MessageFactory(pool).GetPrototype(pool.FindMessageTypeByName('crx_file.CrxFileHeader'))


def read_crx_v3(filepath):
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
        
        if not crx_header.sha256_with_rsa:
            raise ValueError("No RSA proof found in CRX header")
        public_key = crx_header.sha256_with_rsa[0].public_key
        
        extension_id = calculate_extension_id(public_key)
        
        zip_data = f.read()
        manifest = extract_manifest(zip_data)
        
        if not manifest:
            raise ValueError("Could not find manifest.json")
        
        name = manifest.get('name', 'Unknown')
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
    
    mapping = {**{str(i): chr(ord('a') + i) for i in range(10)},
               **{chr(ord('a') + i): chr(ord('a') + 10 + i) for i in range(6)}}
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
    
    args = parser.parse_args()
    
    crx_path = Path(args.crx_file)
    if not crx_path.exists():
        print(f"Error: File '{crx_path}' not found.", file=sys.stderr)
        sys.exit(1)
    
    try:
        info = read_crx_v3(crx_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Check if any output flags are used
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
            json_out = json.dumps({k: v for k, v in info.items() if k != 'xml'}, indent=2, ensure_ascii=False)
            lines.append(json_out)
        if lines:
            print('\n'.join(lines))
        sys.exit(0)
    
    # Default behavior: full output + save files
    print(f"Reading: {crx_path}\n")
    print(f"Extension ID: {info['extension_id']}")
    print(f"Extension Name: {info['name']}")
    print(f"Version: {info['version']}")
    print(f"\nXML:\n{info['xml']}")
    
   
if __name__ == "__main__":
    main()
