#!/usr/bin/env python3
"""
Extract mermaid code blocks from Markdown files and convert them to SVG images.

Requires: Node.js/npx + Chrome (auto-installed via --install)

Usage:
    # Environment setup (first time)
    python3 scripts/extract_mermaid.py --install

    # Environment check
    python3 scripts/extract_mermaid.py --check

    # Convert all *-overview*.md in default docs directory
    python3 scripts/extract_mermaid.py

    # Convert single file, output to default images/ directory
    python3 scripts/extract_mermaid.py docs/xxx.md

    # Convert single file, specify output directory
    python3 scripts/extract_mermaid.py docs/xxx.md my_svgs/

    # Scan all .md in a directory
    python3 scripts/extract_mermaid.py docs/implemented/

    # Scan directory, specify output
    python3 scripts/extract_mermaid.py docs/implemented/ my_svgs/
"""

import re
import os
import sys
import subprocess
import argparse

# Chrome binary path discovery
PUPPETEER_CACHE = os.environ.get(
    "PUPPETEER_CACHE_DIR",
    os.path.expanduser("~/.cache/puppeteer"),
)

DEFAULT_CHROME_PATH = None


def _discover_chrome() -> str | None:
    """Find Chrome binary in puppeteer cache directory."""
    global DEFAULT_CHROME_PATH
    if not os.path.exists(PUPPETEER_CACHE):
        return None
    for root, dirs, files in os.walk(PUPPETEER_CACHE):
        for f in files:
            if f == "chrome" and "chrome-linux64" in root:
                DEFAULT_CHROME_PATH = os.path.join(root, f)
                return DEFAULT_CHROME_PATH
    return None


_discover_chrome()

MMDC_PACKAGE = "@mermaid-js/mermaid-cli@11.4.2"
IMG_DIR = "images"


def slug(text: str) -> str:
    """Convert text to a file-name-safe slug."""
    text = text.lower().strip()
    # Keep Chinese characters, replace others with hyphens
    text = re.sub(r"[^\w\s一-鿿]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def find_mermaid_blocks(content: str):
    """Yield (mermaid_code, section_heading, index) tuples."""
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    for i, m in enumerate(pattern.finditer(content)):
        mermaid_code = m.group(1).strip()
        # Find the nearest section heading above this block
        before = content[: m.start()]
        headings = re.findall(r"^##+ (.+)$", before, re.MULTILINE)
        section = headings[-1] if headings else f"diagram_{i + 1}"
        yield mermaid_code, section, i


def convert_mermaid_to_svg(
    mermaid_code: str,
    output_path: str,
    chrome_path: str | None = None,
    background: str = "transparent",
    timeout: int = 30,
) -> bool:
    """Convert a mermaid code string to an SVG file."""

    # Write mermaid code to a temp .mmd file
    mmd_path = output_path + ".mmd"
    with open(mmd_path, "w") as f:
        f.write(mermaid_code)

    try:
        env = os.environ.copy()
        chrome = chrome_path or DEFAULT_CHROME_PATH
        if chrome:
            env["PUPPETEER_EXECUTABLE_PATH"] = chrome

        result = subprocess.run(
            [
                "npx", "--yes", MMDC_PACKAGE,
                "-i", mmd_path,
                "-o", output_path,
                "-b", background,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        if result.returncode != 0:
            print(f"  FAILED: {result.stderr.strip()[:200]}", file=sys.stderr)
            return False
        return True

    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(
            "  ERROR: npx not found. Install Node.js first.",
            file=sys.stderr,
        )
        return False
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(mmd_path):
            os.remove(mmd_path)


def process_file(
    md_path: str,
    output_dir: str,
    chrome_path: str | None = None,
) -> list[str]:
    """Process a single markdown file and return list of generated SVG paths."""
    md_path = os.path.abspath(md_path)
    if not os.path.isfile(md_path):
        print(f"File not found: {md_path}", file=sys.stderr)
        return []

    with open(md_path) as f:
        content = f.read()

    stem = os.path.basename(md_path).replace(".en.md", "").replace(".md", "")
    suffix = "-en" if md_path.endswith(".en.md") else ""

    generated = []
    for mermaid_code, section, idx in find_mermaid_blocks(content):
        section_slug = slug(section)
        img_name = f"{stem}{suffix}-{section_slug}.svg"
        img_path = os.path.join(output_dir, img_name)

        print(f"  [{idx + 1}] {section} → {img_name} ...", end=" ")
        sys.stdout.flush()

        if convert_mermaid_to_svg(mermaid_code, img_path, chrome_path):
            print("OK")
            generated.append(img_path)
        else:
            print("")

    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Extract mermaid diagrams from Markdown and convert to SVG."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help=(
            "Markdown file or directory to scan. "
            "Defaults to all *-overview*.md in docs/gns3-copilot/implemented/."
        ),
    )
    parser.add_argument(
        "dest",
        nargs="?",
        default=None,
        help="Output directory for SVGs (default: <source_dir>/images/).",
    )
    parser.add_argument(
        "--chrome",
        default=DEFAULT_CHROME_PATH,
        help=f"Path to Chrome binary (auto-detected: {DEFAULT_CHROME_PATH})",
    )
    parser.add_argument(
        "--background", "-b",
        default="transparent",
        help="SVG background color (default: transparent)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Timeout in seconds per diagram (default: 30)",
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check environment and exit (no conversion).",
    )
    parser.add_argument(
        "--install", "-i",
        action="store_true",
        help="Install missing dependencies (Chrome, mermaid-cli).",
    )

    args = parser.parse_args()

    # ── Environment install mode ──
    if args.install:
        print("=== Installing Dependencies ===\n")
        install_ok = True

        # 1. Check npx
        try:
            subprocess.run(["npx", "--version"], capture_output=True, timeout=10)
        except FileNotFoundError:
            print("  ERROR: Node.js/npx not found. Install Node.js first.")
            print("  Visit: https://nodejs.org/")
            sys.exit(1)

        # 2. Install Chrome via puppeteer
        chrome = args.chrome or DEFAULT_CHROME_PATH
        if chrome and os.path.exists(chrome):
            result = subprocess.run(
                [chrome, "--version"], capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            print(f"  Chrome: already installed ({version})")
        else:
            print("  Chrome: installing via puppeteer...")
            ret = subprocess.run(
                ["npx", "puppeteer", "browsers", "install", "chrome-headless-shell"],
                timeout=120,
            )
            if ret.returncode == 0:
                print("  Chrome: installed successfully")
                # Re-discover Chrome path
                _discover_chrome()
            else:
                print("  Chrome: installation failed")
                install_ok = False

        # 3. Pre-cache mermaid-cli
        print("  mermaid-cli: caching...")
        ret = subprocess.run(
            ["npx", "--yes", MMDC_PACKAGE, "--version"],
            capture_output=True, text=True, timeout=60,
        )
        if ret.returncode == 0:
            print("  mermaid-cli: ready")
        else:
            print("  mermaid-cli: download failed")
            install_ok = False

        print(f"\n  Result: {'✓ INSTALLATION COMPLETE' if install_ok else '✗ SOME INSTALLATIONS FAILED'}")

        # Auto-run check after install
        print()
        args.check = True
        # Fall through to check below (args.check is now True)

    # ── Environment check mode ──
    if args.check:
        ok = True

        print("=== Environment Check ===\n")

        # 1. Python
        print(f"  Python: {sys.version.split()[0]}")

        # 2. npx / Node.js
        try:
            result = subprocess.run(
                ["npx", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                print(f"  npx: {result.stdout.strip()}")
            else:
                print("  npx: NOT FOUND")
                ok = False
        except FileNotFoundError:
            print("  npx: NOT FOUND (Node.js not installed)")
            ok = False

        # 3. Chrome
        chrome = args.chrome or DEFAULT_CHROME_PATH
        if chrome and os.path.exists(chrome):
            try:
                result = subprocess.run(
                    [chrome, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                version = result.stdout.strip() if result.returncode == 0 else "?"
                print(f"  Chrome: {version}")
                print(f"    Path: {chrome}")
            except Exception:
                print(f"  Chrome: {chrome}")
        else:
            print("  Chrome: NOT FOUND")
            print("    Run: npx puppeteer browsers install chrome-headless-shell")
            ok = False

        # 4. @mermaid-js/mermaid-cli
        try:
            result = subprocess.run(
                ["npx", "--yes", MMDC_PACKAGE, "--version"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print("  mermaid-cli: available")
            else:
                print("  mermaid-cli: download failed")
                ok = False
        except Exception:
            print("  mermaid-cli: FAILED")
            ok = False

        # 5. Puppeteer cache
        if os.path.exists(PUPPETEER_CACHE):
            print(f"  Puppeteer cache: {PUPPETEER_CACHE}")
            for item in sorted(os.listdir(PUPPETEER_CACHE)):
                item_path = os.path.join(PUPPETEER_CACHE, item)
                if os.path.isdir(item_path):
                    versions = os.listdir(item_path)
                    print(f"    {item}: {', '.join(versions)}")
        else:
            print(f"  Puppeteer cache: NOT FOUND")

        print(f"\n  Result: {'✓ ALL CHECKS PASSED' if ok else '✗ SOME CHECKS FAILED'}")
        sys.exit(0 if ok else 1)

    args = parser.parse_args()

    # Determine source files
    files_to_process = []
    if args.source:
        if os.path.isfile(args.source):
            files_to_process.append(args.source)
        elif os.path.isdir(args.source):
            for f in sorted(os.listdir(args.source)):
                if f.endswith(".md"):
                    files_to_process.append(os.path.join(args.source, f))
        else:
            print(f"Source not found: {args.source}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: scan project docs directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        docs_dir = os.path.join(project_root, "docs", "gns3-copilot", "implemented")
        if os.path.isdir(docs_dir):
            files_to_process = sorted(
                os.path.join(docs_dir, f)
                for f in os.listdir(docs_dir)
                if "-overview" in f and f.endswith(".md")
            )
        else:
            print("No source specified and default docs directory not found.",
                  file=sys.stderr)
            sys.exit(1)

    if not files_to_process:
        print("No markdown files found.", file=sys.stderr)
        sys.exit(1)

    # Determine output directory
    if args.dest:
        output_base = args.dest
    elif args.source and os.path.isfile(args.source):
        output_base = os.path.join(os.path.dirname(args.source), IMG_DIR)
    elif args.source and os.path.isdir(args.source):
        output_base = os.path.join(args.source, IMG_DIR)
    else:
        # Default: use directory of first file
        output_base = os.path.join(os.path.dirname(files_to_process[0]), IMG_DIR)

    os.makedirs(output_base, exist_ok=True)

    # Chrome check
    chrome = args.chrome or DEFAULT_CHROME_PATH
    if not chrome:
        print(
            "WARNING: Chrome not found in puppeteer cache. "
            "Run: npx puppeteer browsers install chrome-headless-shell",
            file=sys.stderr,
        )
    else:
        print(f"Using Chrome: {chrome}")
        print(f"Output: {output_base}")

    print(f"\nProcessing {len(files_to_process)} file(s)...\n")

    total_svgs = 0
    for md_path in files_to_process:
        rel = os.path.relpath(md_path)
        print(f"== {rel} ==")

        svgs = process_file(md_path, output_base, chrome)
        total_svgs += len(svgs)
        print()

    print(f"Done. Generated {total_svgs} SVG(s).")


if __name__ == "__main__":
    main()
