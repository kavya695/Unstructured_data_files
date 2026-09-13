"""Email -> list[str].

Supports:
  .eml  - standard RFC 822 format (stdlib `email` module, no extra install)
  .msg  - Outlook binary format (needs the `extract-msg` package)

Headers are emitted as their own 'page' in "Label: Value" form on purpose —
that means Subject/From/To/Date fall straight into schema_infer.py's
existing regex with zero extra code. Body text is a separate page.
"""
import email
from email import policy
from email.parser import BytesParser


def _body_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_content()
        # fall back to HTML stripped of tags if no plain-text part exists
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                import re
                return re.sub(r"<[^>]+>", " ", part.get_content())
        return ""
    return msg.get_content()


def extract_eml(path: str) -> list[str]:
    with open(path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    header_lines = [
        f"Subject: {msg.get('Subject', '')}",
        f"From: {msg.get('From', '')}",
        f"To: {msg.get('To', '')}",
        f"Date: {msg.get('Date', '')}",
        f"Cc: {msg.get('Cc', '')}",
    ]
    pages = ["\n".join(header_lines)]

    body = _body_text(msg)
    if body.strip():
        pages.append(body)

    attachments = [part.get_filename() for part in msg.iter_attachments() if part.get_filename()]
    if attachments:
        pages.append("Attachments: " + ", ".join(attachments))

    return pages


def extract_msg(path: str) -> list[str]:
    import extract_msg  # only needed for .msg files

    m = extract_msg.Message(path)
    header_lines = [
        f"Subject: {m.subject or ''}",
        f"From: {m.sender or ''}",
        f"To: {m.to or ''}",
        f"Date: {m.date or ''}",
        f"Cc: {m.cc or ''}",
    ]
    pages = ["\n".join(header_lines)]
    if m.body and m.body.strip():
        pages.append(m.body)
    if m.attachments:
        names = [a.longFilename or a.shortFilename for a in m.attachments]
        pages.append("Attachments: " + ", ".join(n for n in names if n))
    m.close()
    return pages
