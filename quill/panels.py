"""Floating AppKit panels, implementing the Claude Design "Classic" handoff
(design/claude-design/design_handoff_quill_call_ui/README.md): light paper
surfaces, ink text, one blue accent, the Quill mark throughout.
Everything here must run on the main thread."""

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSImage,
    NSImageView,
    NSMakeRect,
    NSObject,
    NSPanel,
    NSScreen,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSMutableParagraphStyle,
    NSParagraphStyleAttributeName,
)
from Foundation import NSMakeRange, NSAttributedString, NSMutableAttributedString

from . import config

# ---------- design tokens (README "Design Tokens") ----------

def _rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)

INK = _rgb(0x1C, 0x1C, 0x1C)
PAPER = _rgb(0xF4, 0xF2, 0xED)
SECONDARY = _rgb(0x6B, 0x6B, 0x66)
TERTIARY = _rgb(0x9A, 0x97, 0x8F)
ACCENT = _rgb(0x4B, 0x7B, 0xEC)
ME_BLUE = _rgb(0x7D, 0xB8, 0xFF)
THEM_AMBER = _rgb(0xFF, 0xC4, 0x6B)
GHOST = _rgb(0x1C, 0x1C, 0x1C, 0.05)
HAIRLINE = _rgb(0x1C, 0x1C, 0x1C, 0.07)
NOTE_SLOT = _rgb(0x4B, 0x7B, 0xEC, 0.10)

MARGIN = 20
_STYLE = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
_BEHAVIOR = (NSWindowCollectionBehaviorCanJoinAllSpaces
             | NSWindowCollectionBehaviorFullScreenAuxiliary)

try:
    from AppKit import NSTextAlignmentRight as ALIGN_RIGHT
    from AppKit import NSTextAlignmentCenter as ALIGN_CENTER
except ImportError:                      # numeric fallbacks (macOS values)
    ALIGN_RIGHT, ALIGN_CENTER = 1, 2

_logo_cache = None


def _logo():
    global _logo_cache
    if _logo_cache is None:
        img = NSImage.alloc().initWithContentsOfFile_(
            str(config.PROJECT / "assets" / "quill-logo.png"))
        if img:
            img.setTemplate_(True)
        _logo_cache = img
    return _logo_cache


def _serif(size, weight=0.3):
    """Wordmark font: New York via the system serif design, Georgia fallback."""
    try:
        from AppKit import NSFontDescriptorSystemDesignSerif
        base = NSFont.systemFontOfSize_weight_(size, weight)
        desc = base.fontDescriptor().fontDescriptorWithDesign_(NSFontDescriptorSystemDesignSerif)
        f = NSFont.fontWithDescriptor_size_(desc, size)
        if f:
            return f
    except Exception:
        pass
    return NSFont.fontWithName_size_("Georgia-Bold", size) or NSFont.boldSystemFontOfSize_(size)


def _screen():
    return NSScreen.mainScreen().visibleFrame()


def _make_panel(rect, corner=16.0):
    p = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, _STYLE, NSBackingStoreBuffered, False)
    p.setLevel_(NSFloatingWindowLevel)
    p.setCollectionBehavior_(_BEHAVIOR)
    p.setBackgroundColor_(PAPER)
    p.setHasShadow_(True)
    p.setMovableByWindowBackground_(True)
    p.setHidesOnDeactivate_(False)
    cv = p.contentView()
    cv.setWantsLayer_(True)
    cv.layer().setCornerRadius_(corner)
    cv.layer().setMasksToBounds_(True)
    cv.layer().setBorderWidth_(1.0)
    cv.layer().setBorderColor_(HAIRLINE.CGColor())
    return p


def _slide_in(panel):
    """Entrance: slide+fade from the right (README Motion)."""
    try:
        from AppKit import NSAnimationContext
        final = panel.frame()
        start = NSMakeRect(final.origin.x + 26, final.origin.y,
                           final.size.width, final.size.height)
        panel.setFrame_display_(start, False)
        panel.setAlphaValue_(0.0)
        panel.orderFrontRegardless()

        def _blk(ctx):
            ctx.setDuration_(0.45)
            panel.animator().setFrame_display_(final, True)
            panel.animator().setAlphaValue_(1.0)

        NSAnimationContext.runAnimationGroup_completionHandler_(_blk, None)
    except Exception:
        panel.setAlphaValue_(1.0)
        panel.orderFrontRegardless()


def _label(text, size, color, weight=0.0, mono=False):
    l = NSTextField.labelWithString_(str(text))
    if mono:
        l.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(size, weight))
    else:
        l.setFont_(NSFont.systemFontOfSize_weight_(size, weight))
    l.setTextColor_(color)
    return l


def _pill_button(title, target, action, kind="ghost"):
    """34pt-high rounded-9 buttons per spec: 'primary' accent / 'ghost' ink."""
    b = NSButton.buttonWithTitle_target_action_(title, target, action)
    b.setBordered_(False)
    b.setWantsLayer_(True)
    b.layer().setCornerRadius_(9.0)
    if kind == "primary":
        b.layer().setBackgroundColor_(ACCENT.CGColor())
        fg, weight = NSColor.whiteColor(), 0.3
    elif kind == "ghost-secondary":
        b.layer().setBackgroundColor_(GHOST.CGColor())
        fg, weight = SECONDARY, 0.23
    else:
        b.layer().setBackgroundColor_(GHOST.CGColor())
        fg, weight = INK, 0.23
    attrs = {NSFontAttributeName: NSFont.systemFontOfSize_weight_(13, weight),
             NSForegroundColorAttributeName: fg}
    b.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(title, attrs))
    return b


def _icon_slot(x, y, bg, image, image_pts, tint=INK):
    """42×42 radius-12 slot with a centered template image."""
    slot = NSView.alloc().initWithFrame_(NSMakeRect(x, y, 42, 42))
    slot.setWantsLayer_(True)
    slot.layer().setBackgroundColor_(bg.CGColor())
    slot.layer().setCornerRadius_(12.0)
    if image is not None:
        iv = NSImageView.imageViewWithImage_(image)
        iv.setFrame_(NSMakeRect((42 - image_pts) / 2, (42 - image_pts) / 2,
                                image_pts, image_pts))
        try:
            iv.setContentTintColor_(tint)
        except Exception:
            pass
        slot.addSubview_(iv)
    return slot


def _status_dot_text(dot_color, text, text_color):
    s = NSMutableAttributedString.alloc().init()
    s.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(
        "● ", {NSFontAttributeName: NSFont.systemFontOfSize_(9),
               NSForegroundColorAttributeName: dot_color}))
    s.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(
        text, {NSFontAttributeName: NSFont.systemFontOfSize_weight_(11, 0.23),
               NSForegroundColorAttributeName: text_color}))
    return s


# ---------- 2 · call-detected popup ----------

class CallPopup(NSObject):
    def initWithCallback_(self, callback):
        self = objc.super(CallPopup, self).init()
        if self is None:
            return None
        self.callback = callback
        self.panel = None
        return self

    def showWithContext_(self, context):
        if self.panel is not None:
            return
        f = _screen()
        w, h = 360, 122
        pad = 17
        rect = NSMakeRect(f.origin.x + f.size.width - w - MARGIN,
                          f.origin.y + f.size.height - h - MARGIN, w, h)
        p = _make_panel(rect)
        cv = p.contentView()

        cv.addSubview_(_icon_slot(pad, h - pad - 42, GHOST, _logo(), 26))

        tx = pad + 42 + 13
        title = _label("Call detected", 15, INK, weight=0.3)
        title.setFrame_(NSMakeRect(tx, h - pad - 20, w - tx - pad, 19))
        cv.addSubview_(title)
        sub = _label(f"{context} · take notes?", 12.5, SECONDARY)
        sub.setFrame_(NSMakeRect(tx, h - pad - 39, w - tx - pad, 16))
        sub.setLineBreakMode_(4)
        cv.addSubview_(sub)

        ign = _pill_button("Ignore", self, "ignore:", "ghost")
        ign.setFrame_(NSMakeRect(pad, 14, 82, 34))
        cv.addSubview_(ign)
        rec = _pill_button("Take notes", self, "record:", "primary")
        rec.setFrame_(NSMakeRect(pad + 82 + 9, 14, w - pad * 2 - 82 - 9, 34))
        rec.setKeyEquivalent_("\r")
        cv.addSubview_(rec)

        _slide_in(p)
        self.panel = p
        self.performSelector_withObject_afterDelay_("timeout:", None, 30.0)

    def record_(self, sender):
        self._finish_(True)

    def ignore_(self, sender):
        self._finish_(False)

    def timeout_(self, _):
        self._finish_(False)

    def _finish_(self, accepted):
        NSObject.cancelPreviousPerformRequestsWithTarget_(self)
        if self.panel is not None:
            self.panel.orderOut_(None)
            self.panel = None
            self.callback(accepted)


class _FlippedView(NSView):
    def isFlipped(self):
        return True


# ---------- 3 · live transcript panel ----------

class LivePanel(NSObject):
    def initWithCloser_(self, closer):
        self = objc.super(LivePanel, self).init()
        if self is None:
            return None
        self.closer = closer
        f = _screen()
        w, h = 340, 452
        HDR, FTR = 46, 38
        rect = NSMakeRect(f.origin.x + f.size.width - w - MARGIN,
                          f.origin.y + f.size.height - h - 150, w, h)
        p = _make_panel(rect)
        cv = p.contentView()

        # header: mark · Quill · status pill · clock · ✕
        if _logo() is not None:
            iv = NSImageView.imageViewWithImage_(_logo())
            iv.setFrame_(NSMakeRect(15, h - 33, 19, 19))
            try:
                iv.setContentTintColor_(INK)
            except Exception:
                pass
            cv.addSubview_(iv)
        wm = NSTextField.labelWithString_("Quill")
        wm.setFont_(_serif(15, 0.3))
        wm.setTextColor_(INK)
        wm.setFrame_(NSMakeRect(40, h - 33, 44, 20))
        cv.addSubview_(wm)

        self.status = NSTextField.labelWithString_("")
        self.status.setFrame_(NSMakeRect(88, h - 31, 110, 16))
        cv.addSubview_(self.status)

        self.clock = _label("", 11, TERTIARY, mono=True)
        self.clock.setFrame_(NSMakeRect(w - 15 - 24 - 6 - 52, h - 31, 52, 15))
        self.clock.setAlignment_(ALIGN_RIGHT)
        cv.addSubview_(self.clock)

        close = _pill_button("✕", self, "closePanel:", "ghost-secondary")
        close.layer().setCornerRadius_(7.0)
        close.setFrame_(NSMakeRect(w - 15 - 24, h - 34, 24, 24))
        cv.addSubview_(close)

        hl = NSView.alloc().initWithFrame_(NSMakeRect(0, h - HDR, w, 1))
        hl.setWantsLayer_(True)
        hl.layer().setBackgroundColor_(HAIRLINE.CGColor())
        cv.addSubview_(hl)

        # body: chat bubbles — Them left (amber tint), Me right (blue tint)
        sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, FTR, w, h - HDR - FTR))
        sv.setHasVerticalScroller_(True)
        sv.setDrawsBackground_(False)
        sv.setBorderType_(0)
        doc = _FlippedView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 10))
        sv.setDocumentView_(doc)
        cv.addSubview_(sv)
        self.sv = sv
        self.doc = doc
        self.body_w = w

        # footer: static waveform bars + label
        fl = NSView.alloc().initWithFrame_(NSMakeRect(0, FTR - 1, w, 1))
        fl.setWantsLayer_(True)
        fl.layer().setBackgroundColor_(HAIRLINE.CGColor())
        cv.addSubview_(fl)
        for i, bh in enumerate((8, 14, 10, 13)):
            bar = NSView.alloc().initWithFrame_(NSMakeRect(15 + i * 5, (FTR - bh) / 2, 2.5, bh))
            bar.setWantsLayer_(True)
            bar.layer().setBackgroundColor_(ACCENT.CGColor())
            bar.layer().setCornerRadius_(1.25)
            cv.addSubview_(bar)
        foot = _label("listening · both sides", 11.5, TERTIARY)
        foot.setFrame_(NSMakeRect(15 + 4 * 5 + 8, (FTR - 15) / 2, w - 60, 15))
        cv.addSubview_(foot)

        self.panel = p
        self.entries = []          # ("me"|"them"|"note"|"draft", text)
        self.setStatus_("loading")
        return self

    # -- header state --

    def setStatus_(self, state):
        if state == "live":
            self.status.setAttributedStringValue_(_status_dot_text(ACCENT, "live", SECONDARY))
        elif state == "loading":
            self.status.setAttributedStringValue_(_status_dot_text(TERTIARY, "loading", TERTIARY))
        else:
            self.status.setAttributedStringValue_(_status_dot_text(THEM_AMBER, state, SECONDARY))

    def setClock_(self, text):
        self.clock.setStringValue_(str(text))

    # -- body --

    def closePanel_(self, sender):
        self.hide()
        if self.closer is not None:
            self.closer()

    def reset(self):
        self.entries = []
        self.setStatus_("loading")
        self.setClock_("")
        self._render()

    def show(self):
        _slide_in(self.panel)

    def hide(self):
        self.panel.orderOut_(None)

    def appendLine_(self, line):
        line = str(line)
        # draft tail: "◌ Me: partial words…" replaces the previous draft line;
        # a bare "◌" clears it. Finalized lines drop any trailing draft.
        if line.startswith("◌"):
            if self.entries and self.entries[-1][0] == "draft":
                self.entries.pop()
            text = line[1:].strip()
            if text:
                self.entries.append(("draft", text))
            self._render()
            return
        if self.entries and self.entries[-1][0] == "draft":
            self.entries.pop()
        if line.startswith("Me: "):
            self.entries.append(("me", line[4:]))
        elif line.startswith("Them: "):
            self.entries.append(("them", line[6:]))
        elif "loading model" in line:
            self.setStatus_("loading")
            return
        elif line.startswith("● live"):
            self.setStatus_("live")
            return
        else:
            self.entries.append(("note", line.lstrip("⚠ ").strip()))
        self.entries = self.entries[-60:]
        self._render()

    def _render(self):
        out = NSMutableAttributedString.alloc().init()
        n = len(self.entries)
        for i, (spk, text) in enumerate(self.entries):
            last = i == n - 1
            lab_style = NSMutableParagraphStyle.alloc().init()
            body_style = NSMutableParagraphStyle.alloc().init()
            body_style.setParagraphSpacing_(0 if last else 14)
            body_style.setLineHeightMultiple_(1.25)
            if spk == "me":
                lab_style.setAlignment_(ALIGN_RIGHT)
                body_style.setAlignment_(ALIGN_RIGHT)
            elif spk in ("note", "draft"):
                lab_style.setAlignment_(ALIGN_CENTER)
                body_style.setAlignment_(ALIGN_CENTER)
            lab_style.setParagraphSpacingBefore_(0)

            if spk in ("me", "them"):
                dot_color = ME_BLUE if spk == "me" else THEM_AMBER
                lab_font = NSFont.systemFontOfSize_weight_(10.5, 0.3)
                if spk == "them":
                    parts = [("● ", dot_color), ("THEM", SECONDARY)]
                else:
                    parts = [("ME ", SECONDARY), ("●", dot_color)]
                for t, c in parts:
                    out.appendAttributedString_(
                        NSAttributedString.alloc().initWithString_attributes_(
                            t, {NSFontAttributeName: lab_font,
                                NSForegroundColorAttributeName: c,
                                NSParagraphStyleAttributeName: lab_style}))
                out.appendAttributedString_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        "\n", {NSParagraphStyleAttributeName: lab_style}))
                out.appendAttributedString_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        text + ("" if last else "\n"),
                        {NSFontAttributeName: NSFont.systemFontOfSize_(13.5),
                         NSForegroundColorAttributeName: INK,
                         NSParagraphStyleAttributeName: body_style}))
            elif spk == "draft":
                out.appendAttributedString_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        "◌ " + text + ("" if last else "\n"),
                        {NSFontAttributeName: NSFont.systemFontOfSize_(12.5),
                         NSForegroundColorAttributeName: TERTIARY,
                         NSParagraphStyleAttributeName: body_style}))
            else:
                out.appendAttributedString_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        text + ("" if last else "\n"),
                        {NSFontAttributeName: NSFont.systemFontOfSize_(12),
                         NSForegroundColorAttributeName: TERTIARY,
                         NSParagraphStyleAttributeName: body_style}))
        self.tv.textStorage().setAttributedString_(out)
        self.tv.scrollRangeToVisible_(NSMakeRange(out.length(), 0))


# ---------- ask Quill — answer panel ----------

class AnswerPanel(NSObject):
    """Shows a question and its answer from the meeting records."""

    def init(self):
        self = objc.super(AnswerPanel, self).init()
        if self is None:
            return None
        f = _screen()
        w, h = 420, 400
        HDR, FTR = 46, 30
        rect = NSMakeRect(f.origin.x + f.size.width - w - MARGIN,
                          f.origin.y + f.size.height - h - 150, w, h)
        p = _make_panel(rect)
        cv = p.contentView()

        if _logo() is not None:
            iv = NSImageView.imageViewWithImage_(_logo())
            iv.setFrame_(NSMakeRect(15, h - 33, 19, 19))
            try:
                iv.setContentTintColor_(INK)
            except Exception:
                pass
            cv.addSubview_(iv)
        wm = NSTextField.labelWithString_("Ask Quill")
        wm.setFont_(_serif(15, 0.3))
        wm.setTextColor_(INK)
        wm.setFrame_(NSMakeRect(40, h - 33, 120, 20))
        cv.addSubview_(wm)

        close = _pill_button("✕", self, "closePanel:", "ghost-secondary")
        close.layer().setCornerRadius_(7.0)
        close.setFrame_(NSMakeRect(w - 15 - 24, h - 34, 24, 24))
        cv.addSubview_(close)

        self.q_label = _label("", 12, SECONDARY)
        self.q_label.setFrame_(NSMakeRect(16, h - HDR - 22, w - 32, 16))
        self.q_label.setLineBreakMode_(4)
        cv.addSubview_(self.q_label)

        hl = NSView.alloc().initWithFrame_(NSMakeRect(0, h - HDR, w, 1))
        hl.setWantsLayer_(True)
        hl.layer().setBackgroundColor_(HAIRLINE.CGColor())
        cv.addSubview_(hl)

        sv = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, FTR, w, h - HDR - 26 - FTR))
        sv.setHasVerticalScroller_(True)
        sv.setDrawsBackground_(False)
        sv.setBorderType_(0)
        tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h - HDR - 26 - FTR))
        tv.setEditable_(False)
        tv.setSelectable_(True)
        tv.setDrawsBackground_(False)
        tv.setVerticallyResizable_(True)
        tv.setAutoresizingMask_(2)
        tv.setTextContainerInset_((16, 14))
        sv.setDocumentView_(tv)
        cv.addSubview_(sv)

        foot = _label("saved to Questions.md in your vault", 11, TERTIARY)
        foot.setFrame_(NSMakeRect(0, 8, w, 14))
        foot.setAlignment_(ALIGN_CENTER)
        cv.addSubview_(foot)

        self.panel = p
        self.tv = tv
        return self

    def closePanel_(self, sender):
        self.panel.orderOut_(None)

    def showQuestion_(self, question):
        self.q_label.setStringValue_(str(question))
        self.setBody_("thinking — reading your meetings…")
        _slide_in(self.panel)

    def setAnswer_(self, answer):
        self.setBody_(str(answer))
        self.panel.orderFrontRegardless()

    def setBody_(self, text):
        self.tv.setString_(text)
        self.tv.setFont_(NSFont.systemFontOfSize_(13.0))
        self.tv.setTextColor_(INK)


# ---------- 4 · note-ready card ----------

class NotePopup(NSObject):
    def initWithCallback_(self, callback):
        self = objc.super(NotePopup, self).init()
        if self is None:
            return None
        self.callback = callback
        self.panel = None
        return self

    def showWithTitle_(self, note_title):
        if self.panel is not None:
            self.panel.orderOut_(None)
            self.panel = None
        f = _screen()
        w, h = 360, 140
        pad = 17
        rect = NSMakeRect(f.origin.x + f.size.width - w - MARGIN,
                          f.origin.y + f.size.height - h - MARGIN, w, h)
        p = _make_panel(rect)
        cv = p.contentView()

        check = NSImage.imageWithSystemSymbolName_accessibilityDescription_("checkmark", None)
        cv.addSubview_(_icon_slot(pad, h - pad - 42, NOTE_SLOT, check, 22, tint=ACCENT))

        tx = pad + 42 + 13
        title = _label("Note ready", 15, INK, weight=0.3)
        title.setFrame_(NSMakeRect(tx, h - pad - 20, w - tx - pad, 19))
        cv.addSubview_(title)
        sub = _label(str(note_title), 12.5, SECONDARY)
        sub.setFrame_(NSMakeRect(tx, h - pad - 39, w - tx - pad, 16))
        sub.setLineBreakMode_(4)
        cv.addSubview_(sub)

        dlt = _pill_button("Delete", self, "deleteNote:", "ghost-secondary")
        dlt.setFrame_(NSMakeRect(pad, 32, 82, 34))
        cv.addSubview_(dlt)
        opn = _pill_button("Open note", self, "openNote:", "primary")
        opn.setFrame_(NSMakeRect(pad + 82 + 9, 32, w - pad * 2 - 82 - 9, 34))
        opn.setKeyEquivalent_("\r")
        cv.addSubview_(opn)

        hint = _label("Keeps automatically if you do nothing", 11, TERTIARY)
        hint.setFrame_(NSMakeRect(0, 9, w, 14))
        hint.setAlignment_(ALIGN_CENTER)
        cv.addSubview_(hint)

        _slide_in(p)
        self.panel = p
        self.performSelector_withObject_afterDelay_("timeout:", None, 60.0)

    def openNote_(self, sender):
        self._finish_("open")

    def deleteNote_(self, sender):
        self._finish_("delete")

    def timeout_(self, _):
        self._finish_("keep")

    def _finish_(self, action):
        NSObject.cancelPreviousPerformRequestsWithTarget_(self)
        if self.panel is not None:
            self.panel.orderOut_(None)
            self.panel = None
            self.callback(action)
