"""Repo ichida ochiq sir (hardcoded secret) va commit qilingan .env yo'qligini tekshiradi.

SEC-001 regressiya testi. Bu test muammo tuzatilgunga qadar YIQILADI.
"""
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kod ichida uchraydigan sir naqshlari (maskalangan, qiymat saqlanmaydi)
SECRET_PATTERNS = [
    r"""(?i)api[_-]?key['"]\s*[:=]\s*['"][A-Za-z0-9]{20,}['"]""",
    r"""(?i)secret['"]\s*[:=]\s*['"][A-Za-z0-9]{20,}['"]""",
    r"""\b\d{8,10}:[A-Za-z0-9_-]{30,}\b""",          # Telegram bot token
    r"""\bAKIA[0-9A-Z]{16}\b""",                       # AWS access key
    r"""\bsk-[A-Za-z0-9]{20,}\b""",                    # OpenAI-style key
    r"""\bgsk_[A-Za-z0-9]{20,}\b""",                   # Groq key
    r"""\bAIza[0-9A-Za-z_\-]{30,}\b""",                # Google API key
]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "tests"}
SCAN_EXT = {".py", ".js", ".ts", ".env", ".yml", ".yaml", ".toml", ".json"}


def iter_files():
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in SCAN_EXT or name == ".env":
                yield os.path.join(root, name)


class NoExposedSecretsTest(unittest.TestCase):
    def test_no_env_file_tracked(self):
        """`.env` repoda mavjud bo'lmasligi kerak (faqat `.env.example`)."""
        env_path = os.path.join(REPO_ROOT, ".env")
        self.assertFalse(
            os.path.exists(env_path),
            ".env fayli repoda mavjud — uni olib tashlang, faqat .env.example qoldiring",
        )

    def test_no_hardcoded_secrets_in_source(self):
        """Kod fayllarida hardcoded sir bo'lmasligi kerak."""
        findings = []
        for path in iter_files():
            if os.path.basename(path) == ".env.example":
                continue
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except OSError:
                continue
            for pattern in SECRET_PATTERNS:
                for match in re.finditer(pattern, text):
                    line_no = text[: match.start()].count("\n") + 1
                    rel = os.path.relpath(path, REPO_ROOT)
                    findings.append(f"{rel}:{line_no} [{match.group(0)[:10]}...]")
        self.assertEqual(
            findings, [],
            "Hardcoded sirlar topildi:\n" + "\n".join(findings),
        )


if __name__ == "__main__":
    unittest.main()
