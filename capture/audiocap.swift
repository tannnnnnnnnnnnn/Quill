// audiocap — records the microphone (echo-cancelled via raw AUVoiceIO) and
// system audio (Core Audio process tap) to me.caf / them.caf.
//
// TWO-PROCESS ARCHITECTURE: the voice-processing unit and the tap's aggregate
// device conflict when they bind the same output device in one process
// (VPIO wins, tap starves — observed 2026-07-14). So the launched process
// (role "mic") captures the AEC mic and spawns ITSELF with --role sys; the
// child (same signed binary → same TCC identity) runs the tap alone.
//
// Markers in <outdir>: audiocap.pid (parent), .ready, .done, .sys_ready, .sys_done
// Usage: audiocap <outdir> [max-seconds] [--role sys]

import AudioToolbox
import AVFoundation
import CoreAudio
import Foundation

setbuf(stdout, nil)

func log(_ msg: String) {
    FileHandle.standardError.write(("audiocap: " + msg + "\n").data(using: .utf8)!)
}
func fail(_ msg: String) -> Never {
    FileHandle.standardError.write(("ERROR: " + msg + "\n").data(using: .utf8)!)
    exit(1)
}

guard CommandLine.arguments.count >= 2 else {
    fail("usage: audiocap <output-dir> [max-seconds] [--role sys]")
}
let outDir = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
var maxSeconds: Double = 14400
if CommandLine.arguments.count >= 3, let s = Double(CommandLine.arguments[2]) {
    maxSeconds = s
}
let roleSys = CommandLine.arguments.contains("--role")
    && CommandLine.arguments.contains("sys")
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

func defaultDevice(_ selector: AudioObjectPropertySelector) -> AudioObjectID {
    var addr = AudioObjectPropertyAddress(mSelector: selector,
                                          mScope: kAudioObjectPropertyScopeGlobal,
                                          mElement: kAudioObjectPropertyElementMain)
    var dev = AudioObjectID(kAudioObjectUnknown)
    var sz = UInt32(MemoryLayout<AudioObjectID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &sz, &dev)
    return dev
}

// ══════════════════════════════ role: sys ══════════════════════════════
// Child process: system-audio process tap → them.caf. Nothing else.

if roleSys {
    let tapDesc = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
    tapDesc.name = "audiocap-system-tap"
    tapDesc.isPrivate = true
    tapDesc.muteBehavior = .unmuted

    var tapID = AudioObjectID(kAudioObjectUnknown)
    var status = AudioHardwareCreateProcessTap(tapDesc, &tapID)
    guard status == noErr, tapID != kAudioObjectUnknown else {
        fail("process tap creation failed (\(status)) — grant System Audio Recording")
    }

    var fmtAddr = AudioObjectPropertyAddress(
        mSelector: kAudioTapPropertyFormat,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var tapASBD = AudioStreamBasicDescription()
    var asbdSize = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
    status = AudioObjectGetPropertyData(tapID, &fmtAddr, 0, nil, &asbdSize, &tapASBD)
    guard status == noErr, let tapFormat = AVAudioFormat(streamDescription: &tapASBD) else {
        fail("cannot read tap format (\(status))")
    }
    log("sys: tap format \(tapFormat.sampleRate) Hz \(tapFormat.channelCount)ch")

    func deviceUID(_ dev: AudioObjectID) -> String {
        var addr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyDeviceUID,
                                              mScope: kAudioObjectPropertyScopeGlobal,
                                              mElement: kAudioObjectPropertyElementMain)
        var uid: CFString = "" as CFString
        var sz = UInt32(MemoryLayout<CFString>.size)
        AudioObjectGetPropertyData(dev, &addr, 0, nil, &sz, &uid)
        return uid as String
    }
    let outUID = deviceUID(defaultDevice(kAudioHardwarePropertyDefaultOutputDevice))
    log("sys: clock device \(outUID)")

    let aggDesc: [String: Any] = [
        kAudioAggregateDeviceNameKey as String: "audiocap-aggregate",
        kAudioAggregateDeviceUIDKey as String: UUID().uuidString,
        kAudioAggregateDeviceIsPrivateKey as String: true,
        kAudioAggregateDeviceIsStackedKey as String: false,
        kAudioAggregateDeviceTapAutoStartKey as String: true,
        kAudioAggregateDeviceMainSubDeviceKey as String: outUID,
        kAudioAggregateDeviceSubDeviceListKey as String: [
            [kAudioSubDeviceUIDKey as String: outUID,
             kAudioSubDeviceDriftCompensationKey as String: true]
        ],
        kAudioAggregateDeviceTapListKey as String: [
            [kAudioSubTapUIDKey as String: tapDesc.uuid.uuidString,
             kAudioSubTapDriftCompensationKey as String: true]
        ],
    ]
    var aggID = AudioObjectID(kAudioObjectUnknown)
    status = AudioHardwareCreateAggregateDevice(aggDesc as CFDictionary, &aggID)
    guard status == noErr, aggID != kAudioObjectUnknown else {
        fail("aggregate device creation failed (\(status))")
    }

    // commonFormat/interleaved MUST match the tap format. Initialised from
    // settings alone the file is non-interleaved float32, every write throws,
    // and the `try?` below drops the error — them.caf keeps its header and
    // gains no frames.
    var themFile: AVAudioFile? = try? AVAudioFile(
        forWriting: outDir.appendingPathComponent("them.caf"),
        settings: tapFormat.settings,
        commonFormat: tapFormat.commonFormat,
        interleaved: tapFormat.isInterleaved)
    guard themFile != nil else { fail("cannot create them.caf") }

    var wroteFrames = false
    var loggedWriteError = false
    var loggedShape = false
    var rawPeak: Float = 0
    var procID: AudioDeviceIOProcID?
    status = AudioDeviceCreateIOProcIDWithBlock(&procID, aggID, nil) { _, inInputData, _, _, _ in
        let abl = UnsafeMutableAudioBufferListPointer(
            UnsafeMutablePointer(mutating: inInputData))
        if !loggedShape {
            loggedShape = true
            var d = "sys: DIAG inInputData buffers=\(abl.count)"
            for (i, b) in abl.enumerated() {
                d += " [\(i)] ch=\(b.mNumberChannels) bytes=\(b.mDataByteSize)"
            }
            log(d)
        }
        for b in abl {
            guard let data = b.mData, b.mDataByteSize > 0 else { continue }
            let n = Int(b.mDataByteSize) / MemoryLayout<Float>.size
            let p = data.bindMemory(to: Float.self, capacity: n)
            for i in 0..<n {
                let v = abs(p[i])
                if v > rawPeak { rawPeak = v }
            }
        }
        guard let buf = AVAudioPCMBuffer(pcmFormat: tapFormat,
                                         bufferListNoCopy: inInputData,
                                         deallocator: nil) else { return }
        do {
            try themFile?.write(from: buf)
            if !wroteFrames { wroteFrames = true; log("sys: first frames written") }
        } catch {
            if !loggedWriteError { loggedWriteError = true; log("sys: WRITE FAILED \(error)") }
        }
    }
    guard status == noErr, procID != nil else { fail("IOProc creation failed (\(status))") }

    var cfgAddr = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyStreamConfiguration,
        mScope: kAudioObjectPropertyScopeInput,
        mElement: kAudioObjectPropertyElementMain)
    var cfgSize: UInt32 = 0
    if AudioObjectGetPropertyDataSize(aggID, &cfgAddr, 0, nil, &cfgSize) == noErr, cfgSize > 0 {
        let raw = UnsafeMutableRawPointer.allocate(byteCount: Int(cfgSize),
                                                   alignment: MemoryLayout<AudioBufferList>.alignment)
        defer { raw.deallocate() }
        if AudioObjectGetPropertyData(aggID, &cfgAddr, 0, nil, &cfgSize, raw) == noErr {
            let list = UnsafeMutableAudioBufferListPointer(
                raw.assumingMemoryBound(to: AudioBufferList.self))
            var d = "sys: DIAG aggregate input streams=\(list.count)"
            for (i, b) in list.enumerated() { d += " [\(i)] ch=\(b.mNumberChannels)" }
            log(d)
        }
    }

    status = AudioDeviceStart(aggID, procID)
    guard status == noErr else { fail("device start failed (\(status))") }

    var stopping = false
    func sysStop() {
        if stopping { return }
        stopping = true
        AudioDeviceStop(aggID, procID)
        if let p = procID { AudioDeviceDestroyIOProcID(aggID, p) }
        AudioHardwareDestroyAggregateDevice(aggID)
        AudioHardwareDestroyProcessTap(tapID)
        themFile = nil
        FileManager.default.createFile(atPath: outDir.appendingPathComponent(".sys_done").path,
                                       contents: nil)
        log("sys: DIAG raw peak from tap buffers = \(rawPeak)")
        log("sys: done")
        exit(0)
    }
    signal(SIGINT, SIG_IGN)
    signal(SIGTERM, SIG_IGN)
    let s1 = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
    s1.setEventHandler { sysStop() }; s1.resume()
    let s2 = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
    s2.setEventHandler { sysStop() }; s2.resume()
    DispatchQueue.main.asyncAfter(deadline: .now() + maxSeconds + 10) { sysStop() }

    FileManager.default.createFile(atPath: outDir.appendingPathComponent(".sys_ready").path,
                                   contents: nil)
    log("sys: recording")
    RunLoop.main.run()
    exit(0)
}

// ══════════════════════════════ role: mic ══════════════════════════════
// Parent: echo-cancelled mic (raw AUVoiceIO, plain-engine fallback) + child spawn.

switch AVCaptureDevice.authorizationStatus(for: .audio) {
case .authorized:
    break
case .notDetermined:
    let sem = DispatchSemaphore(value: 0)
    var granted = false
    AVCaptureDevice.requestAccess(for: .audio) { ok in granted = ok; sem.signal() }
    sem.wait()
    if !granted { fail("microphone permission denied") }
default:
    fail("microphone permission denied — System Settings > Privacy & Security > Microphone")
}

final class MicCtx {
    var unit: AudioUnit?
    var file: AVAudioFile?
    var fmt: AVAudioFormat?
}
let micCtx = MicCtx()
var engine: AVAudioEngine? = nil
var micFile: AVAudioFile? = nil

func startVoiceProcessedMic() -> Bool {
    var desc = AudioComponentDescription(componentType: kAudioUnitType_Output,
                                         componentSubType: kAudioUnitSubType_VoiceProcessingIO,
                                         componentManufacturer: kAudioUnitManufacturer_Apple,
                                         componentFlags: 0, componentFlagsMask: 0)
    guard let comp = AudioComponentFindNext(nil, &desc) else { return false }
    var unitOpt: AudioUnit?
    guard AudioComponentInstanceNew(comp, &unitOpt) == noErr, let unit = unitOpt else { return false }
    micCtx.unit = unit

    var one: UInt32 = 1
    guard AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO,
                               kAudioUnitScope_Input, 1, &one, 4) == noErr,
          AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO,
                               kAudioUnitScope_Output, 0, &one, 4) == noErr else { return false }

    var dIn = defaultDevice(kAudioHardwarePropertyDefaultInputDevice)
    var dOut = defaultDevice(kAudioHardwarePropertyDefaultOutputDevice)
    guard AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice,
                               kAudioUnitScope_Global, 1, &dIn,
                               UInt32(MemoryLayout<AudioObjectID>.size)) == noErr,
          AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice,
                               kAudioUnitScope_Global, 0, &dOut,
                               UInt32(MemoryLayout<AudioObjectID>.size)) == noErr else { return false }

    if #available(macOS 14.0, *) {
        var duck = AUVoiceIOOtherAudioDuckingConfiguration(
            mEnableAdvancedDucking: DarwinBoolean(false),
            mDuckingLevel: .min)
        let ds = AudioUnitSetProperty(unit, kAUVoiceIOProperty_OtherAudioDuckingConfiguration,
                                      kAudioUnitScope_Global, 0, &duck,
                                      UInt32(MemoryLayout<AUVoiceIOOtherAudioDuckingConfiguration>.size))
        log("vp ducking config status: \(ds)")
    }

    var silenceCB = AURenderCallbackStruct(inputProc: { _, flags, _, _, _, ioData -> OSStatus in
        if let abl = UnsafeMutableAudioBufferListPointer(ioData) {
            for buf in abl { memset(buf.mData, 0, Int(buf.mDataByteSize)) }
        }
        flags.pointee.insert(.unitRenderAction_OutputIsSilence)
        return noErr
    }, inputProcRefCon: nil)
    guard AudioUnitSetProperty(unit, kAudioUnitProperty_SetRenderCallback,
                               kAudioUnitScope_Input, 0, &silenceCB,
                               UInt32(MemoryLayout<AURenderCallbackStruct>.size)) == noErr else { return false }

    guard AudioUnitInitialize(unit) == noErr else { return false }

    var fmt = AudioStreamBasicDescription()
    var fsz = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
    guard AudioUnitGetProperty(unit, kAudioUnitProperty_StreamFormat,
                               kAudioUnitScope_Output, 1, &fmt, &fsz) == noErr,
          fmt.mSampleRate > 0,
          let avfmt = AVAudioFormat(streamDescription: &fmt) else {
        AudioUnitUninitialize(unit)
        return false
    }
    guard let f = try? AVAudioFile(forWriting: outDir.appendingPathComponent("me.caf"),
                                   settings: avfmt.settings) else {
        AudioUnitUninitialize(unit)
        return false
    }
    micCtx.file = f
    micCtx.fmt = avfmt

    let refCon = Unmanaged.passRetained(micCtx).toOpaque()
    var inputCB = AURenderCallbackStruct(inputProc: { rc, flags, ts, bus, frames, _ -> OSStatus in
        let c = Unmanaged<MicCtx>.fromOpaque(rc).takeUnretainedValue()
        guard let u = c.unit, let fmt = c.fmt,
              let buf = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: frames) else { return noErr }
        buf.frameLength = frames
        let stx = AudioUnitRender(u, flags, ts, bus, frames, buf.mutableAudioBufferList)
        if stx == noErr { try? c.file?.write(from: buf) }
        return stx
    }, inputProcRefCon: refCon)
    guard AudioUnitSetProperty(unit, kAudioOutputUnitProperty_SetInputCallback,
                               kAudioUnitScope_Global, 1, &inputCB,
                               UInt32(MemoryLayout<AURenderCallbackStruct>.size)) == noErr else { return false }

    guard AudioOutputUnitStart(unit) == noErr else { return false }
    log("mic: voice-processed (AEC on), \(avfmt.sampleRate) Hz \(avfmt.channelCount)ch")
    return true
}

if !startVoiceProcessedMic() {
    log("mic: VPIO unavailable — falling back to plain capture")
    if let u = micCtx.unit { AudioUnitUninitialize(u); micCtx.unit = nil }
    let eng = AVAudioEngine()
    let micFormat = eng.inputNode.inputFormat(forBus: 0)
    guard micFormat.sampleRate > 0, micFormat.channelCount > 0 else {
        fail("no usable input device (sample rate 0)")
    }
    log("mic format: \(micFormat.sampleRate) Hz, \(micFormat.channelCount) ch (plain)")
    micFile = try? AVAudioFile(forWriting: outDir.appendingPathComponent("me.caf"),
                               settings: micFormat.settings)
    guard micFile != nil else { fail("cannot create me.caf") }
    eng.inputNode.installTap(onBus: 0, bufferSize: 4096, format: micFormat) { buffer, _ in
        try? micFile?.write(from: buffer)
    }
    do { try eng.start() } catch { fail("mic engine start failed: \(error.localizedDescription)") }
    engine = eng
}

// spawn the system-audio child (same signed binary → same TCC identity)
try? FileManager.default.removeItem(at: outDir.appendingPathComponent(".sys_ready"))
try? FileManager.default.removeItem(at: outDir.appendingPathComponent(".sys_done"))
let child = Process()
child.executableURL = Bundle.main.executableURL
    ?? URL(fileURLWithPath: CommandLine.arguments[0])
child.arguments = [outDir.path, String(Int(maxSeconds)), "--role", "sys"]
do { try child.run() } catch {
    log("sys child spawn failed: \(error.localizedDescription) — mic-only recording")
}
for _ in 0..<24 {   // up to 6s for the tap to come up
    if FileManager.default.fileExists(atPath: outDir.appendingPathComponent(".sys_ready").path) {
        log("sys child ready (pid \(child.processIdentifier))")
        break
    }
    if !child.isRunning { log("sys child exited early — them.caf may be missing"); break }
    Thread.sleep(forTimeInterval: 0.25)
}

// ---------- lifecycle ----------

var stopping = false
func stopAndExit() {
    if stopping { return }
    stopping = true
    log("stopping")
    if child.isRunning {
        child.terminate()   // SIGTERM — child finalizes them.caf, writes .sys_done
        for _ in 0..<32 {
            if FileManager.default.fileExists(atPath: outDir.appendingPathComponent(".sys_done").path) { break }
            Thread.sleep(forTimeInterval: 0.25)
        }
    }
    if let u = micCtx.unit {
        AudioOutputUnitStop(u)
        AudioUnitUninitialize(u)
        micCtx.file = nil
    }
    if let eng = engine {
        eng.inputNode.removeTap(onBus: 0)
        eng.stop()
    }
    micFile = nil
    try? FileManager.default.removeItem(at: outDir.appendingPathComponent("audiocap.pid"))
    FileManager.default.createFile(atPath: outDir.appendingPathComponent(".done").path, contents: nil)
    log("done")
    exit(0)
}

signal(SIGINT, SIG_IGN)
signal(SIGTERM, SIG_IGN)
let sigint = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
sigint.setEventHandler { stopAndExit() }
sigint.resume()
let sigterm = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
sigterm.setEventHandler { stopAndExit() }
sigterm.resume()
DispatchQueue.main.asyncAfter(deadline: .now() + maxSeconds) { stopAndExit() }

try? String(ProcessInfo.processInfo.processIdentifier.description)
    .write(to: outDir.appendingPathComponent("audiocap.pid"), atomically: true, encoding: .utf8)
FileManager.default.createFile(atPath: outDir.appendingPathComponent(".ready").path, contents: nil)
print("READY")
log("recording to \(outDir.path) (max \(Int(maxSeconds))s)")
RunLoop.main.run()
