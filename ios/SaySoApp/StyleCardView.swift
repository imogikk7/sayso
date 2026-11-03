import SwiftUI

/// One style in full: its self-check, how you write to each kind of person, your formal voice,
/// and what SaySo learned from you and from your corrections.
struct StyleCardView: View {
    let styleID: String
    @Binding var activeID: String
    var focus: Audience? = nil
    let onChange: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var style: Style?
    @State private var error: String?
    @State private var formalKind: FormalKind?
    @State private var confirmClearFormal = false
    @State private var confirmDelete = false

    var body: some View {
        ZStack {
            Theme.backdrop
            ScrollViewReader { proxy in
                ScrollView(.vertical) {
                    content
                        .padding(.horizontal, 20)
                        .padding(.top, 8)
                        .padding(.bottom, 32)
                        .pageWidth()
                }
                .scrollBounceBehavior(.basedOnSize, axes: .horizontal)
                .refreshable { await load() }
                .onChange(of: style?.id) { _, newID in
                    guard newID != nil, let focus else { return }
                    Task {
                        try? await Task.sleep(for: .milliseconds(250))
                        withAnimation(.easeInOut(duration: 0.4)) { proxy.scrollTo(focus.rawValue, anchor: .top) }
                    }
                }
            }
        }
        .navigationTitle(style?.name ?? "Style")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
        .sheet(item: $formalKind) { kind in
            FormalImportView(kind: kind, styleID: styleID) { Task { await load() } }
        }
        .confirmationDialog("Remove all formal writing from this style?", isPresented: $confirmClearFormal,
                            titleVisibility: .visible) {
            Button("Remove formal writing", role: .destructive) { Task { await clearFormal() } }
        }
        .confirmationDialog("Delete this style?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete style", role: .destructive) { Task { await delete() } }
        }
        .task { await load() }
    }

    @ViewBuilder
    private var content: some View {
        if let style {
            VStack(alignment: .leading, spacing: 28) {
                summary(style)
                if let scores = style.scores, !(scores.samples ?? []).isEmpty || scores.note != nil {
                    samples(scores)
                }
                audienceSection(style)
                formalSection(style)
                learnedSection(style)
                rulesSection(style)
                if style.id != "main" {
                    Button(role: .destructive) { confirmDelete = true } label: {
                        Label("Delete style", systemImage: "trash")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.red)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(Color.red.opacity(0.08), in: .capsule)
                    }
                    .buttonStyle(.plain)
                }
            }
        } else if let error {
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                Text(error).font(.footnote)
                Spacer(minLength: 0)
            }
            .glassCard(padding: 12)
        } else {
            ProgressView()
                .frame(maxWidth: .infinity)
                .padding(.top, 80)
        }
    }

    // MARK: Summary and self-check

    private func summary(_ style: Style) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            StyleHeroCard(style: style, isActive: style.id == activeID)
            if style.id == activeID {
                Label("The keyboard and shortcut write in this style", systemImage: "checkmark.circle.fill")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.accentColor)
            } else if style.isReady {
                Button("Use this style") {
                    SharedStore.styleID = style.id
                    SharedStore.styleName = style.name
                    activeID = style.id
                }
                .buttonStyle(PrimaryButtonStyle())
            }
            if let source = learnedFrom(style) {
                HStack(spacing: 10) {
                    StyleIconTile(icon: "tray.full.fill", gradient: StylePalette.messages, size: 34)
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Learned from").font(.caption).foregroundStyle(.secondary)
                        Text(source).font(Theme.label(14))
                    }
                    Spacer(minLength: 0)
                }
                .glassCard(padding: 12)
            }
        }
    }

    private func learnedFrom(_ style: Style) -> String? {
        if let counts = style.counts {
            return "\(counts["turns"] ?? 0) messages in \(counts["chats"] ?? 0) chats"
        }
        return style.source
    }

    private func samples(_ scores: StyleScores) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "Self-check", subtitle: loraNote(scores.checked))
            VStack(alignment: .leading, spacing: 14) {
                ForEach(scores.samples ?? [], id: \.self) { sample in
                    VStack(alignment: .leading, spacing: 6) {
                        Text("SAYSO").font(Theme.label(10)).tracking(1).foregroundStyle(.secondary)
                        StyleBubble(text: sample.suggested, mine: false)
                        Text("YOU, FOR REAL").font(Theme.label(10)).tracking(1).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .trailing)
                        StyleBubble(text: sample.real)
                    }
                }
                if let note = scores.note {
                    Text(note).font(.footnote).foregroundStyle(.secondary)
                }
            }
            .glassCard(radius: 20, padding: 16)
        }
    }

    private func loraNote(_ checked: Int?) -> String {
        let prefix = checked.map { "Checked on \($0) of your real replies it hadn't seen. " } ?? ""
        switch style?.lora {
        case "ready": return prefix + "This style has its own model."
        case "training": return prefix + "Its own model is training; until then Muse Spark writes in this style."
        case "waiting for GPU": return prefix + "Its own model will train when the GPU is on; until then Muse Spark writes in this style."
        default: return prefix + "Add more chats for this style to get its own model."
        }
    }

    // MARK: Audiences

    private func audiences(_ style: Style) -> [Audience] {
        Audience.allCases.filter { style.profile?[$0.rawValue] != nil }
    }

    private func audienceSection(_ style: Style) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "By who you're talking to",
                               subtitle: "How your messages change with each kind of person.")
            let list = audiences(style)
            if list.isEmpty {
                Text("No audiences yet. Add chats and SaySo learns how you write to each kind of person.")
                    .font(.footnote).foregroundStyle(.secondary)
                    .glassCard(radius: 20, padding: 16)
            }
            ForEach(list) { audience in
                if let profile = style.profile?[audience.rawValue] {
                    StyleAudienceDetail(audience: audience, profile: profile,
                                        examples: style.examples?[audience.rawValue] ?? [])
                        .id(audience.rawValue)
                }
            }
        }
    }

    // MARK: Formal writing

    private func formalSection(_ style: Style) -> some View {
        let formal = style.formal
        let emails = formal?.counts?["email"] ?? 0
        let essays = formal?.counts?["essay"] ?? 0
        let hasFormal = (formal?.paragraphs ?? 0) > 0
        return VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "Formal writing",
                               subtitle: "Emails, essays and papers you wrote yourself. Official messages, emails and essays then sound like your formal self, not a generic polite AI.")
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 10) {
                    StyleStat(value: emails, label: emails == 1 ? "email" : "emails", icon: "envelope.fill")
                    StyleStat(value: essays, label: essays == 1 ? "essay or document" : "essays & documents", icon: "doc.text.fill")
                }
                if hasFormal, let profile = formal?.profile {
                    formalProfile(profile)
                }
                HStack(spacing: 10) {
                    formalButton("Add emails", icon: "envelope") { formalKind = .email }
                    formalButton("Add essays", icon: "doc.text") { formalKind = .essay }
                }
                if hasFormal {
                    Button(role: .destructive) { confirmClearFormal = true } label: {
                        Text("Remove all formal writing").font(.footnote.weight(.semibold)).foregroundStyle(.red)
                    }
                    .buttonStyle(.plain)
                    .frame(maxWidth: .infinity)
                }
            }
            .glassCard(radius: 20, padding: 16)
            Text(".txt, .docx, .pdf, screenshots, or paste.").font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func formalProfile(_ profile: FormalProfile) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let words = profile.sentenceWords {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text("~\(Int(words.rounded()))").font(Theme.display(22)).foregroundStyle(Theme.navy)
                    Text("words per sentence").font(.caption).foregroundStyle(.secondary)
                    if let paragraph = profile.paragraphWords {
                        Text("· ~\(Int(paragraph.rounded())) per paragraph").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            if let connectors = profile.connectors, !connectors.isEmpty {
                chips(title: "Links ideas with", items: connectors, icon: nil)
            }
            if let openings = profile.openings, !openings.isEmpty {
                chips(title: "Opens with", items: openings, icon: "text.quote")
            }
            if let closings = profile.closings, !closings.isEmpty {
                chips(title: "Signs off with", items: closings, icon: "signature")
            }
        }
    }

    private func chips(title: String, items: [String], icon: String?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            StyleFlowLayout(spacing: 6) {
                ForEach(items, id: \.self) { item in
                    StyleChip(text: item, icon: icon)
                }
            }
        }
    }

    private func formalButton(_ title: String, icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(title, systemImage: icon)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.accentColor)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
                .background(Color.accentColor.opacity(0.1), in: .capsule)
        }
        .buttonStyle(.plain)
    }

    // MARK: Learned from you

    @ViewBuilder
    private func learnedSection(_ style: Style) -> some View {
        if let learning = style.learning {
            VStack(alignment: .leading, spacing: 12) {
                StyleSectionHeader(title: "Learned from you",
                                   subtitle: "Your newest messages are used as examples first, so suggestions follow how you write now.")
                HStack(spacing: 10) {
                    StyleStat(value: learning.typed, label: "sent with the keyboard", icon: "keyboard")
                    StyleStat(value: learning.edited, label: "suggestions you changed", icon: "pencil")
                    StyleStat(value: learning.liked, label: "answers you liked", icon: "hand.thumbsup")
                }
                if !learning.recent.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(learning.recent) { message in
                            learnedRow(message)
                        }
                    }
                    .glassCard(radius: 20, padding: 14)
                }
            }
        }
    }

    private func learnedRow(_ message: LearnedMessage) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Button { Task { await forgetLearned(message.id) } } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.body)
                    .foregroundStyle(.tertiary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Delete")
            VStack(alignment: .trailing, spacing: 4) {
                StyleBubble(text: message.text)
                if let suggested = message.suggested {
                    Text("instead of: \(StylePalette.oneLine(suggested))")
                        .font(.caption).foregroundStyle(.secondary).strikethrough()
                        .multilineTextAlignment(.trailing)
                }
                Text(audienceLabel(message.audience))
                    .font(.caption2).foregroundStyle(.tertiary)
            }
            .frame(maxWidth: .infinity, alignment: .trailing)
        }
        .contextMenu {
            Button(role: .destructive) { Task { await forgetLearned(message.id) } } label: {
                Label("Delete", systemImage: "trash")
            }
        }
    }

    private func audienceLabel(_ raw: String) -> String {
        guard let audience = Audience(rawValue: raw) else { return raw }
        return "\(StylePalette.emoji(audience)) \(audience.label)"
    }

    // MARK: Learned from corrections

    private func rulesSection(_ style: Style) -> some View {
        let rules = style.preferences ?? []
        return VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "Learned from your corrections")
            VStack(alignment: .leading, spacing: 10) {
                if rules.isEmpty {
                    Text("Nothing yet. Fix answers in Chat (\u{201C}shorter\u{201D}, \u{201C}no emoji\u{201D}) and SaySo remembers what you prefer.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                ForEach(Array(rules.enumerated()), id: \.offset) { index, rule in
                    ruleRow(rule, index: index)
                }
            }
            .glassCard(radius: 20, padding: 14)
        }
    }

    private func ruleRow(_ rule: String, index: Int) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "sparkles")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.accentColor)
            Text(rule).font(.subheadline).frame(maxWidth: .infinity, alignment: .leading)
            Button { Task { await forget(index) } } label: {
                Text("Forget")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.red)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Color.red.opacity(0.08), in: .capsule)
            }
            .buttonStyle(.plain)
        }
        .contextMenu {
            Button(role: .destructive) { Task { await forget(index) } } label: {
                Label("Forget", systemImage: "trash")
            }
        }
    }

    // MARK: Actions

    private func load() async {
        do {
            style = try await SaySoAPI.style(styleID)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func clearFormal() async {
        if let updated = try? await SaySoAPI.updateStyle(styleID, clearDocuments: true) { style = updated }
        onChange()
    }

    private func forgetLearned(_ id: String) async {
        if let updated = try? await SaySoAPI.updateStyle(styleID, removeLearned: id) { style = updated }
        onChange()
    }

    private func forget(_ index: Int) async {
        if let updated = try? await SaySoAPI.updateStyle(styleID, removePreference: index) { style = updated }
        onChange()
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
