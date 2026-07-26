#!/bin/sh
# Quill installer — https://github.com/tannnnnnnnnnnnn/Quill
#
#   curl -fsSL https://tannnnnnnnnnnnn.github.io/Quill/install.sh | sh
#
# Installs the pipeline into ~/.local/share/quill and a `meet` command into
# ~/.local/bin. Downloads the prebuilt recorder rather than building it, so
# Xcode is not required.
#
# On the recorder binary: it is signed ad hoc, not with an Apple Developer
# certificate, because this project does not have one. That is survivable here
# only because curl does not set the quarantine attribute a browser download
# would — Gatekeeper therefore never blocks it. Downloading the same file in a
# browser and double-clicking it WOULD be blocked, which is why this script
# exists. The tarball is checked against the SHA-256 published beside it; both
# come from the same GitHub release, so that is an integrity check against a
# corrupted download, not a defence against a compromised release.

set -eu

REPO="tannnnnnnnnnnnn/Quill"
PREFIX="${QUILL_PREFIX:-$HOME/.local/share/quill}"
BIN_DIR="${QUILL_BIN_DIR:-$HOME/.local/bin}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }
die() { printf '\nerror: %s\n' "$*" >&2; exit 1; }

# --- 1. this only works on one kind of machine -----------------------------
[ "$(uname -s)" = "Darwin" ] || die "Quill is macOS only (found $(uname -s))."
[ "$(uname -m)" = "arm64" ] || die "Quill needs Apple silicon — transcription runs on MLX."
case "$(sw_vers -productVersion)" in
  # major version only; 14.0-14.3 slip through and fail later at the tap
  1[0-3].*|[1-9].*) die "Quill needs macOS 14.4 or newer (found $(sw_vers -productVersion))." ;;
esac

say "Installing Quill into $PREFIX"

# --- 2. uv ------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  say "  installing uv (Python toolchain)"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
[ -x "$UV" ] || die "uv installed but not found on PATH — open a new terminal and re-run."

# --- 3. the release ---------------------------------------------------------
VERSION="${QUILL_VERSION:-$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | sed -n 's/.*"tag_name" *: *"\([^"]*\)".*/\1/p' | head -1)}"
[ -n "$VERSION" ] || die "no published release found for $REPO."
say "  version $VERSION"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "  downloading source"
curl -fsSL "https://github.com/$REPO/archive/refs/tags/$VERSION.tar.gz" -o "$TMP/src.tar.gz" \
  || die "could not download the source tarball for $VERSION."

say "  downloading recorder"
BASE="https://github.com/$REPO/releases/download/$VERSION"
curl -fsSL "$BASE/Audiocap.app.tar.gz" -o "$TMP/app.tar.gz" \
  || die "could not download the recorder for $VERSION."
if curl -fsSL "$BASE/Audiocap.app.tar.gz.sha256" -o "$TMP/app.sha256" 2>/dev/null; then
  EXPECT="$(cut -d' ' -f1 < "$TMP/app.sha256")"
  ACTUAL="$(shasum -a 256 "$TMP/app.tar.gz" | cut -d' ' -f1)"
  [ "$EXPECT" = "$ACTUAL" ] || die "recorder checksum mismatch — refusing to install.
  expected $EXPECT
  got      $ACTUAL"
else
  die "no checksum published for the recorder — refusing to install an unverified binary."
fi

# --- 4. lay it down ---------------------------------------------------------
mkdir -p "$PREFIX" "$BIN_DIR"
rm -rf "$PREFIX.old"
# keep the previous install until this one is on its feet (`set -e`: no && chain)
if [ -d "$PREFIX/quill" ]; then
  mv "$PREFIX" "$PREFIX.old"
  mkdir -p "$PREFIX"
fi
tar -xzf "$TMP/src.tar.gz" -C "$TMP"
cp -R "$TMP"/Quill-*/. "$PREFIX/"
mkdir -p "$PREFIX/bin"
tar -xzf "$TMP/app.tar.gz" -C "$PREFIX/bin"
[ -x "$PREFIX/bin/Audiocap.app/Contents/MacOS/audiocap" ] \
  || die "the recorder did not unpack correctly."

say "  installing Python dependencies (a few minutes, ~1 GB)"
(cd "$PREFIX" && "$UV" sync --quiet) || die "uv sync failed in $PREFIX."

cat > "$BIN_DIR/meet" <<EOF
#!/bin/sh
exec "$UV" run --project "$PREFIX" meet "\$@"
EOF
chmod +x "$BIN_DIR/meet"
rm -rf "$PREFIX.old"

# --- 5. hand over -----------------------------------------------------------
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "
Add this to your shell profile, then open a new terminal:
  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# `meet init` asks questions, but piping this script into sh means stdin is the
# script. Borrow the terminal — and check by opening it, not by testing that it
# exists, because /dev/tty is present but unusable under cron, CI and some
# sandboxes. Never fail the install over this; the two commands are printable.
if (exec < /dev/tty) 2>/dev/null; then
  say "
Setup — where your notes and recordings go:"
  if "$BIN_DIR/meet" init < /dev/tty; then
    say "
Checking that recording actually works:"
    "$BIN_DIR/meet" doctor < /dev/tty || true
  else
    say "
Setup did not finish. Run it yourself:
  meet init
  meet doctor"
  fi
else
  say "
Installed. Finish with:
  meet init
  meet doctor"
fi

say "
Quill is installed. Next:
  1. Add the Chrome extension:  https://github.com/$REPO#browser-extension
  2. Claude Code must be installed and signed in — it writes the notes.
  3. Start the menu bar app:    meet menubar"
