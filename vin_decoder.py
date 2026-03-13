import base64
import sys

KEY = "g2memberutil97534"


def decode_encrypted_vin(encrypted_vin: str, key: str = KEY) -> str:
    encrypted_bytes = base64.b64decode(encrypted_vin)

    vin_chars = []
    for i, b in enumerate(encrypted_bytes):
        vin_chars.append(chr(b ^ ord(key[i])))

    return "".join(vin_chars)


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
