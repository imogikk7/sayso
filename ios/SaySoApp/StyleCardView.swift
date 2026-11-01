import SwiftUI
import UniformTypeIdentifiers

/// Your style: how you write to each kind of person, what SaySo learned from your corrections, a few real examples.
struct StyleCardView: View {
    let styleID: String
    @Binding var activeID: String
    let onChange: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var style: Style?
    @State private var error: String?
    @State private var importing = false
    @State private var pasting = false
    @State private var adding = false

    var body: some View {
        List {
            if let style {
                Section {
                    if style.id == activeID {
                        Label("The keyboard and shortcut write in this style", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(Color.accentColor)
                    } else if style.isReady {
                        Button("Use this style") {
                            SharedStore.styleID = style.id
                            SharedStore.styleName = style.name
                            activeID = style.id
                        }
                    }
                    if let counts = style.counts {
                        LabeledContent("Learned from", value: "\(counts["turns"] ?? 0) messages in \(counts["chats"] ?? 0) chats")
                    } else if let source = style.source {
                        LabeledContent("Learned from", value: source)
                    }
                }
                if let scores = style.scores {
                    SelfCheckSection(scores: scores, lora: style.lora)
                }
                ForEach(audiences(style), id: \.0) { audience, profile in
                    Section(audience.label) {
                        AudienceProfileView(profile: profile, examples: style.examples?[audience.rawValue] ?? [])
                    }
                }
                Section {
                    if let formal = style.formal, formal.paragraphs > 0 {
                        LabeledContent("Learned from", value: "\(formal.documents) documents · \(formal.paragraphs) paragraphs")
                        if let p = formal.profile {
                            if let words = p.sentenceWords { LabeledContent("Sentences", value: "~\(Int(words)) words") }
                            if let connectors = p.connectors, !connectors.isEmpty {
                                Text("Links ideas with: " + connectors.joined(separator: ", ")).font(.footnote)
                            }
                            if let openings = p.openings, !openings.isEmpty {
                                Text("Opens with: " + openings.joined(separator: " / ")).font(.footnote)
                            }
                            if let closings = p.closings, !closings.isEmpty {
                                Text("Signs off with: " + closings.joined(separator: " / ")).font(.footnote)
                            }
                        }
                    }
                    if adding {
                        ProgressView("Learning your formal voice…")
                    } else {
                        Button { importing = true } label: { Label("Add documents", systemImage: "doc.badge.plus") }
                        Button { pasting = true } label: { Label("Paste text", systemImage: "doc.on.clipboard") }
                        if (style.formal?.paragraphs ?? 0) > 0 {
                            Button("Remove all formal writing", role: .destructive) { Task { await clearFormal() } }
                        }
                    }
                } header: {
                    Text("Formal writing")
                } footer: {
                    Text("Emails, essays, papers you wrote yourself (.txt, .docx, .pdf, or paste). Official messages, emails and essays then sound like your formal self, not a generic polite AI.")
                }
                if let learning = style.learning {
                    Section {
                        LabeledContent("Sent with the keyboard", value: "\(learning.typed)")
                        LabeledContent("Suggestions you changed", value: "\(learning.edited)")
                        LabeledContent("Answers you liked", value: "\(learning.liked)")
                        ForEach(learning.recent) { message in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(message.text).font(.subheadline)
                                if let suggested = message.suggested {
                                    Text("instead of: \(suggested)").font(.caption).foregroundStyle(.secondary).strikethrough()
                                }
                                Text(Audience(rawValue: message.audience)?.label ?? message.audience)
                                    .font(.caption2).foregroundStyle(.tertiary)
                            }
                            .swipeActions { Button("Delete", role: .destructive) { Task { await forgetLearned(message.id) } } }
                        }
                    } header: {
                        Text("Learned from you")
                    } footer: {
                        Text("Your newest messages are used as examples first, so suggestions follow how you write now.")
                    }
                }
                Section {
                    if (style.preferences ?? []).isEmpty {
                        Text("Nothing yet. Fix answers in Chat (\u{201C}shorter\u{201D}, \u{201C}no emoji\u{201D}) and SaySo remembers what you prefer.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    ForEach(Array((style.preferences ?? []).enumerated()), id: \.offset) { index, rule in
                        Text(rule)
                            .swipeActions { Button("Forget", role: .destructive) { Task { await forget(index) } } }
                    }
                } header: {
                    Text("Learned from your corrections")
                }
                if style.id != "main" {
                    Section {
                        Button("Delete style", role: .destructive) { Task { await delete() } }
                    }
                }
            } else if let error {
                Text(error).foregroundStyle(.red)
            } else {
                ProgressView()
            }
        }
        .navigationTitle(style?.name ?? "Style")
        .fileImporter(isPresented: $importing,
                      allowedContentTypes: [.plainText, .pdf, UTType(filenameExtension: "docx") ?? .data, UTType(filenameExtension: "md") ?? .plainText],
                      allowsMultipleSelection: true) { result in
            if case .success(let urls) = result { Task { await addFormal(urls: urls, text: "") } }
        }
        .sheet(isPresented: $pasting) {
            EditAnswerView(text: "") { text in
                pasting = false
                Task { await addFormal(urls: [], text: text) }
            }
        }
        .task { await load() }
        .refreshable { await load() }
    }

    private func audiences(_ style: Style) -> [(Audience, AudienceProfile)] {
        Audience.allCases.compactMap { audience in style.profile?[audience.rawValue].map { (audience, $0) } }
    }

    private func load() async {
        do {
            style = try await SaySoAPI.style(styleID)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func addFormal(urls: [URL], text: String) async {
        var files: [Upload] = []
        for url in urls {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            if let data = try? Data(contentsOf: url) {
                files.append(Upload(name: url.lastPathComponent, data: data,
                                    mimeType: UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream"))
            }
        }
        guard !files.isEmpty || !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        adding = true
        defer { adding = false }
        do {
            try await SaySoAPI.addDocuments(to: styleID, files: files, text: text)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func clearFormal() async {
        style = try? await SaySoAPI.updateStyle(styleID, clearDocuments: true)
    }

    private func forgetLearned(_ id: String) async {
        style = try? await SaySoAPI.updateStyle(styleID, removeLearned: id)
    }

    private func forget(_ index: Int) async {
        style = try? await SaySoAPI.updateStyle(styleID, removePreference: index)
    }

    private func delete() async {
        do {
            try await SaySoAPI.deleteStyle(styleID)
            onChange()
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct AudienceProfileView: View {
    let profile: AudienceProfile
    let examples: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(habits).font(.subheadline)
            if let acts = profile.acts, !acts.isEmpty {
                Text("Usually: " + top(acts)).font(.footnote).foregroundStyle(.secondary)
            }
            if let tones = profile.tones, !tones.isEmpty {
                Text("Tone: " + top(tones)).font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(examples, id: \.self) { example in
                Text("\u{201C}\(example.replacingOccurrences(of: "\n", with: " / "))\u{201D}")
                    .font(.footnote).italic()
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.background.secondary, in: .rect(cornerRadius: 10))
            }
        }
        .padding(.vertical, 4)
    }

    private var habits: String {
        var parts: [String] = []
        if let chars = profile.medianChars { parts.append("~\(Int(chars)) characters") }
        if let lower = profile.lowercaseStart { parts.append("\(Int(lower * 100))% start lowercase") }
        if let punct = profile.endsWithPunctuation { parts.append("\(Int(punct * 100))% end with punctuation") }
        if let laugh = profile.laughter, laugh > 0.05 { parts.append("laughs in \(Int(laugh * 100))%") }
        if let swear = profile.swear, swear > 0.05 { parts.append("swears in \(Int(swear * 100))%") }
        return parts.joined(separator: " · ")
    }

    private func top(_ shares: [String: Double]) -> String {
        shares.sorted { $0.value > $1.value }.prefix(3)
            .map { "\($0.key.replacingOccurrences(of: "_", with: " ")) \(Int($0.value * 100))%" }
            .joined(separator: ", ")
    }
}
