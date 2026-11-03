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
    @Published var fromShortcut = false  // the results are replies to a screenshot (Back Tap or "Last screenshot")
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

    // Learning from what the user sends with this keyboard (their own text only)
    private var lastText = ""  // the field's text at the last change
    private var userDeleted = false  // the field was emptied with ⌫, not sent
    private var pasted = false  // text arrived that wasn't typed here (a paste may be someone else's words)
    private var suggestion: String?  // the ✨ variant put in the field, to see if the user changed it
    private var queue: [LearnItem] {
        get { UserDefaults.standard.data(forKey: "learnQueue").flatMap { try? JSONDecoder().decode([LearnItem].self, from: $0) } ?? [] }
        set { UserDefaults.standard.set(try? JSONEncoder().encode(Array(newValue.suffix(200))), forKey: "learnQueue") }
    }

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
        checkShortcutReplies()
        returnLabel = Self.label(for: proxy?.returnKeyType)
        lastText = proxy?.documentContextBeforeInput ?? ""
        readDraft()
        autoShift()
    }

    /// Replies the Back Tap shortcut just made come up here, once, as cards in place of the keys (in either mode): a
    /// tap puts one in the chat (the shortcut can't paste, and iOS drops its clipboard writes while SaySo runs in the
    /// background). Checked on open and every couple of seconds while the keyboard is up, since the shortcut runs
    /// over it. They replace older ✨ results, but never a series that is being sent. Their header says where they
    /// came from; they stay until one is picked or ✕ is tapped.
    func checkShortcutReplies() {
        guard hasFullAccess, !busy, series.isEmpty, let latest = ReplyStore.takeFresh() else { return }
        let replies = latest.replies.map { PanelOption(label: $0.intent, text: $0.text, parts: $0.parts ?? []) }
        guard !replies.isEmpty else { return }
        tab = .replies
        if let audience = Audience(rawValue: latest.context.audience) { self.audience = audience }
        message = nil
        warming = false
        fromShortcut = true
        options = replies
        haptic.impactOccurred()
    }

    /// The panel's Rewrite / Write / Replies picker: switching by hand drops the previous tab's results.
    /// (Not an onChange of `tab`: the shortcut sets the tab too, and must not wipe its own replies.)
    func selectTab(_ newTab: PanelTab) {
        guard newTab != tab else { return }
        tab = newTab
        closeResults()
    }

    /// The text in the field before the cursor is the user's draft (or instruction).
    /// iOS may only expose part of a long field; for a chat message that is the whole draft.
    func readDraft() {
        draft = proxy?.documentContextBeforeInput ?? ""
    }

    /// Called on every change of the field. A field that had text and is suddenly empty (and not because the user
    /// erased it) was sent: that text is one of the user's messages.
    func fieldChanged() {
        // Only what is before the cursor counts as typed: text after it (a quoted email, a reply below) isn't theirs.
        let before = proxy?.documentContextBeforeInput ?? ""
        let now = before + (proxy?.documentContextAfterInput ?? "")
        let sent = lastText.trimmingCharacters(in: .whitespacesAndNewlines)
        if before.count > lastText.count + 1 { pasted = true }  // more than one character at once: not typed here
        if now.isEmpty && !sent.isEmpty && !userDeleted && !pasted {
            remember(sent)
        }
        if now.isEmpty {
            userDeleted = false
            pasted = false
        }
        lastText = before
        readDraft()
        autoShift()
    }

    private var canLearn: Bool {
        guard settings.learns, hasFullAccess, let proxy else { return false }
        // Not in email, link, number, code or search fields (passwords already get the system keyboard).
        let skipped: Set<UIKeyboardType> = [.emailAddress, .URL, .webSearch, .numberPad, .phonePad, .decimalPad,
                                             .asciiCapableNumberPad, .namePhonePad, .numbersAndPunctuation]
        if let type = proxy.keyboardType, skipped.contains(type) { return false }
        if proxy.textContentType != nil || proxy.isSecureTextEntry == true { return false }
        if [.search, .google, .yahoo].contains(proxy.returnKeyType) { return false }
        return true
    }

    private func remember(_ text: String) {
        defer { suggestion = nil }
        guard canLearn else { return }
        if let suggestion, suggestion == text { return }  // sent a suggestion as it was: not the user's own wording
        var items = queue
        items.append(LearnItem(text: text, audience: audience.rawValue, suggested: suggestion))
        queue = items
        if items.count >= 3 { flush() }
    }

    /// Sends what was learned (on every few messages and when the keyboard closes); keeps it if the network fails.
    func flush() {
        let waiting = queue
        guard !waiting.isEmpty, hasFullAccess else { return }
        let items = Array(waiting.prefix(50))  // the server takes at most 50 at a time; the rest go next time
        queue = Array(waiting.dropFirst(50))
        Task {
            do {
                try await SaySoAPI.learn(items)
            } catch {
                queue = items + queue
            }
        }
    }

    func nextKeyboard() {
        controller?.advanceToNextInputMode()
    }

    // MARK: - Letter keys

    func type(_ key: String) {
        tap()
        userDeleted = false
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
        userDeleted = true
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
        lastText = proxy?.documentContextBeforeInput ?? ""
        readDraft()
        autoShift()
        if message != nil { message = nil; warming = false }  // typing again dismisses a status in the strip
        // Typing drops stale ✨ results, but not a series being sent or the screenshot's replies (only ✕ or a pick).
        if !options.isEmpty && series.isEmpty && !fromShortcut { options = [] }
    }

    /// Capital letter at the start of the field and of a sentence (if turned on in the app's Keyboard settings).
    func autoShift() {
        guard shift != .caps else { return }
        guard settings.autoCapitalize else {
            shift = .off
            return
        }
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
            self.fromShortcut = true
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
        lastText = ""  // replacing the draft is not sending it
        message = nil
        // ✨ / Rewrite / Write replace the draft; replies (to a screenshot or copied messages) go in at the cursor.
        if !fromShortcut && (mode == .letters || tab != .replies) {
            for _ in 0..<(proxy.documentContextBeforeInput ?? "").count { proxy.deleteBackward() }
        }
        if option.parts.count > 1 {
            series = option.parts
            seriesIndex = 0
            proxy.insertText(option.parts[0])
            suggestion = option.parts[0]
            options = [option]
        } else {
            proxy.insertText(option.text)
            suggestion = option.text
            options = []
            fromShortcut = false
        }
        userDeleted = false
        lastText = suggestion ?? ""
        readDraft()
    }

    /// The next part of a series (after the user sent the previous one).
    func insertNextPart() {
        guard seriesIndex + 1 < series.count, let proxy else { return }
        seriesIndex += 1
        proxy.insertText(series[seriesIndex])
        suggestion = series[seriesIndex]
        lastText = series[seriesIndex]
        if seriesIndex + 1 == series.count {
            options = []
            series = []
            fromShortcut = false
        }
        readDraft()
    }

    func closeResults() {
        options = []
        series = []
        message = nil
        fromShortcut = false
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
        fromShortcut = false
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
