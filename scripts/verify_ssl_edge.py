#!/usr/bin/env python3
"""
Verification script for Orchestra Edge Proxy (SSL, HTTP, Security Headers, and HSTS scoping).
"""

import ssl
import sys
import socket
import urllib.request
import urllib.error
import http.client


def verify_http(host: str = "127.0.0.1", port: int = 8080) -> bool:
    print(f"\n[1/4] Verifying Plain HTTP on http://{host}:{port}/health ...")
    try:
        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "Orchestra-SSL-Verifier"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            print(f"  HTTP Status: {status}")
            hsts = resp.headers.get("Strict-Transport-Security")
            print(f"  HSTS header on HTTP: {hsts} (Expected: None)")
            if status == 200 and hsts is None:
                print("  PASS: Plain HTTP operational without HSTS pollution.")
                return True
            return False
    except Exception as e:
        print(f"  FAIL: HTTP request error: {e}")
        return False


def verify_https_handshake(host: str = "127.0.0.1", port: int = 8443) -> bool:
    print(f"\n[2/4] Verifying TLS Handshake on https://{host}:{port} ...")
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # Self-signed dev cert testing

        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname="localhost") as ssock:
                version = ssock.version()
                cipher = ssock.cipher()
                cert = ssock.getpeercert(binary_form=False)
                print(f"  TLS Protocol Version: {version}")
                print(f"  Cipher Suite: {cipher[0] if cipher else 'Unknown'}")
                if version in ("TLSv1.2", "TLSv1.3"):
                    print("  PASS: TLS 1.2/1.3 negotiated successfully.")
                    return True
                print("  FAIL: Unexpected TLS version.")
                return False
    except Exception as e:
        print(f"  FAIL: TLS handshake error: {e}")
        return False


def verify_https_security_headers(host: str = "127.0.0.1", port: int = 8443) -> bool:
    print(f"\n[3/4] Verifying Security Headers on https://{host}:{port}/health ...")
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        url = f"https://{host}:{port}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "Orchestra-SSL-Verifier"})
        with urllib.request.urlopen(req, context=context, timeout=5) as resp:
            headers = resp.headers
            print(f"  Status: {resp.status}")

            x_cto = headers.get("X-Content-Type-Options")
            x_fo = headers.get("X-Frame-Options")
            hsts = headers.get("Strict-Transport-Security")

            print(f"  X-Content-Type-Options: {x_cto} (Expected: nosniff)")
            print(f"  X-Frame-Options: {x_fo} (Expected: DENY)")
            print(f"  Strict-Transport-Security on localhost: {hsts} (Expected: None)")

            passed = (
                x_cto == "nosniff"
                and x_fo == "DENY"
                and (hsts is None or hsts == "")
            )
            if passed:
                print("  PASS: Security headers verified and HSTS correctly omitted for localhost.")
                return True
            else:
                print("  FAIL: Header assertion mismatch.")
                return False
    except Exception as e:
        print(f"  FAIL: HTTPS header check error: {e}")
        return False


def verify_https_api_routing(host: str = "127.0.0.1", port: int = 8443) -> bool:
    print(f"\n[4/4] Verifying End-to-End Reverse Proxy Routing via HTTPS ...")
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        url = f"https://{host}:{port}/health/ready"
        req = urllib.request.Request(url, headers={"User-Agent": "Orchestra-SSL-Verifier"})
        with urllib.request.urlopen(req, context=context, timeout=5) as resp:
            data = resp.read().decode()
            print(f"  Response: {data[:100]}")
            if resp.status == 200:
                print("  PASS: Backend probe reachable via HTTPS reverse proxy.")
                return True
            return False
    except Exception as e:
        print(f"  FAIL: HTTPS API routing error: {e}")
        return False


def main():
    h = verify_http()
    tls = verify_https_handshake()
    headers = verify_https_security_headers()
    api = verify_https_api_routing()

    if all([h, tls, headers, api]):
        print("\n=== ALL EDGE PROXY VERIFICATION CHECKS PASSED ===")
        sys.exit(0)
    else:
        print("\n=== EDGE PROXY VERIFICATION FAILED ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
