APP = bin/Audiocap.app

.PHONY: build setup clean

build:
	mkdir -p $(APP)/Contents/MacOS
	swiftc -O -o $(APP)/Contents/MacOS/audiocap capture/audiocap.swift
	cp capture/Info.plist $(APP)/Contents/Info.plist
	codesign --force --sign - --identifier com.tanmay.audiocap $(APP)
	@echo "built $(APP)"

setup:
	uv sync
	$(MAKE) build

clean:
	rm -rf bin .venv
