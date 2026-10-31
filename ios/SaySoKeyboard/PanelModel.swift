import SwiftUI
import UIKit

enum PanelTab: String, CaseIterable, Identifiable {
    case rewrite = "Rewrite"
    case compose = "Write"
    case replies = "Replies"

    var id: String { rawValue }
}

enum KeyboardMode { case letters, panel }

enum ShiftState { case off, on, caps }

struct PanelOption: Identifiable, Hashable {
    let id = UUID()
    let label: String?
    let text: String
    var parts: [String] = []  // a series: the messages to send one by one
}

@MainActor
final class PanelModel: ObservableObject {
    @Published var mode: KeyboardMode = .letters
    @Published var tab: PanelTab = .rewrite
    @Published var audience: Audience {
        didSet { UserDefaults.standard.set(audience.rawValue, forKey: "audience") }
    }
    @Published var format: ReplyFormat {
        didSet { UserDefaults.standard.set(format.rawValue, forKey: "format") }
    }
    @Published var suggested: [Audience] = []  // the AI's top 3 for the last text, most likely first
    @Published var settings = KeyboardSettings()
    @Published var draft = ""
    @Published var options: [PanelOption] = []
    @Published var series: [String] = []  // the series being sent, part by part
    @Published var seriesIndex = 0
    @Published var busy = false
    @Published var message: String?
    @Published var warming = false
    @Published var showsGlobe = true
    @Published var hasFullAccess = false

    // Letters
    @Published var language: KeyboardLanguage {
        didSet { UserDefaults.standard.set(language.rawValue, forKey: "language") }
    }
    @Published var page: KeyPage = .letters
    @Published var shift: ShiftState = .on
    @Published var returnLabel = "return"
    private var lastShiftTap = Date.distantPast

    private weak var controller: UIInputViewController?
    private var proxy: UITextDocumentProxy? { controller?.textDocumentProxy }
    private let haptic = UIImpactFeedbackGenerator(style: .light)

    init(controller: UIInputViewController) {
        self.controller = controller
        let defaults = UserDefaults.standard
        audience = defaults.string(forKey: "audience").flatMap(Audience.init(rawValue:)) ?? .friends
        format = defaults.string(forKey: "format").flatMap(ReplyFormat.init(rawValue:)) ?? .message
        language = defaults.string(forKey: "language").flatMap(KeyboardLanguage.init(rawValue:)) ?? .russian
    }

    /// On every open: the app's keyboard settings (App Group, needs Full Access), the mode it opens with.
    func appear(fullAccess: Bool, needsGlobe: Bool) {
        hasFullAccess = fullAccess
        showsGlobe = needsGlobe
        if fullAccess {
            settings = SharedStore.keyboard
            SharedStore.keyboardOpenedWithFullAccess = Date()
        }
        if !settings.audiences.contains(audience), let first = settings.audiences.first { audience = first }
        if !settings.formats.contains(format), let first = settings.formats.first { format = first }
        mode = settings.startsWithLetters ? .letters : .panel
        returnLabel = Self.label(for: proxy?.returnKeyType)
        readDraft()
        autoShift()
    }

    /// The text in the field before the cursor is the user's draft (or instruction).
    /// iOS may only expose part of a long field; for a chat message that is the whole draft.
    func readDraft() {
        draft = proxy?.documentContextBeforeInput ?? ""
    }

    func nextKeyboard() {
        controller?.advanceToNextInputMode()
    }

    // MARK: - Letter keys

    func type(_ key: String) {
        tap()
        proxy?.insertText(shift == .off ? key : key.uppercased())
        if shift == .on { shift = .off }
        afterTyping()
    }

    func typeAlternate(_ key: String) {
        guard let alternate = alternates[key] else { return }
        tap()
        proxy?.insertText(shift == .off ? alternate : alternate.uppercased())
        if shift == .on { shift = .off }
        afterTyping()
    }

    func space() {
        tap()
        // Double space ends a sentence, as on the system keyboard.
        if let before = proxy?.documentContextBeforeInput, before.hasSuffix(" "), !before.hasSuffix("  "),
           let last = before.dropLast().last, last.isLetter || last.isNumber {
            proxy?.deleteBackward()
            proxy?.insertText(". ")
        } else {
            proxy?.insertText(" ")
        }
        if page != .letters { page = .letters }
        afterTyping()
    }

    func newline() {
        tap()
        proxy?.insertText("\n")
        afterTyping()
    }

    func deleteBackward() {
        tap()
        proxy?.deleteBackward()
        afterTyping()
    }

    func toggleShift() {
        tap()
        let now = Date()
        shift = now.timeIntervalSince(lastShiftTap) < 0.3 ? .caps : (shift == .off ? .on : .off)
        lastShiftTap = now
    }

    func switchLanguage() {
        tap()
        language = language.other
    }

    private func afterTyping() {
        readDraft()
        autoShift()
        if !options.isEmpty && series.isEmpty { options = [] }
    }

    /// Capital letter at the start of the field and of a sentence.
    func autoShift() {
        guard shift != .caps else { return }
        let before = proxy?.documentContextBeforeInput ?? ""
        let ended = before.trimmingCharacters(in: .whitespaces).last.map { ".!?".contains($0) } ?? false
        shift = before.isEmpty || before.hasSuffix("\n") || (before.hasSuffix(" ") && ended) ? .on : .off
    }

    private func tap() {
        if settings.haptics && hasFullAccess { haptic.impactOccurred(intensity: 0.6) }
    }

    private static func label(for type: UIReturnKeyType?) -> String {
        switch type {
        case .send: "send"
        case .search, .google, .yahoo: "search"
        case .go: "go"
        case .done: "done"
        case .next: "next"
        default: "return"
        }
    }

    // MARK: - ✨ and the panel

    /// ✨: the text in the field, in the user's style, as 1–3 variants that replace the keys until one is picked.
    func sparkle() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            message = "Type something first, then ✨."
            return
        }
        let count = settings.variants
        let audience = audience, format = format
        perform {
            var responses = [try await SaySoAPI.rewrite(text, audience: audience, format: format)]
            if responses[0].candidates.count < count, count > 1 {  // Muse Spark writes one at a time: ask again
                await withTaskGroup(of: StyledResponse?.self) { group in
                    for _ in 1..<count { group.addTask { try? await SaySoAPI.rewrite(text, audience: audience, format: format) } }
                    for await response in group { if let response { responses.append(response) } }
                }
            }
            self.suggest(responses[0].audiences)
            return self.unique(responses.map { PanelOption(label: nil, text: $0.text, parts: $0.parts ?? []) }
                               + responses[0].candidates.map { PanelOption(label: nil, text: $0) }, limit: count)
        }
    }

    func run() {
        switch tab {
        case .rewrite: generate { try await SaySoAPI.rewrite($0, audience: $1, format: $2) }
        case .compose: generate { try await SaySoAPI.compose($0, audience: $1, format: $2) }
        case .replies: loadLatest()
        }
    }

    private func generate(_ call: @escaping (String, Audience, ReplyFormat) async throws -> StyledResponse) {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            message = tab == .rewrite ? "Type a draft first." : "Type what to say, e.g. “say I'm 20 min late”."
            return
        }
        let audience = audience, format = format, limit = settings.variants
        perform {
            let response = try await call(text, audience, format)
            self.suggest(response.audiences)
            let first = PanelOption(label: nil, text: response.text, parts: response.parts ?? [])
            return self.unique([first] + response.candidates.map { PanelOption(label: nil, text: $0) }, limit: limit)
        }
    }

    func loadLatest() {
        perform {
            let latest = try await SaySoAPI.latest()
            guard let replies = latest.replies, !replies.isEmpty else {
                throw SaySoError.invalid("No screenshot replies yet. Double-tap the back of your iPhone in a chat.")
            }
            if let raw = latest.audience, let audience = Audience(rawValue: raw) { self.audience = audience }
            return replies.map { PanelOption(label: $0.intent, text: $0.text, parts: $0.parts ?? []) }
        }
    }

    /// Their copied messages (handed over by the system Paste button, no clipboard prompt) → three replies.
    func reply(to copied: String) {
        let copied = copied.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !copied.isEmpty else {
            message = "Copy their message first."
            return
        }
        let audience = audience, format = format
        perform {
            let response = try await SaySoAPI.reply(messages: copied, audience: audience, format: format)
            self.suggest(response.context.audiences)
            return response.replies.map { PanelOption(label: $0.intent, text: $0.text, parts: $0.parts ?? []) }
        }
    }

    /// Replaces the draft (✨, Rewrite, Write) or inserts at the cursor (Replies). A series goes in part by part:
    /// the first part now, the next one after the user has sent it.
    func insert(_ option: PanelOption) {
        guard let proxy else { return }
        if mode == .letters || tab != .replies {
            for _ in 0..<(proxy.documentContextBeforeInput ?? "").count { proxy.deleteBackward() }
        }
        if option.parts.count > 1 {
            series = option.parts
            seriesIndex = 0
            proxy.insertText(option.parts[0])
            options = [option]
        } else {
            proxy.insertText(option.text)
            options = []
        }
        readDraft()
    }

    /// The next part of a series (after the user sent the previous one).
    func insertNextPart() {
        guard seriesIndex + 1 < series.count, let proxy else { return }
        seriesIndex += 1
        proxy.insertText(series[seriesIndex])
        if seriesIndex + 1 == series.count {
            options = []
            series = []
        }
        readDraft()
    }

    func closeResults() {
        options = []
        series = []
        message = nil
    }

    private func suggest(_ raw: [String]?) {
        suggested = (raw ?? []).compactMap(Audience.init(rawValue:))
    }

    private func unique(_ options: [PanelOption], limit: Int) -> [PanelOption] {
        var seen = Set<String>()
        return Array(options.filter { !$0.text.isEmpty && seen.insert($0.text).inserted }.prefix(max(limit, 1)))
    }

    private func perform(_ work: @escaping () async throws -> [PanelOption]) {
        guard hasFullAccess else {
            message = "SaySo needs Full Access to reach your style: Settings → General → Keyboard → Keyboards → SaySo."
            return
        }
        busy = true
        message = nil
        warming = false
        series = []
        Task {
            do {
                options = try await work()
                if options.isEmpty { message = "Nothing came back, try again." }
            } catch SaySoError.warming {
                warming = true
                message = SaySoError.warming.errorDescription
            } catch {
                message = error.localizedDescription
            }
            busy = false
        }
    }
}
