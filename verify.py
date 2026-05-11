import sys
import json
import socket
import smtplib
import dns.resolver
import argparse
import time
import random

FROM_ADDRESS = "verify@checker.local"
HELO_DOMAIN  = "checker.local"
TIMEOUT      = 10  # seconds per connection


def get_mx_records(domain: str) -> list[str]:
    """Return MX hostnames sorted by priority (lowest = highest priority)."""
    try:
        records = dns.resolver.resolve(domain, "MX")
        sorted_mx = sorted(records, key=lambda r: r.preference)
        return [str(r.exchange).rstrip(".") for r in sorted_mx]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
        # Try A record fallback
        try:
            dns.resolver.resolve(domain, "A")
            return [domain]
        except Exception:
            return []
    except Exception:
        return []


def smtp_check(email: str, mx_hosts: list[str]) -> dict:
    """
    Perform SMTP handshake up to RCPT TO.
    Returns dict with keys: deliverable (bool|None), code (int), message (str), mx_used (str)
    """
    last_error = None

    for mx in mx_hosts[:3]:  # Try top 3 MX records
        try:
            with smtplib.SMTP(timeout=TIMEOUT) as smtp:
                smtp.connect(mx, 25)
                smtp.helo(HELO_DOMAIN)
                smtp.mail(FROM_ADDRESS)
                code, message = smtp.rcpt(email)
                smtp.rset()  # politely reset instead of just dropping
                smtp.quit()

                msg = message.decode("utf-8", errors="replace") if isinstance(message, bytes) else message

                if code == 250:
                    return {"deliverable": True,  "code": code, "message": msg, "mx_used": mx}
                elif code == 251:
                    return {"deliverable": True,  "code": code, "message": msg, "mx_used": mx}
                elif 500 <= code <= 599:
                    return {"deliverable": False, "code": code, "message": msg, "mx_used": mx}
                elif 400 <= code <= 499:
                    # Greylisting / temporary failure — inconclusive
                    last_error = {"deliverable": None, "code": code, "message": msg, "mx_used": mx}
                else:
                    last_error = {"deliverable": None, "code": code, "message": msg, "mx_used": mx}

        except smtplib.SMTPConnectError as e:
            last_error = {"deliverable": None, "code": -1, "message": f"Connect error: {e}", "mx_used": mx}
        except smtplib.SMTPServerDisconnected as e:
            last_error = {"deliverable": None, "code": -2, "message": f"Server disconnected: {e}", "mx_used": mx}
        except smtplib.SMTPRecipientsRefused as e:
            # Explicitly refused — invalid
            refused = list(e.recipients.values())
            code, msg = (refused[0][0], refused[0][1].decode("utf-8", errors="replace")) if refused else (550, "Refused")
            return {"deliverable": False, "code": code, "message": msg, "mx_used": mx}
        except (socket.timeout, TimeoutError):
            last_error = {"deliverable": None, "code": -3, "message": "Connection timed out", "mx_used": mx}
        except OSError as e:
            # Port 25 blocked (common on cloud/CI runners)
            last_error = {"deliverable": None, "code": -4, "message": f"Network error (port 25 may be blocked): {e}", "mx_used": mx}
        except Exception as e:
            last_error = {"deliverable": None, "code": -99, "message": str(e), "mx_used": mx}

        # Small delay between MX attempts
        time.sleep(0.5)

    return last_error or {"deliverable": None, "code": -5, "message": "No MX servers reachable", "mx_used": ""}


def verify_email(email: str) -> dict:
    email = email.strip().lower()
    result = {
        "email":       email,
        "deliverable": None,
        "smtp_code":   None,
        "smtp_message": "",
        "mx_used":     "",
        "error":       None
    }

    if "@" not in email:
        result["error"] = "Invalid format"
        result["deliverable"] = False
        return result

    domain = email.split("@")[1]
    mx_hosts = get_mx_records(domain)

    if not mx_hosts:
        result["error"] = "No MX records found"
        result["deliverable"] = False
        return result

    smtp_result = smtp_check(email, mx_hosts)
    result["deliverable"]   = smtp_result["deliverable"]
    result["smtp_code"]     = smtp_result["code"]
    result["smtp_message"]  = smtp_result["message"]
    result["mx_used"]       = smtp_result["mx_used"]

    if smtp_result["code"] == -4:
        result["error"] = "port_blocked"

    return result


def main():
    parser = argparse.ArgumentParser(description="SMTP Email Verifier")
    parser.add_argument("emails", nargs="*", help="Email addresses to verify")
    parser.add_argument("--file", "-f", help="File with one email per line")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between verifications (seconds)")
    args = parser.parse_args()

    emails = list(args.emails)

    if args.file:
        with open(args.file) as f:
            emails += [line.strip() for line in f if line.strip()]

    if not emails:
        print(json.dumps({"error": "No emails provided"}))
        sys.exit(1)

    results = []
    for i, email in enumerate(emails):
        if i > 0:
            time.sleep(args.delay + random.uniform(0, 0.2))
        res = verify_email(email)
        results.append(res)
        # Stream progress to stderr so GitHub Actions logs show it
        status = "✅" if res["deliverable"] is True else "❌" if res["deliverable"] is False else "❓"
        print(f"{status}  {email}  →  code={res['smtp_code']}  {res['smtp_message'][:60]}", file=sys.stderr)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
