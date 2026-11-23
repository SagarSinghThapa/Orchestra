#!/usr/bin/env python3
"""
Development Self-Signed Certificate Generator for Orchestra.
Generates a local 2048-bit RSA certificate and key for local HTTPS testing.
STRICTLY FOR LOCAL DEVELOPMENT AND TESTING.
DO NOT USE IN PRODUCTION.
"""

import os
import sys
import datetime
import ipaddress
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


def generate_dev_certificate(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_path = output_dir / "orchestra_dev.crt"
    key_path = output_dir / "orchestra_dev.key"

    print(f"Generating 2048-bit RSA private key...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Localhost"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Orchestra Local Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
    )

    certificate = cert_builder.sign(
        private_key=private_key,
        algorithm=hashes.SHA256(),
    )

    # Write private key
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(certificate.public_bytes(serialization.Encoding.PEM))

    print(f"Development certificate generated: {cert_path}")
    print(f"Development private key generated: {key_path}")
    return cert_path, key_path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    target_dir = repo_root / "nginx" / "certs"
    generate_dev_certificate(target_dir)
