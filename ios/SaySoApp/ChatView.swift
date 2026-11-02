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
        case .message: "bubble.left"
        case .series: "square.stack"
        case .official: "briefcase"
        case .email: "envelope"
        case .essay: "doc.text"
        }
    }
    var format: ReplyFormat { ReplyFormat(rawValue: rawValue) ?? .email }
    var isFormal: Bool { self == .email || self == .essay }
}

/// Chat with your style: write from an instruction, rewrite a draft, or reply to someone's message, as a message,
/// a series, an official message, an email or an essay. Fix any answer ("shorter", "no emoji", or your own version)
/// and the style remembers what you prefer.
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

    private static let modes: [(ChatMode, String)] = [(.write, "square.and.pencil"), (.rewrite, "arrow.triangle.2.circlepath"),
                                                       (.reply, "arrowshape.turn.up.left")]

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
    @State private var replyTo = ""  // email: the email being answered
    @State private var busy = false
    @State private var editing: (answer: String, text: String)?
    @State private var toast: String?
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
                Theme.backdrop
                VStack(spacing: 0) {
                    controls
                    conversation
                    inputBar
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    VStack(spacing: 1) {
                        LogoView().frame(height: 22)
                        Text("in \(SharedStore.styleName)").font(.caption2.weight(.medium)).foregroundStyle(.secondary)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("New", systemImage: "square.and.pencil") { reset() }.disabled(items.isEmpty)
                }
            }
            .overlay(alignment: .top) {
                if let toast {
                    Label(toast, systemImage: "sparkles")
                        .font(.footnote.weight(.medium))
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .background(.thinMaterial, in: .capsule)
                        .padding(.top, 8)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .sheet(isPresented: Binding(get: { editing != nil }, set: { if !$0 { editing = nil } })) {
                EditAnswerView(text: editing?.text ?? "") { edited in
                    if let original = editing?.answer { Task { await saveEdit(original: original, edited: edited) } }
                    editing = nil
                }
            }
        }
    }

    // MARK: Controls: what to do, what to write, for whom

    private var controls: some View {
        VStack(alignment: .leading, spacing: 10) {
            modePicker
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(kinds) { k in
                        Pill(title: k.label, icon: k.icon, selected: kind == k) { kind = k }
                    }
                }
                .padding(.horizontal, 16)
            }
            .padding(.horizontal, -16)
            details
        }
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .padding(.bottom, 10)
        .onChange(of: mode) { _, _ in
            if !kinds.contains(kind) { kind = .message }
            reset()
        }
        .onChange(of: kind) { _, _ in reset() }
    }

    /// Write / Rewrite / Reply as one segmented capsule.
    private var modePicker: some View {
        HStack(spacing: 4) {
            ForEach(Self.modes, id: \.0) { m, icon in
                Button {
                    withAnimation(.snappy(duration: 0.25)) { mode = m }
                } label: {
                    Label(m.label, systemImage: icon)
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .foregroundStyle(mode == m ? Color.white : Color.primary)
                        .background { if mode == m { Capsule().fill(Theme.accentGradient) } }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(4)
        .background(.regularMaterial, in: .capsule)
        .overlay(Capsule().stroke(Color.primary.opacity(0.06)))
    }

    /// The fields that depend on what is written: who it's for, the email being answered, the essay question.
    @ViewBuilder private var details: some View {
        switch kind {
        case .essay:
            VStack(alignment: .leading, spacing: 8) {
                TextField("Essay question or topic", text: $question, axis: .vertical)
                    .lineLimit(1...3)
                    .font(.subheadline.weight(.medium))
                Divider()
                Stepper(value: $words, in: 100...650, step: 50) {
                    Label("About \(words) words", systemImage: "text.alignleft").font(.subheadline)
                }
            }
            .glassCard(padding: 12)
        case .email where mode == .write:
            HStack(alignment: .top) {
                Image(systemName: "arrowshape.turn.up.left").foregroundStyle(.secondary).padding(.top, 2)
                TextField("Answering an email? Paste it here (optional)", text: $replyTo, axis: .vertical)
                    .lineLimit(1...4)
                    .font(.subheadline)
                PasteButton(payloadType: String.self) { strings in
                    Task { @MainActor in replyTo = strings.joined(separator: "\n") }
                }
                .labelStyle(.iconOnly)
                .buttonBorderShape(.circle)
                .controlSize(.small)
            }
            .glassCard(padding: 12)
        case .email:
            EmptyView()
        default:
            HStack(spacing: 6) {
                Text("To").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(Audience.allCases) { a in
                            Pill(title: a.label, selected: audience == a) { audience = a }
                        }
                    }
                }
            }
        }
    }

    // MARK: The conversation

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if items.isEmpty { empty }
                    ForEach(items) { item in row(item).id(item.id) }
                    if busy { typing }
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: items.count) { _, _ in
                if let last = items.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
            }
        }
    }

    private var typing: some View {
        HStack(spacing: 8) {
            Avatar()
            ProgressView().controlSize(.small)
            Text(kind == .essay ? "Writing your essay…" : "Writing like you…").font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var empty: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text(emptyTitle).font(.system(size: 26, weight: .bold))
                Text(emptySubtitle).font(.subheadline).foregroundStyle(.secondary)
            }
            .padding(.top, 8)
            VStack(spacing: 10) {
                ForEach(examples, id: \.self) { example in
                    Button {
                        text = example
                        focused = true
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: "sparkles").foregroundStyle(Color.accentColor)
                            Text(example).font(.subheadline).foregroundStyle(.primary).multilineTextAlignment(.leading)
                            Spacer(minLength: 0)
                            Image(systemName: "arrow.up.left").font(.caption).foregroundStyle(.tertiary)
                        }
                        .glassCard(padding: 12)
                    }
                    .buttonStyle(.plain)
                }
            }
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "hand.thumbsdown").foregroundStyle(Color.accentColor)
                Text("Not quite you? Tap 👎 and say what to change (\u{201C}shorter\u{201D}, \u{201C}no emoji\u{201D}) or edit it yourself. SaySo remembers.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            .padding(.horizontal, 4)
        }
    }

    private var emptyTitle: String {
        switch (mode, kind) {
        case (.write, .essay): "Your essay, in your voice"
        case (_, .email): mode == .reply ? "Answer an email" : "Write an email"
        case (.write, _): "What should it say?"
        case (.rewrite, _): "Say it your way"
        default: "Reply like you would"
        }
    }

    private var emptySubtitle: String {
        switch (mode, kind) {
        case (.write, .essay): "Add the question above, then your notes: facts, moments, what you think. 🎙 works great here."
        case (.write, .email): "Say what the email should say. SaySo writes it the way you write emails."
        case (.reply, .email): "Paste the email you got. SaySo answers it in your formal voice."
        case (.write, _): "Tell SaySo what to say, it writes it the way you text."
        case (.rewrite, _): "Paste a draft, SaySo rewrites it in your words."
        default: "Paste their message, SaySo answers it like you."
        }
    }

    private var examples: [String] {
        switch (mode, kind) {
        case (.write, .essay): ["I grew up fixing my grandpa's radios, that's how I got into engineering",
                                "Moving to a new city alone taught me to ask for help"]
        case (.write, .email): ["Ask Professor Kim to move my defense to Thursday",
                                "Follow up on my internship application from last week"]
        case (.reply, .email): ["Hi, we'd like to invite you to an interview on Monday at 10. Please confirm."]
        case (.write, .official): ["Ask my manager for Friday off", "Tell the landlord the heating is broken again"]
        case (.write, .series): ["Tell the guys about my weekend in the mountains", "Explain to mom why I'll be late tonight"]
        case (.write, _): ["Tell Mira I'm 20 min late", "Ask if anyone wants pizza tonight", "Say happy birthday to Dan"]
        case (.rewrite, _): ["Dear friend, I regret to inform you that I will not be able to attend today.",
                             "I'm sorry but I think I need a bit more time for the project"]
        default: ["Are you coming tonight? We start at 8", "Can you send me the notes from today's lecture?"]
        }
    }

    @ViewBuilder private func row(_ item: Item) -> some View {
        switch item {
        case .input(_, let text):
            Text(text)
                .foregroundStyle(.white)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(Theme.accentGradient, in: .rect(cornerRadius: Theme.bubble))
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.leading, 48)
        case .note(_, let text):
            Label(text, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity)
        case .answer(let id, let answer, let audience, let format):
            AnswerView(answer: answer, format: format, audience: audience, isLast: items.last?.id == id,
                       onCopy: { UIPasteboard.general.string = answer.text; show("Copied") },
                       onLike: { Task { await like(answer, audience: audience, format: format) } },
                       onFix: { fixing = true; focused = true },
                       onEdit: { editing = (answer.text, answer.text) },
                       onAudience: { picked in self.audience = picked; Task { await run(again: true) } },
                       onQuestion: { q in answering = q; fixing = true; focused = true },
                       onCopySubject: { subject in UIPasteboard.general.string = subject; show("Subject copied") })
        }
    }

    // MARK: Input

    private var inputBar: some View {
        VStack(spacing: 8) {
            if fixing {
                HStack {
                    Label(answering == nil ? "What should change?" : "Answering a question", systemImage: "wand.and.stars")
                        .font(.caption.weight(.semibold))
                    Spacer()
                    Button("Cancel") { fixing = false; answering = nil }.font(.caption)
                }
                .foregroundStyle(.secondary)
                if answering == nil { reasons }
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
                    .background(.regularMaterial, in: .rect(cornerRadius: 22))
                    .overlay(RoundedRectangle(cornerRadius: 22).stroke(Color.primary.opacity(0.08)))
                actionButton
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 10)
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
            await run(again: false)
        }
    }

    /// Revises the last answer with this feedback (typed, said, or a quick reason chip).
    private func fix(_ feedback: String, shown: String? = nil) async {
        guard !history.isEmpty else { return }
        history[history.count - 1].feedback = feedback
        answering = nil
        items.append(.input(UUID(), shown ?? feedback))
        fixing = false
        await run(again: false)
    }

    /// again: the same input for another audience (a new thread of answers, no feedback).
    private func run(again: Bool) async {
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
                                                 replyTo: answeringEmail ? thread : replyTo)
            history.append(ChatTurn(answer: answer.text))
            items.append(.answer(UUID(), answer, audience, kind.format))
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
        UIPasteboard.general.string = edited
        let result = try? await SaySoAPI.feedback(answer: original, edited: edited, audience: audience, format: format)
        show(result?.learned.map { "Learned: \($0)" } ?? "Saved your version (copied)")
    }

    private func show(_ message: String) {
        withAnimation { toast = message }
        Task {
            try? await Task.sleep(for: .seconds(2.5))
            withAnimation { if toast == message { toast = nil } }
        }
    }

    private func reset() {
        items = []
        history = []
        thread = ""
        fixing = false
        answering = nil
    }
}

/// SaySo's little "S" next to its answers.
struct Avatar: View {
    var body: some View {
        Text("S")
            .font(.system(size: 13, weight: .heavy).width(.expanded))
            .foregroundStyle(.white)
            .frame(width: 28, height: 28)
            .background(Theme.stroke, in: .circle)
    }
}

/// One answer: a bubble (or a stack of bubbles for a series), the AI's audience guesses, and the feedback actions.
struct AnswerView: View {
    let answer: ChatAnswer
    let format: ReplyFormat
    let audience: Audience
    let isLast: Bool
    let onCopy: () -> Void
    let onLike: () -> Void
    let onFix: () -> Void
    let onEdit: () -> Void
    let onAudience: (Audience) -> Void
    var onQuestion: (String) -> Void = { _ in }
    var onCopySubject: (String) -> Void = { UIPasteboard.general.string = $0 }

    @State private var liked = false

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Avatar()
            content
        }
        .padding(.trailing, 24)
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let subject = answer.subject {
                HStack(alignment: .firstTextBaseline) {
                    Label("Subject: \(subject)", systemImage: "envelope")
                        .font(.subheadline.weight(.semibold))
                        .textSelection(.enabled)
                    Spacer(minLength: 8)
                    Button("Copy subject", systemImage: "doc.on.doc") { onCopySubject(subject) }
                        .font(.caption)
                        .buttonStyle(.bordered)
                        .buttonBorderShape(.capsule)
                        .controlSize(.mini)
                }
            }
            ForEach(Array((answer.parts?.isEmpty == false ? answer.parts! : [answer.text]).enumerated()), id: \.offset) { _, part in
                Text(part)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(.regularMaterial, in: .rect(cornerRadius: Theme.bubble))
                    .overlay(RoundedRectangle(cornerRadius: Theme.bubble).stroke(Color.primary.opacity(0.06)))
            }
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
                ForEach(alternatives, id: \.self) { alternative in
                    Text(alternative).font(.footnote).foregroundStyle(.secondary)
                        .padding(.horizontal, 10)
                        .onTapGesture { UIPasteboard.general.string = alternative }
                }
            }
            HStack(spacing: 16) {
                Button(action: onCopy) { Image(systemName: "doc.on.doc") }
                Button { liked = true; onLike() } label: { Image(systemName: liked ? "hand.thumbsup.fill" : "hand.thumbsup") }
                if isLast {
                    Button(action: onFix) { Image(systemName: "hand.thumbsdown") }
                    Button(action: onEdit) { Image(systemName: "pencil") }
                }
                Spacer()
                if isLast, let suggestions = answer.audiences?.compactMap(Audience.init(rawValue:)), suggestions.count > 1 {
                    Menu {
                        ForEach(suggestions) { suggestion in
                            Button { onAudience(suggestion) } label: {
                                Label(suggestion.label, systemImage: suggestion == audience ? "checkmark" : "sparkles")
                            }
                        }
                    } label: {
                        Label("AI: \(suggestions.first!.label)", systemImage: "sparkles").font(.caption)
                    }
                }
            }
            .buttonStyle(.borderless)
            .foregroundStyle(.secondary)
            .font(.subheadline)
            .padding(.horizontal, 4)
        }
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
