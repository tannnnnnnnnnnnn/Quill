// vptest <outdir> <seconds> <mode>
// mode a: VP on input only; mixer→output (vol 0)
// mode d: VP on input only; input→mixer→output (vol 0)  [full duplex pull]
// mode e: VP on both nodes; input→mixer→output (vol 0)
import AVFoundation
import Foundation
setbuf(stdout, nil)
func log(_ m: String) { FileHandle.standardError.write((m + "\n").data(using: .utf8)!) }
guard CommandLine.arguments.count >= 4, let secs = Double(CommandLine.arguments[2]) else {
    log("usage: vptest <outdir> <seconds> <a|d|e>"); exit(1)
}
let outDir = CommandLine.arguments[1]
let mode = CommandLine.arguments[3]
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

let engine = AVAudioEngine()
do {
    try engine.inputNode.setVoiceProcessingEnabled(true)
    if mode == "e" { try engine.outputNode.setVoiceProcessingEnabled(true) }
} catch { print("VPFAIL enable: \(error.localizedDescription)"); exit(2) }
if #available(macOS 14.0, *) {
    engine.inputNode.voiceProcessingOtherAudioDuckingConfiguration =
        AVAudioVoiceProcessingOtherAudioDuckingConfiguration(
            enableAdvancedDucking: false, duckingLevel: .min)
}
if mode == "d" || mode == "e" {
    engine.connect(engine.inputNode, to: engine.mainMixerNode, format: nil)
}
engine.connect(engine.mainMixerNode, to: engine.outputNode, format: nil)
engine.mainMixerNode.outputVolume = 0.0

let url = URL(fileURLWithPath: outDir).appendingPathComponent("vp.caf")
var file: AVAudioFile?
var frames: Int64 = 0
engine.inputNode.installTap(onBus: 0, bufferSize: 4096, format: nil) { buf, _ in
    if file == nil {
        file = try? AVAudioFile(forWriting: url, settings: buf.format.settings)
        log("first buffer: \(buf.format.sampleRate) Hz \(buf.format.channelCount)ch")
    }
    try? file?.write(from: buf)
    frames += Int64(buf.frameLength)
}
engine.prepare()
do { try engine.start() } catch {
    print("VPFAIL start: \(error.localizedDescription)"); exit(5)
}
print("READY")
Thread.sleep(forTimeInterval: secs)
engine.stop()
print("DONE frames=\(frames)")
