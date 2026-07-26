APP = bin/Audiocap.app

EXT_VERSION = $(shell python3 -c "import json;print(json.load(open('extension/manifest.json'))['version'])")

.PHONY: build setup test extension-zip clean

build:
	mkdir -p $(APP)/Contents/MacOS
	swiftc -O -o $(APP)/Contents/MacOS/audiocap capture/audiocap.swift
	cp capture/Info.plist $(APP)/Contents/Info.plist
	codesign --force --sign - --identifier com.tanmay.audiocap $(APP)
	@echo "built $(APP)"

setup:
	uv sync
	$(MAKE) build

test:
	uv run python -m unittest discover -s tests
	node --test extension/tests/*.test.mjs

# Upload package for the Chrome Web Store. Excludes tests and the dev harness.
extension-zip:
	mkdir -p dist
	rm -f dist/quill-extension-$(EXT_VERSION).zip
	cd extension && zip -qr ../dist/quill-extension-$(EXT_VERSION).zip . \
		-x "tests/*" "harness/*" "STORE_LISTING.md" ".*"
	@echo "built dist/quill-extension-$(EXT_VERSION).zip"

clean:
	rm -rf bin .venv dist
