import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def urlsafe_b64encode(data: bytes) -> str:
    # URL-safe base64 encoding without padding
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def generate_vapid_keys():
    # Generate SECP256R1 (NIST P-256) elliptic curve private key
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Get the private key bytes (raw private scalar, 32 bytes)
    private_value = private_key.private_numbers().private_value
    private_bytes = private_value.to_bytes(32, byteorder='big')
    
    # Get the public key in uncompressed point format (65 bytes: 0x04 prefix + 32-byte X + 32-byte Y)
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    # Encode both to URL-safe base64
    private_key_b64 = urlsafe_b64encode(private_bytes)
    public_key_b64 = urlsafe_b64encode(public_bytes)
    
    return public_key_b64, private_key_b64

def main():
    try:
        public_key_b64, private_key_b64 = generate_vapid_keys()
        print("VAPID Keys generated successfully!\n")
        print(f"VAPID_PUBLIC_KEY={public_key_b64}")
        print(f"VAPID_PRIVATE_KEY={private_key_b64}")
        print("\nYou can add these to your .env file.")
    except Exception as e:
        print(f"Error generating VAPID keys: {e}")

if __name__ == "__main__":
    main()
