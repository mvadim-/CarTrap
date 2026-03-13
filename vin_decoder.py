from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent / "backend" / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cartrap.modules.copart_provider.vin import decode_encrypted_vin


def main():
    if len(sys.argv) < 2:
        print("Usage: python vin_decoder.py <encryptedVIN>")
        sys.exit(1)

    encrypted_vin = sys.argv[1]

    try:
        vin = decode_encrypted_vin(encrypted_vin)
        print(vin)
    except Exception as e:
        print("Error decoding VIN:", e)


if __name__ == "__main__":
    main()
