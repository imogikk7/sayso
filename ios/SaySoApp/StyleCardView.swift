import SwiftUI

/// Your style: how you write to each kind of person, what SaySo learned from your corrections, a few real examples.
struct StyleCardView: View {
    let styleID: String
    @Binding var activeID: String
    let onChange: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var style: Style?
    @State private var error: String?

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
