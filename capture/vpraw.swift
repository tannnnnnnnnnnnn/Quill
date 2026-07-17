// vpraw — raw AUVoiceIO experiment (below AVAudioEngine): can macOS's
// voice-processing unit run with split mic/speaker devices, and does its
// echo canceller remove OTHER apps' speaker audio from the mic?
// Usage: vpraw <outdir> <seconds>  → writes vp.caf
import AudioToolbox
import AVFoundation
import Foundation

setbuf(stdout, nil)
func log(_ m: String) { FileHandle.standardError.write((m + "\n").data(using: .utf8)!) }
func fail(_ m: String) -> Never { print("VPFAIL \(m)"); exit(1) }

guard CommandLine.arguments.count >= 3, let secs = Double(CommandLine.arguments[2]) else {
    fail("usage: vpraw <outdir> <seconds>")
}
let outDir = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
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
let inDev = defaultDevice(kAudioHardwarePropertyDefaultInputDevice)
let outDev = defaultDevice(kAudioHardwarePropertyDefaultOutputDevice)
log("input dev \(inDev), output dev \(outDev)")

var desc = AudioComponentDescription(componentType: kAudioUnitType_Output,
                                     componentSubType: kAudioUnitSubType_VoiceProcessingIO,
                                     componentManufacturer: kAudioUnitManufacturer_Apple,
                                     componentFlags: 0, componentFlagsMask: 0)
guard let comp = AudioComponentFindNext(nil, &desc) else { fail("no VPIO component") }
var unitOpt: AudioUnit?
guard AudioComponentInstanceNew(comp, &unitOpt) == noErr, let unit = unitOpt else {
    fail("instance create")
}

var one: UInt32 = 1
var st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO,
                              kAudioUnitScope_Input, 1, &one, 4)
log("enable input bus: \(st)")
st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO,
                          kAudioUnitScope_Output, 0, &one, 4)
log("enable output bus: \(st)")

// devices: element 1 = input side, element 0 = output side
var dIn = inDev
st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice,
                          kAudioUnitScope_Global, 1, &dIn, UInt32(MemoryLayout<AudioObjectID>.size))
log("set input device: \(st)")
var dOut = outDev
st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice,
                          kAudioUnitScope_Global, 0, &dOut, UInt32(MemoryLayout<AudioObjectID>.size))
log("set output device: \(st)")

// output render: silence (we play nothing; the question is whether the AEC
// reference covers device playback from other apps anyway)
var silenceCB = AURenderCallbackStruct(inputProc: { _, flags, _, _, frames, ioData -> OSStatus in
    if let abl = UnsafeMutableAudioBufferListPointer(ioData) {
        for buf in abl { memset(buf.mData, 0, Int(buf.mDataByteSize)) }
    }
    flags.pointee.insert(.unitRenderAction_OutputIsSilence)
    return noErr
}, inputProcRefCon: nil)
st = AudioUnitSetProperty(unit, kAudioUnitProperty_SetRenderCallback,
                          kAudioUnitScope_Input, 0, &silenceCB,
                          UInt32(MemoryLayout<AURenderCallbackStruct>.size))
log("set render callback: \(st)")

st = AudioUnitInitialize(unit)
if st != noErr { fail("initialize: \(st)") }

// after init, read the actual client format on the input's output side
var fmt = AudioStreamBasicDescription()
var fsz = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
st = AudioUnitGetProperty(unit, kAudioUnitProperty_StreamFormat,
                          kAudioUnitScope_Output, 1, &fmt, &fsz)
log("client fmt status \(st): \(fmt.mSampleRate) Hz, \(fmt.mChannelsPerFrame)ch, flags \(fmt.mFormatFlags)")
guard st == noErr, fmt.mSampleRate > 0 else { fail("bad client format") }

guard let avfmt = AVAudioFormat(streamDescription: &fmt) else { fail("avformat") }
let file = try! AVAudioFile(forWriting: outDir.appendingPathComponent("vp.caf"),
                            settings: avfmt.settings)

final class Ctx {
    var unit: AudioUnit; var file: AVAudioFile; var fmt: AVAudioFormat; var frames: Int64 = 0
    init(unit: AudioUnit, file: AVAudioFile, fmt: AVAudioFormat) {
        self.unit = unit; self.file = file; self.fmt = fmt
    }
}
let ctx = Ctx(unit: unit, file: file, fmt: avfmt)
let ctxPtr = Unmanaged.passRetained(ctx).toOpaque()

var inputCB = AURenderCallbackStruct(inputProc: { refCon, flags, ts, bus, frames, _ -> OSStatus in
    let c = Unmanaged<Ctx>.fromOpaque(refCon).takeUnretainedValue()
    guard let buf = AVAudioPCMBuffer(pcmFormat: c.fmt, frameCapacity: frames) else { return noErr }
    buf.frameLength = frames
    let stx = AudioUnitRender(c.unit, flags, ts, bus, frames, buf.mutableAudioBufferList)
    if stx == noErr {
        try? c.file.write(from: buf)
        c.frames += Int64(frames)
    }
    return stx
}, inputProcRefCon: ctxPtr)
st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_SetInputCallback,
                          kAudioUnitScope_Global, 1, &inputCB,
                          UInt32(MemoryLayout<AURenderCallbackStruct>.size))
log("set input callback: \(st)")

st = AudioOutputUnitStart(unit)
if st != noErr { fail("start: \(st)") }
print("READY")
Thread.sleep(forTimeInterval: secs)
AudioOutputUnitStop(unit)
AudioUnitUninitialize(unit)
print("DONE frames=\(ctx.frames)")
