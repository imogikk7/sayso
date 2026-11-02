import AVFoundation
import Foundation

/// Records a voice note as mono 16-bit 16 kHz WAV, the format Muse Voice Transcribe takes.
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
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker])
            try session.setActive(true)
            recorder = try AVAudioRecorder(url: url, settings: [
                AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 16_000, AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false,
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
