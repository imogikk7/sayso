import SwiftUI
import UIKit

/// Chat with your style: write from an instruction, rewrite a draft, or reply to someone's message. Fix any answer
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

    @State private var mode: ChatMode = .write
    @State private var audience: Audience = .friends
    @State private var format: ReplyFormat = .message
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

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                controls
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            if items.isEmpty { empty }
                            ForEach(items) { item in row(item).id(item.id) }
                            if busy { ProgressView().frame(maxWidth: .infinity) }
                        }
                        .padding()
                    }
                    .onChange(of: items.count) { _, _ in
                        if let last = items.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
                    }
                }
                inputBar
            }
            .navigationTitle("Chat")
            .navigationSubtitle("in \(SharedStore.styleName)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
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

    private var controls: some View {
        VStack(spacing: 8) {
            Picker("Mode", selection: $mode) {
                ForEach(ChatMode.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            if mode == .essay {
                TextField("Essay question or topic", text: $question, axis: .vertical)
                    .lineLimit(1...3)
                    .padding(8)
                    .background(.background.secondary, in: .rect(cornerRadius: 10))
                Stepper("About \(words) words", value: $words, in: 100...650, step: 50).font(.subheadline)
            } else if mode == .email {
                HStack(alignment: .top) {
                    TextField("The email you're answering (optional)", text: $replyTo, axis: .vertical)
                        .lineLimit(1...4)
                        .padding(8)
                        .background(.background.secondary, in: .rect(cornerRadius: 10))
                    PasteButton(payloadType: String.self) { strings in
                        Task { @MainActor in replyTo = strings.joined(separator: "\n") }
                    }
                    .labelStyle(.iconOnly)
                    .buttonBorderShape(.circle)
                }
            } else {
            HStack {
                Menu {
                    Picker("For", selection: $audience) { ForEach(Audience.allCases) { Text($0.label).tag($0) } }
                } label: {
                    Label("For: \(audience.label)", systemImage: "person.2").font(.subheadline)
                }
                Spacer()
                Menu {
                    Picker("Format", selection: $format) {
                        ForEach(ReplyFormat.allCases) { Label($0.label, systemImage: $0.systemImage).tag($0) }
                    }
                } label: {
                    Label(format.label, systemImage: format.systemImage).font(.subheadline)
                }
            }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .onChange(of: mode) { _, _ in reset() }
    }

    private var empty: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(emptyTitle).font(.headline)
            Text("Then tell it what to change: \u{201C}shorter\u{201D}, \u{201C}less formal\u{201D}, \u{201C}no emoji\u{201D}, or edit the answer yourself. What you prefer becomes part of your style.")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .padding(.top, 40)
    }

    private var emptyTitle: String {
        switch mode {
        case .write: "Say what to write: \u{201C}tell her I'm 20 min late\u{201D}"
        case .rewrite: "Paste or type a draft to say it your way"
        case .reply: "Paste their message to get your reply"
        case .email: "Say or type what the email should say; paste the one you're answering above"
        case .essay: "Add the question above, then your notes: facts, moments, what you think. 🎙 works great here"
        }
    }

    @ViewBuilder private func row(_ item: Item) -> some View {
        switch item {
        case .input(_, let text):
            Text(text)
                .padding(10)
                .background(Color.accentColor.opacity(0.15), in: .rect(cornerRadius: 14))
                .frame(maxWidth: .infinity, alignment: .trailing)
        case .note(_, let text):
            Text(text).font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity)
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

    private var inputBar: some View {
        VStack(spacing: 6) {
            if fixing {
                HStack {
                    Label("Fixing the last answer", systemImage: "wand.and.stars").font(.caption)
                    Spacer()
                    Button("Cancel") { fixing = false; answering = nil }.font(.caption)
                }
                .foregroundStyle(.secondary)
                if answering == nil { reasons }
            }
            HStack(alignment: .bottom) {
                TextField(placeholder, text: $text, axis: .vertical)
                    .lineLimit(1...6)
                    .focused($focused)
                    .padding(10)
                    .background(.background.secondary, in: .rect(cornerRadius: 18))
                if mode == .reply && !fixing {
                    PasteButton(payloadType: String.self) { strings in
                        Task { @MainActor in text = strings.joined(separator: "\n") }
                    }
                    .labelStyle(.iconOnly)
                    .buttonBorderShape(.circle)
                }
                if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || recorder.isRecording {
                    Button {
                        Task { await voice() }
                    } label: {
                        Image(systemName: recorder.isRecording ? "stop.circle.fill" : "mic.circle.fill")
                            .font(.system(size: 32))
                            .foregroundStyle(recorder.isRecording ? Color.red : Color.accentColor)
                            .symbolEffect(.pulse, isActive: recorder.isRecording)
                    }
                    .disabled(busy)
                } else {
                    Button {
                        Task { await send() }
                    } label: {
                        Image(systemName: "arrow.up.circle.fill").font(.system(size: 32))
                    }
                    .disabled(busy)
                }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    /// After 👎: one tap says what's wrong, without typing. Typing or 🎙 still work for anything else.
    private var reasons: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(fixReasons, id: \.self) { reason in
                    Button(reason) {
                        focused = false
                        Task { await fix(reason) }
                    }
                    .font(.footnote)
                    .buttonStyle(.bordered)
                    .buttonBorderShape(.capsule)
                    .controlSize(.small)
                }
            }
        }
        .disabled(busy || history.isEmpty)
    }

    private var fixReasons: [String] {
        mode.isFormal
            ? ["Shorter", "Longer", "More personal", "Simpler words", "Less formal"]
            : ["Too long", "Too formal", "Too casual", "Not my words", "Wrong meaning", "Too rude"]
    }

    private var placeholder: String {
        if recorder.isRecording { return "Listening… \(recorder.seconds)s — tap ■ when done" }
        if let answering { return "Answer: \(answering)" }
        if fixing { return mode.isFormal ? "What to change or add?" : "What to change? e.g. shorter, warmer, no emoji" }
        switch mode {
        case .write: return "What should it say?"
        case .rewrite: return "Your draft"
        case .reply: return "Their message"
        case .email: return "What should the email say?"
        case .essay: return "Your notes: facts, stories, thoughts"
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
        do {
            let answer = try await SaySoAPI.chat(mode: mode, text: thread, audience: audience, format: format, history: history,
                                                 question: question, words: words, replyTo: replyTo)
            history.append(ChatTurn(answer: answer.text))
            items.append(.answer(UUID(), answer, audience, mode.isFormal ? .email : format))
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
                    .padding(10)
                    .background(.background.secondary, in: .rect(cornerRadius: 14))
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
