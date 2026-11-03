import AVFoundation
import Foundation

/// Records a voice note as mono 16-bit 24 kHz WAV: Muse Voice Transcribe takes 16 or 24 kHz WAV, and 24 kHz (what its
/// realtime API streams) keeps more of the consonants that tell English words apart ("s", "f" and "th" have energy above
/// 8 kHz, where 16 kHz cuts off). Two minutes is 5.8 MB, under the server's 10 MB.
@MainActor
final class VoiceRecorder: ObservableObject {
    @Published private(set) var isRecording = false
    @Published private(set) var seconds = 0

    private var recorder: AVAudioRecorder?
    private var timer: Timer?
    /// Called when the 2-minute limit stops the recording by itself, so the note is sent instead of lost.
    var onLimit: (() -> Void)?
    private let url = FileManager.default.temporaryDirectory.appending(path: "sayso-voice.wav")

    /// Asks for the microphone the first time; false if the user said no.
    func start() async -> Bool {
        guard await AVAudioApplication.requestRecordPermission() else { return false }
        _ = await OnDeviceSpeech.authorized()  // the second hearing; asked now so no dialog interrupts a note
        do {
            let session = AVAudioSession.sharedInstance()
            // .measurement: the raw microphone, without the system's voice processing and automatic gain, which
            // smear the sounds speech recognizers rely on (Apple's own speech sample records this way). The server
            // trims the silence and brings a quiet note up to a normal level (writer.prepare_wav).
            try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker])
            try session.setActive(true)
            recorder = try AVAudioRecorder(url: url, settings: [
                AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 24_000, AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false,
                AVSampleRateConverterAudioQualityKey: AVAudioQuality.max.rawValue,  // 48 kHz mic → 24 kHz, cleanly
            ])
            guard recorder?.record(forDuration: 120) == true else { return false }  // at most 2 minutes
        } catch {
            return false
        }
        isRecording = true
        seconds = 0
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                self.seconds += 1
                if self.recorder?.isRecording == false, self.isRecording {
                    self.timer?.invalidate()
                    self.isRecording = false
                    self.onLimit?()
                }
            }
        }
        return true
    }

    /// Stops and returns the WAV; the file is deleted right away.
    func stop() -> Data? {
        recorder?.stop()
        timer?.invalidate()
        isRecording = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        defer { try? FileManager.default.removeItem(at: url) }
        return try? Data(contentsOf: url)
    }
}
