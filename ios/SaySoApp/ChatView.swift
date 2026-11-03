import SwiftUI
import UIKit

/// What SaySo writes: a chat message, a series of messages, an official message, an email or an essay. Email and
/// essay are written in the user's formal voice (their own documents) and have their own fields.
enum WriteKind: String, CaseIterable, Identifiable {
    case message, series, official, email, essay

    var id: String { rawValue }
    var label: String { rawValue.capitalized }
    var icon: String {
        switch self {
        case .message: "bubble.left.fill"
        case .series: "square.stack.fill"
        case .official: "briefcase.fill"
        case .email: "envelope.fill"
        case .essay: "doc.text.fill"
        }
    }
    var format: ReplyFormat { ReplyFormat(rawValue: rawValue) ?? .email }
    var isFormal: Bool { self == .email || self == .essay }
}

extension ChatMode {
    var icon: String {
        switch self {
        case .write: "square.and.pencil"
        case .rewrite: "arrow.triangle.2.circlepath"
        default: "arrowshape.turn.up.left.fill"
        }
    }
}

/// A conversation with SaySo, like a messenger: tell it what to write, paste a draft to rewrite, or paste their
/// message to reply; as a message, a series, an official message, an email or an essay. Fix any answer
/// ("shorter", "no emoji", or your own version) and the style remembers what you prefer.
struct ChatView: View {
    private enum Item: Identifiable {
        case input(UUID, String)
        case answer(UUID, ChatAnswer, Audience, ReplyFormat)
        case note(UUID, String)

        var id: UUID {
            switch self {
            case .input(let id, _), .answer(let id, _, _, _), .note(let id, _): id
            }
        }
    }

    /// The quick actions SaySo offers in its welcome message.
    private static let starts: [(String, String, ChatMode, WriteKind)] = [
        ("Message", "bubble.left.fill", .write, .message), ("Email", "envelope.fill", .write, .email),
        ("Essay", "doc.text.fill", .write, .essay), ("Series", "square.stack.fill", .write, .series),
        ("Rewrite", "arrow.triangle.2.circlepath", .rewrite, .message),
        ("Reply", "arrowshape.turn.up.left.fill", .reply, .message),
    ]

    @State private var mode: ChatMode = .write
    @State private var kind: WriteKind = .message
    @State private var audience: Audience = .friends
    @State private var text = ""
    @State private var items: [Item] = []
    @State private var thread = ""  // the input the current answers are for
    @State private var history: [ChatTurn] = []
    @State private var fixing = false
    @State private var answering: String?  // an essay question the user is answering
    @State private var question = ""  // essay: the question or topic
    @State private var words = 250  // essay: about how many words
    @State private var customWords = false  // essay: the length is set with the stepper, not a preset
    @State private var previous: [PreviousTurn] = []  // this thread's last turns, sent back for context
    @State private var busy = false
    @State private var editing: (answer: String, text: String)?
    @State private var toast: String?
    @State private var toastIcon = "sparkles"
    @FocusState private var focused: Bool
    @StateObject private var recorder = VoiceRecorder()

    private var kinds: [WriteKind] { mode == .write ? WriteKind.allCases : WriteKind.allCases.filter { $0 != .essay } }

    /// What the server is asked for: email and essay are their own modes there.
    private var apiMode: ChatMode {
        switch (mode, kind) {
        case (.write, .essay): .essay
        case (.write, .email), (.reply, .email): .email
        default: mode
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ChatWallpaper()
                VStack(spacing: 0) {
                    header
                    conversation
                    composer
                }
            }
            .toolbar(.hidden, for: .navigationBar)
            .overlay(alignment: .top) {
                if let toast {
                    Label(toast, systemImage: toastIcon)
                        .font(.footnote.weight(.semibold))
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .background(.thinMaterial, in: .capsule)
                        .shadow(color: .black.opacity(0.1), radius: 8, y: 3)
                        .padding(.top, 70)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .sheet(isPresented: Binding(get: { editing != nil }, set: { if !$0 { editing = nil } })) {
                EditAnswerView(text: editing?.text ?? "") { edited in
                    if let original = editing?.answer { Task { await saveEdit(original: original, edited: edited) } }
                    editing = nil
                }
            }
            .onChange(of: mode) { _, _ in
                if !kinds.contains(kind) { kind = .message }
            }
        }
    }

    // MARK: Header: the wordmark in one line, and a new chat

    private var header: some View {
        ZStack {
            LogoHorizontal()
                .frame(height: 32)
                .accessibilityAddTraits(.isHeader)
            HStack {
                Spacer()
                Button { withAnimation { reset() } } label: {
                    Image(systemName: "square.and.pencil")
                        .font(.system(size: 16, weight: .semibold))
                        .frame(width: 38, height: 38)
                        .background(.regularMaterial, in: .circle)
                }
                .disabled(items.isEmpty)
                .accessibilityLabel("New chat")
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial)
        .overlay(alignment: .bottom) { Divider().opacity(0.5) }
    }

    // MARK: The conversation

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    welcome
                    ForEach(items) { item in row(item).id(item.id) }
                    if busy { typing }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 16)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: items.count) { _, _ in
                if let last = items.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
            }
        }
    }

    /// SaySo's first messages: who it is, the difference it makes, and what it can write.
    private var welcome: some View {
        VStack(alignment: .leading, spacing: 8) {
            SaySoBubble { Text("Hey! I'm SaySo 👋 I write like **you**, not like an AI.") }
            SaySoBubble(avatar: false) {
                VStack(alignment: .leading, spacing: 10) {
                    Text("What are we writing?")
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)], spacing: 8) {
                        ForEach(Self.starts, id: \.0) { title, icon, m, k in
                            QuickAction(title: title, icon: icon, selected: mode == m && kind == k) {
                                withAnimation(.snappy) {
                                    mode = m
                                    kind = k
                                }
                                focused = k != .essay
                            }
                        }
                    }
                }
            }
            if items.isEmpty { tryThese }
        }
    }

    /// Examples for the current mode and kind, as tappable chips.
    private var tryThese: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Try one").font(.caption.weight(.semibold)).foregroundStyle(.secondary).padding(.leading, 44)
            ForEach(examples, id: \.self) { example in
                Button {
                    if kind == .essay && question.isEmpty { question = example } else { text = example }
                    focused = true
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkles").font(.caption)
                        Text(example).font(.subheadline).multilineTextAlignment(.leading)
                    }
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .foregroundStyle(Color.accentColor)
                    .background(Color.accentColor.opacity(0.1), in: .capsule)
                    .overlay(Capsule().stroke(Color.accentColor.opacity(0.25)))
                }
                .buttonStyle(.plain)
                .padding(.leading, 44)
            }
        }
        .padding(.top, 4)
    }

    private var typing: some View {
        HStack(spacing: 8) {
            Avatar(size: 32)
            TypingDots()
                .padding(.horizontal, 14).padding(.vertical, 12)
                .background(Color(.tertiarySystemBackground), in: BubbleShape(mine: false))
            if kind == .essay { Text("Writing your essay…").font(.caption).foregroundStyle(.secondary) }
        }
    }

    private var examples: [String] {
        switch (mode, kind) {
        case (.write, .essay): ["Why do you want to study engineering?", "A challenge you overcame"]
        case (.write, .email): ["Ask Professor Kim to move my defense to Thursday",
                                "Follow up on my internship application"]
        case (.reply, .email): ["Hi, we'd like to invite you to an interview on Monday at 10. Please confirm."]
        case (.write, .official): ["Ask my manager for Friday off", "Tell the landlord the heating is broken again"]
        case (.write, .series): ["Tell the guys about my weekend in the mountains"]
        case (.write, _): ["Tell Mira I'm 20 min late", "Ask who wants pizza tonight", "Say happy birthday to Dan"]
        case (.rewrite, _): ["Dear friend, I regret to inform you that I will not be able to attend today."]
        default: ["Are you coming tonight? We start at 8", "Can you send me the notes from today's lecture?"]
        }
    }

    @ViewBuilder private func row(_ item: Item) -> some View {
        switch item {
        case .input(_, let text):
            Text(text)
                .foregroundStyle(.white)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(Theme.accentGradient, in: BubbleShape(mine: true))
                .copyMenu(text, shape: BubbleShape(mine: true), onCopy: copy)
                .shadow(color: Color.accentColor.opacity(0.25), radius: 6, y: 2)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.leading, 56)
        case .note(_, let text):
            Label(text, systemImage: "exclamationmark.triangle")
                .font(.footnote).foregroundStyle(.secondary)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(.regularMaterial, in: .capsule)
                .frame(maxWidth: .infinity)
        case .answer(let id, let answer, let audience, let format):
            AnswerView(answer: answer, format: format, audience: audience, isLast: items.last?.id == id,
                       onCopy: copy,
                       onLike: { Task { await like(answer, audience: audience, format: format) } },
                       onFix: { fixing = true; focused = true },
                       onEdit: { editing = (answer.text, answer.text) },
                       onAudience: { picked in self.audience = picked; Task { await run(again: true) } },
                       onQuestion: { q in answering = q; fixing = true; focused = true },
                       onCopySubject: { subject in UIPasteboard.general.string = subject; show("Subject copied") })
        }
    }

    // MARK: Composer

    private var composer: some View {
        VStack(alignment: .leading, spacing: 8) {
            if fixing {
                fixingBar
            } else {
                settingsRow
                details
            }
            HStack(alignment: .bottom, spacing: 8) {
                if mode == .reply && !fixing {
                    PasteButton(payloadType: String.self) { strings in
                        Task { @MainActor in text = strings.joined(separator: "\n") }
                    }
                    .labelStyle(.iconOnly)
                    .buttonBorderShape(.circle)
                    .tint(Color.accentColor)
                }
                TextField(placeholder, text: $text, axis: .vertical)
                    .lineLimit(1...6)
                    .focused($focused)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 22))
                    .overlay(RoundedRectangle(cornerRadius: 22).stroke(Color.primary.opacity(0.08)))
                actionButton
            }
        }
        .padding(.horizontal, 14)
        .padding(.top, 10)
        .padding(.bottom, 8)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) { Divider().opacity(0.5) }
    }

    /// Write / Rewrite / Reply, what it is, and who it's for, as small menus above the field.
    private var settingsRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                Menu {
                    Picker("Mode", selection: $mode) {
                        ForEach([ChatMode.write, .rewrite, .reply]) { m in Label(m.label, systemImage: m.icon).tag(m) }
                    }
                } label: { MenuPill(title: mode.label, icon: mode.icon) }
                Menu {
                    Picker("Kind", selection: $kind) {
                        ForEach(kinds) { k in Label(k.label, systemImage: k.icon).tag(k) }
                    }
                } label: { MenuPill(title: kind.label, icon: kind.icon) }
                if !kind.isFormal {
                    Menu {
                        Picker("To", selection: $audience) {
                            ForEach(Audience.allCases) { a in Text(a.label).tag(a) }
                        }
                    } label: { MenuPill(title: "To \(audience.label)", icon: "person.2.fill") }
                }
            }
        }
    }

    /// The essay's own fields: the question or topic, and how long, as two separate cards.
    @ViewBuilder private var details: some View {
        if kind == .essay && mode == .write {
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Image(systemName: "text.quote").font(.footnote.weight(.semibold)).foregroundStyle(Color.accentColor)
                    TextField("Essay question or topic", text: $question, axis: .vertical)
                        .lineLimit(1...3)
                        .font(.subheadline.weight(.semibold))
                }
                .padding(.horizontal, 12).padding(.vertical, 9)
                .background(Color(.tertiarySystemBackground), in: .rect(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.primary.opacity(0.08)))
                essayLength
            }
        }
    }

    private static let essayLengths = [150, 250, 400, 650]

    /// How long the essay should be: a few presets, or Custom with a stepper.
    private var essayLength: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Label("Length", systemImage: "ruler")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Text("about \(words) words")
                    .font(.caption.weight(.semibold))
                    .monospacedDigit()
                    .foregroundStyle(Color.accentColor)
                    .contentTransition(.numericText())
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Self.essayLengths, id: \.self) { length in
                        LengthChip(title: "\(length)", selected: !customWords && words == length) {
                            withAnimation(.snappy) {
                                customWords = false
                                words = length
                            }
                        }
                    }
                    LengthChip(title: "Custom", selected: customWords) {
                        withAnimation(.snappy) { customWords = true }
                    }
                    if customWords {
                        Stepper("Words", value: $words.animation(.snappy), in: 100...900, step: 50)
                            .labelsHidden()
                            .transition(.opacity.combined(with: .scale(scale: 0.9, anchor: .leading)))
                    }
                }
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 9)
        .background(Color.accentColor.opacity(0.07), in: .rect(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.accentColor.opacity(0.18)))
    }

    private var fixingBar: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Label(answering == nil ? "What should change?" : "Answering a question", systemImage: "wand.and.stars")
                    .font(.caption.weight(.semibold))
                Spacer()
                Button("Cancel") { fixing = false; answering = nil }.font(.caption.weight(.semibold))
            }
            .foregroundStyle(.secondary)
            if answering == nil { reasons }
        }
    }

    private var actionButton: some View {
        let empty = text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        let listening = recorder.isRecording
        return Button {
            Task { if empty || listening { await voice() } else { await send() } }
        } label: {
            Image(systemName: listening ? "stop.fill" : empty ? "mic.fill" : "arrow.up")
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 42, height: 42)
                .background(listening ? AnyShapeStyle(Color.red) : AnyShapeStyle(Theme.accentGradient), in: .circle)
                .shadow(color: Color.accentColor.opacity(0.35), radius: 8, y: 3)
                .symbolEffect(.pulse, isActive: listening)
        }
        .disabled(busy)
        .accessibilityLabel(listening ? "Stop" : empty ? "Speak" : "Send")
    }

    /// After 👎: one tap says what's wrong, without typing. Typing or 🎙 still work for anything else.
    private var reasons: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(fixReasons, id: \.self) { reason in
                    Pill(title: reason, selected: false) {
                        focused = false
                        Task { await fix(reason) }
                    }
                }
            }
        }
        .disabled(busy || history.isEmpty)
    }

    private var fixReasons: [String] {
        kind.isFormal
            ? ["Shorter", "Longer", "More personal", "Simpler words", "Less formal"]
            : ["Too long", "Too formal", "Too casual", "Not my words", "Wrong meaning", "Too rude"]
    }

    private var placeholder: String {
        if recorder.isRecording { return "Listening… \(recorder.seconds)s, tap ■ when done" }
        if let answering { return "Answer: \(answering)" }
        if fixing { return kind.isFormal ? "What to change or add?" : "e.g. shorter, warmer, no emoji" }
        switch (mode, kind) {
        case (.write, .essay): return "Your notes: facts, stories, thoughts"
        case (.write, .email): return "What should the email say?"
        case (.reply, .email): return "The email you got"
        case (.write, _): return "What should it say?"
        case (.rewrite, _): return "Your draft"
        default: return "Their message"
        }
    }

    /// 🎙: say it, Muse Voice Transcribe writes it down, and it goes out like typed text (an instruction, a draft,
    /// their message in Reply, or what to change while fixing).
    private func voice() async {
        if !recorder.isRecording {
            recorder.onLimit = { Task { await finishVoice() } }
            if await !recorder.start() { show("Allow the microphone in Settings → SaySo") }
            return
        }
        await finishVoice()
    }

    /// Stops (or takes the recording the 2-minute limit already stopped) and sends what was said.
    private func finishVoice() async {
        guard let wav = recorder.stop() else { return }
        busy = true
        do {
            let said = try await SaySoAPI.transcribe(wav: wav)
            busy = false
            guard !said.isEmpty else { return show("Didn't catch that, try again") }
            text = said
            await send()
        } catch {
            busy = false
            items.append(.note(UUID(), error.localizedDescription))
        }
    }

    private func send() async {
        let input = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }
        text = ""
        if fixing, !history.isEmpty {
            await fix(answering.map { "Add (answering \"\($0)\"): \(input)" } ?? input, shown: input)
        } else {
            thread = input
            history = []
            items.append(.input(UUID(), input))
            await run(again: false, request: input)
        }
    }

    /// Revises the last answer with this feedback (typed, said, or a quick reason chip).
    private func fix(_ feedback: String, shown: String? = nil) async {
        guard !history.isEmpty else { return }
        history[history.count - 1].feedback = feedback
        answering = nil
        items.append(.input(UUID(), shown ?? feedback))
        fixing = false
        await run(again: false, request: shown ?? feedback)
    }

    /// again: the same input for another audience (a new thread of answers, no feedback). request: what the user
    /// said this turn (the input, or what to change), kept with the answer as context for the next requests.
    private func run(again: Bool, request: String? = nil) async {
        guard !thread.isEmpty else { return }
        if again { history = [] }
        busy = true
        defer { busy = false }
        // Reply + Email: the input is the email they got; it's answered in the user's formal voice.
        let answeringEmail = mode == .reply && kind == .email
        do {
            let answer = try await SaySoAPI.chat(mode: apiMode, text: answeringEmail ? "Answer this email." : thread,
                                                 audience: audience, format: kind.format, history: history,
                                                 question: question, words: words,
                                                 replyTo: answeringEmail ? thread : "", previous: previous)
            history.append(ChatTurn(answer: answer.text))
            items.append(.answer(UUID(), answer, audience, kind.format))
            previous = Array((previous + [PreviousTurn(request: request ?? thread, answer: answer.joinedParts)]).suffix(3))
            if let learned = answer.learned { show("Learned: \(learned)") }
        } catch {
            items.append(.note(UUID(), error.localizedDescription))
        }
    }

    private func like(_ answer: ChatAnswer, audience: Audience, format: ReplyFormat) async {
        show("Saved as an example of your style")
        _ = try? await SaySoAPI.feedback(answer: answer.text, liked: true, audience: audience, format: format)
    }

    private func saveEdit(original: String, edited: String) async {
        let edited = edited.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !edited.isEmpty, edited != original else { return }
        let format = kind.format
        items.append(.answer(UUID(), ChatAnswer(text: edited, parts: format == .series ? edited.split(separator: "\n").map(String.init) : nil),
                             audience, format))
        if !history.isEmpty { history[history.count - 1] = ChatTurn(answer: edited) }
        if let last = previous.last { previous[previous.count - 1] = PreviousTurn(request: last.request, answer: edited) }
        UIPasteboard.general.string = edited
        let result = try? await SaySoAPI.feedback(answer: original, edited: edited, audience: audience, format: format)
        show(result?.learned.map { "Learned: \($0)" } ?? "Saved your version (copied)")
    }

    /// Long-press Copy, a copy button or the action bar: the text goes to the clipboard with a tap and a toast.
    private func copy(_ text: String) {
        UIPasteboard.general.string = text
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        show(String(localized: "Copied"), icon: "doc.on.doc.fill")
    }

    private func show(_ message: String, icon: String = "sparkles") {
        toastIcon = icon
        withAnimation { toast = message }
        Task {
            try? await Task.sleep(for: .seconds(2.5))
            withAnimation { if toast == message { toast = nil } }
        }
    }

    private func reset() {
        items = []
        history = []
        previous = []
        thread = ""
        fixing = false
        answering = nil
    }
}

/// SaySo's avatar: the "S" on the blue brush gradient.
struct Avatar: View {
    var size: CGFloat = 32

    var body: some View {
        Text("S")
            .font(.custom("Archivo-ExpandedBlack", size: size * 0.46))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(Theme.stroke, in: .circle)
            .overlay(Circle().stroke(.white.opacity(0.6), lineWidth: 1.5))
    }
}

/// A chat bubble with a small tail corner: the user's on the right, SaySo's on the left. In a run of messages (a
/// series) only the first one is round at the top on the tail side, as in a messenger.
struct BubbleShape: Shape {
    let mine: Bool
    var first = true

    func path(in rect: CGRect) -> Path {
        let top: CGFloat = first ? 18 : 6
        return UnevenRoundedRectangle(topLeadingRadius: mine ? 18 : top, bottomLeadingRadius: mine ? 18 : 5,
                                      bottomTrailingRadius: mine ? 5 : 18, topTrailingRadius: mine ? top : 18)
            .path(in: rect)
    }
}

extension View {
    /// Long-press a bubble, as in a messenger: Copy (the whole text), Copy all (a series), Share. The preview keeps
    /// the bubble's shape.
    func copyMenu<S: Shape>(_ text: String, all: String? = nil, shape: S,
                            onCopy: @escaping (String) -> Void) -> some View {
        contentShape(.contextMenuPreview, shape)
            .contextMenu {
                Button("Copy", systemImage: "doc.on.doc") { onCopy(text) }
                if let all, all != text {
                    Button("Copy all messages", systemImage: "square.on.square") { onCopy(all) }
                }
                ShareLink(item: all ?? text) { Label("Share", systemImage: "square.and.arrow.up") }
            }
    }
}

extension ChatAnswer {
    /// The messages of the main answer, one per bubble (just the text when there are no parts).
    var messages: [String] { Self.nonEmpty(parts) ?? [text] }

    /// The main answer as one text: its messages, one per line.
    var joinedParts: String { messages.joined(separator: "\n") }

    /// The messages of each alternative, one per card (its text when the server sent no parts for it).
    func alternativeMessages(_ index: Int) -> [String] {
        let alternative = alternatives?[index] ?? ""
        let parts = alternativeParts.flatMap { index < $0.count ? $0[index] : nil }
        return Self.nonEmpty(parts) ?? [alternative]
    }

    private static func nonEmpty(_ parts: [String]?) -> [String]? {
        let kept = (parts ?? []).filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        return kept.isEmpty ? nil : kept
    }
}

/// One message from SaySo, with its avatar (or the space for it, in a run of messages).
struct SaySoBubble<Content: View>: View {
    var avatar = true
    @ViewBuilder let content: Content

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if avatar { Avatar() } else { Color.clear.frame(width: 32, height: 1) }
            content
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(Color(.tertiarySystemBackground), in: BubbleShape(mine: false))
                .shadow(color: .black.opacity(0.06), radius: 4, y: 2)
            Spacer(minLength: 30)
        }
    }
}

/// A quick action inside SaySo's welcome message.
struct QuickAction: View {
    let title: String
    let icon: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon).font(.caption.weight(.bold))
                Text(title).font(.footnote.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.8)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 10).padding(.vertical, 9)
            .foregroundStyle(selected ? Color.white : Color.accentColor)
            .background {
                if selected {
                    RoundedRectangle(cornerRadius: 12).fill(Theme.accentGradient)
                } else {
                    RoundedRectangle(cornerRadius: 12).fill(Color.accentColor.opacity(0.1))
                }
            }
        }
        .buttonStyle(.plain)
    }
}

/// The label of a small menu above the message field.
struct MenuPill: View {
    let title: String
    let icon: String

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: icon).font(.caption2.weight(.bold))
            Text(title).font(.footnote.weight(.semibold))
            Image(systemName: "chevron.down").font(.system(size: 8, weight: .heavy))
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .foregroundStyle(Color.accentColor)
        .background(Color.accentColor.opacity(0.12), in: .capsule)
    }
}

/// Three dots bouncing while SaySo writes.
struct TypingDots: View {
    @State private var on = false

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3, id: \.self) { i in
                Circle().fill(Color.secondary).frame(width: 7, height: 7)
                    .offset(y: on ? -3 : 3)
                    .animation(.easeInOut(duration: 0.45).repeatForever().delay(Double(i) * 0.15), value: on)
            }
        }
        .onAppear { on = true }
    }
}

/// The chat background: the brand backdrop with a faint pattern of writing doodles, like a messenger wallpaper.
struct ChatWallpaper: View {
    private static let symbols = ["sparkles", "bubble.left", "heart", "envelope", "pencil", "face.smiling",
                                  "paperplane", "quote.bubble", "text.bubble", "hand.thumbsup"]

    var body: some View {
        ZStack {
            Theme.backdrop
            Canvas { context, size in
                var seed: UInt64 = 42
                func next() -> Double {
                    seed = seed &* 6364136223846793005 &+ 1442695040888963407
                    return Double(seed >> 33) / Double(UInt64(1) << 31)
                }
                let step: CGFloat = 62
                var y: CGFloat = 24
                var row = 0
                while y < size.height + step {
                    var x: CGFloat = row % 2 == 0 ? 22 : 53
                    while x < size.width + step {
                        let name = Self.symbols[Int(next() * Double(Self.symbols.count)) % Self.symbols.count]
                        var layer = context
                        layer.translateBy(x: x, y: y)
                        layer.rotate(by: .degrees(next() * 50 - 25))
                        let symbol = Text(Image(systemName: name))
                            .font(.system(size: 15 + next() * 6, weight: .medium))
                            .foregroundStyle(Color.accentColor.opacity(0.09))
                        layer.draw(symbol, at: .zero)
                        x += step
                    }
                    y += step
                    row += 1
                }
            }
            .ignoresSafeArea()
        }
    }
}

/// One answer: a bubble per message (a series is a run of bubbles, each with its copy button), the alternatives
/// (a series one is a collapsed stack that opens into cards), the AI's audience guesses and the feedback actions.
struct AnswerView: View {
    let answer: ChatAnswer
    let format: ReplyFormat
    let audience: Audience
    let isLast: Bool
    let onCopy: (String) -> Void
    let onLike: () -> Void
    let onFix: () -> Void
    let onEdit: () -> Void
    let onAudience: (Audience) -> Void
    var onQuestion: (String) -> Void = { _ in }
    var onCopySubject: (String) -> Void = { UIPasteboard.general.string = $0 }

    @State private var liked = false
    @State private var copied: String?

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Avatar()
            content
            Spacer(minLength: 16)
        }
    }

    private func copy(_ text: String) {
        onCopy(text)
        withAnimation(.snappy) { copied = text }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let subject = answer.subject {
                HStack(alignment: .firstTextBaseline) {
                    Label("Subject: \(subject)", systemImage: "envelope")
                        .font(.subheadline.weight(.semibold))
                    Spacer(minLength: 8)
                    Button("Copy subject", systemImage: "doc.on.doc") { onCopySubject(subject) }
                        .font(.caption)
                        .buttonStyle(.bordered)
                        .buttonBorderShape(.capsule)
                        .controlSize(.mini)
                }
            }
            bubbles
            if let count = answer.words, answer.outline != nil {
                Text("\(count) words").font(.caption).foregroundStyle(.secondary)
            }
            if isLast, let questions = answer.questions, !questions.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Make it stronger: answer one").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    ForEach(questions, id: \.self) { q in
                        Button { onQuestion(q) } label: {
                            Label(q, systemImage: "questionmark.bubble").font(.footnote).multilineTextAlignment(.leading)
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            if let alternatives = answer.alternatives, !alternatives.isEmpty {
                Text("Or say it like this").font(.caption.weight(.semibold)).foregroundStyle(.secondary).padding(.leading, 4)
                ForEach(alternatives.indices, id: \.self) { index in
                    AlternativeView(messages: answer.alternativeMessages(index), copied: copied, onCopy: copy)
                }
            }
            actions
        }
    }

    /// The main answer: one bubble, or a run of bubbles (one per message) with a copy button beside each.
    private var bubbles: some View {
        let messages = answer.messages
        let all = messages.count > 1 ? answer.joinedParts : nil
        return VStack(alignment: .leading, spacing: 3) {
            ForEach(messages.indices, id: \.self) { index in
                let message = messages[index]
                let shape = BubbleShape(mine: false, first: index == 0)
                HStack(spacing: 6) {
                    Text(message)
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .background(Color(.tertiarySystemBackground), in: shape)
                        .copyMenu(message, all: all, shape: shape, onCopy: copy)
                        .shadow(color: .black.opacity(0.06), radius: 4, y: 2)
                    if all != nil { CopyChip(done: copied == message) { copy(message) } }
                }
            }
        }
    }

    private var actions: some View {
        HStack(spacing: 8) {
            HStack(spacing: 18) {
                Button { copy(answer.joinedParts) } label: { Image(systemName: "doc.on.doc") }
                    .accessibilityLabel("Copy")
                Button { liked = true; onLike() } label: {
                    Image(systemName: liked ? "hand.thumbsup.fill" : "hand.thumbsup").foregroundStyle(liked ? Color.accentColor : Color.secondary)
                }
                if isLast {
                    Button(action: onFix) { Image(systemName: "hand.thumbsdown") }
                    Button(action: onEdit) { Image(systemName: "pencil") }
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 7)
            .background(.regularMaterial, in: .capsule)
            if isLast, let suggestions = answer.audiences?.compactMap(Audience.init(rawValue:)), suggestions.count > 1 {
                Menu {
                    ForEach(suggestions) { suggestion in
                        Button { onAudience(suggestion) } label: {
                            Label(suggestion.label, systemImage: suggestion == audience ? "checkmark" : "sparkles")
                        }
                    }
                } label: {
                    MenuPill(title: "For \(audience.label)?", icon: "sparkles")
                }
            }
        }
        .buttonStyle(.borderless)
        .foregroundStyle(.secondary)
        .font(.subheadline)
    }
}

/// One "Or say it like this" option. A single message is one card with a copy button. A series is a collapsed
/// stack, like a notification group: its first message on top, one or two cards peeking out beneath and "+N".
/// Tap opens it into one card per message, each with its own copy button.
struct AlternativeView: View {
    let messages: [String]
    let copied: String?
    let onCopy: (String) -> Void

    @State private var expanded = false

    private var all: String? { messages.count > 1 ? messages.joined(separator: "\n") : nil }

    var body: some View {
        if messages.count > 1 && !expanded {
            collapsed
                .transition(.opacity)
        } else {
            VStack(alignment: .leading, spacing: 3) {
                ForEach(messages.indices, id: \.self) { index in
                    let message = messages[index]
                    let shape = BubbleShape(mine: false, first: index == 0)
                    HStack(spacing: 6) {
                        card(Text(message).font(.subheadline), shape: shape)
                            .copyMenu(message, all: all, shape: shape, onCopy: onCopy)
                        CopyChip(done: copied == message) { onCopy(message) }
                    }
                }
                if messages.count > 1 {
                    Button { withAnimation(.snappy) { expanded = false } } label: {
                        Label("Show less", systemImage: "chevron.up")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.secondary)
                            .padding(.leading, 8).padding(.top, 2)
                    }
                    .buttonStyle(.plain)
                }
            }
            .transition(.opacity.combined(with: .scale(scale: 0.97, anchor: .top)))
        }
    }

    /// The first message on top, the rest as cards peeking out beneath it.
    private var collapsed: some View {
        let depth = min(messages.count - 1, 2)
        let shape = BubbleShape(mine: false)
        return HStack(spacing: 6) {
            Button { withAnimation(.snappy) { expanded = true } } label: {
                card(HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(messages[0]).font(.subheadline).lineLimit(3)
                    Text("+\(messages.count - 1)")
                        .font(.caption.weight(.bold))
                        .monospacedDigit()
                        .foregroundStyle(Color.accentColor)
                        .padding(.horizontal, 7).padding(.vertical, 2)
                        .background(Color.accentColor.opacity(0.14), in: .capsule)
                }, shape: shape)
                .background(alignment: .bottom) {
                    ZStack(alignment: .bottom) {
                        if depth > 1 { peek.padding(.horizontal, 18).offset(y: 12).opacity(0.6) }
                        peek.padding(.horizontal, 9).offset(y: 6).opacity(0.9)
                    }
                }
                .padding(.bottom, CGFloat(depth) * 6)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .copyMenu(messages[0], all: all, shape: RoundedRectangle(cornerRadius: 16), onCopy: onCopy)
            .accessibilityHint("Shows all \(messages.count) messages")
            Color.clear.frame(width: CopyChip.size, height: 1)  // lines up with the copy buttons of other cards
        }
    }

    /// A card beneath the top one, only its bottom edge showing.
    private var peek: some View {
        RoundedRectangle(cornerRadius: 14, style: .continuous)
            .fill(Color(.tertiarySystemBackground))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Color.accentColor.opacity(0.2)))
            .shadow(color: .black.opacity(0.06), radius: 3, y: 2)
    }

    /// An alternative's card: lighter than an answer bubble, with a dashed accent edge.
    private func card<Content: View>(_ content: Content, shape: BubbleShape) -> some View {
        content
            .multilineTextAlignment(.leading)
            .foregroundStyle(.primary)
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(Color(.tertiarySystemBackground), in: shape)
            .overlay(shape.stroke(Color.accentColor.opacity(0.35), style: StrokeStyle(lineWidth: 1, dash: [4, 3])))
    }
}

/// The small copy button beside a message of a series or an alternative card; turns into a check once copied.
struct CopyChip: View {
    static let size: CGFloat = 28
    let done: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: done ? "checkmark" : "doc.on.doc")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(done ? Color.accentColor : Color.secondary)
                .contentTransition(.symbolEffect(.replace))
                .frame(width: Self.size, height: Self.size)
                .background(.regularMaterial, in: .circle)
                .overlay(Circle().stroke(Color.primary.opacity(0.06)))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(done ? "Copied" : "Copy")
    }
}

/// One essay length preset (or Custom) in the composer.
struct LengthChip: View {
    let title: LocalizedStringKey
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.footnote.weight(.semibold))
                .monospacedDigit()
                .padding(.horizontal, 12).padding(.vertical, 6)
                .foregroundStyle(selected ? Color.white : Color.primary)
                .background {
                    if selected { Capsule().fill(Theme.accentGradient) } else { Capsule().fill(.regularMaterial) }
                }
                .overlay(Capsule().stroke(Color.primary.opacity(selected ? 0 : 0.08)))
        }
        .buttonStyle(.plain)
    }
}

/// The user writes their own version of an answer: it's copied, kept as an example, and may teach a rule.
struct EditAnswerView: View {
    @State var text: String
    let onSave: (String) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            TextEditor(text: $text)
                .padding()
                .navigationTitle("Your version")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) { Button("Save") { onSave(text) } }
                }
        }
        .presentationDetents([.medium])
    }
}
