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
    @State private var busy = false
    @State private var editing: (answer: String, text: String)?
    @State private var toast: String?
    @FocusState private var focused: Bool

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
                       onAudience: { picked in self.audience = picked; Task { await run(again: true) } })
        }
    }

    private var inputBar: some View {
        VStack(spacing: 6) {
            if fixing {
                HStack {
                    Label("Fixing the last answer", systemImage: "wand.and.stars").font(.caption)
                    Spacer()
                    Button("Cancel") { fixing = false }.font(.caption)
                }
                .foregroundStyle(.secondary)
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
                Button {
                    Task { await send() }
                } label: {
                    Image(systemName: "arrow.up.circle.fill").font(.system(size: 32))
                }
                .disabled(busy || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    private var placeholder: String {
        if fixing { return "What to change? e.g. shorter, warmer, no emoji" }
        switch mode {
        case .write: return "What should it say?"
        case .rewrite: return "Your draft"
        case .reply: return "Their message"
        }
    }

    private func send() async {
        let input = text.trimmingCharacters(in: .whitespacesAndNewlines)
        text = ""
        if fixing, !history.isEmpty {
            history[history.count - 1].feedback = input
            items.append(.input(UUID(), input))
            fixing = false
            await run(again: false)
        } else {
            thread = input
            history = []
            items.append(.input(UUID(), input))
            await run(again: false)
        }
    }

    /// again: the same input for another audience (a new thread of answers, no feedback).
    private func run(again: Bool) async {
        guard !thread.isEmpty else { return }
        if again { history = [] }
        busy = true
        defer { busy = false }
        do {
            let answer = try await SaySoAPI.chat(mode: mode, text: thread, audience: audience, format: format, history: history)
            history.append(ChatTurn(answer: answer.text))
            items.append(.answer(UUID(), answer, audience, format))
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

    @State private var liked = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array((answer.parts?.isEmpty == false ? answer.parts! : [answer.text]).enumerated()), id: \.offset) { _, part in
                Text(part)
                    .textSelection(.enabled)
                    .padding(10)
                    .background(.background.secondary, in: .rect(cornerRadius: 14))
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
