import SwiftUI

/// Where a tap in the Styles tab leads: a style's card, optionally scrolled to one audience.
struct StyleRoute: Hashable {
    let id: String
    var focus: Audience? = nil
}

/// Your voice: the style in use, one section per kind of text. Messages: how much it sounds like you and how you
/// write to each kind of person; Emails: greetings, sign-offs, tone and length; Essays: structure and voice. Lists the
/// user edits by hand (greetings, sign-offs, phrases they never use) are saved on the server.
struct StylesView: View {
    @State private var styles: [Style] = []
    @State private var activeID = SharedStore.styleID
    @State private var detail: Style?
    @State private var loadingDetail = false
    @State private var adding = false
    @State private var formal: FormalKind?
    @State private var error: String?
    @State private var path: [StyleRoute] = []
    @State private var kind: StyleKind = .messages
    @State private var editing: CustomList?

    /// The style in use, from the list (fresh status and progress).
    private var active: Style? { styles.first { $0.id == activeID } ?? styles.first }

    /// The full active style (profile, examples, formal writing, learning) once it has loaded.
    private var full: Style? {
        guard let detail, detail.id == active?.id else { return nil }
        return detail
    }

    private var others: [Style] { styles.filter { $0.id != active?.id } }

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                Theme.backdrop
                ScrollView {
                    content
                        .padding(.horizontal, 20)
                        .padding(.top, 8)
                        .padding(.bottom, 32)
                }
                .refreshable { await load() }
            }
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: StyleRoute.self) { route in
                StyleCardView(styleID: route.id, activeID: $activeID, focus: route.focus) { Task { await load() } }
            }
            .sheet(isPresented: $adding, onDismiss: { Task { await load() } }) {
                AddStyleView { style in
                    use(style)
                    adding = false
                }
            }
            .sheet(item: $formal) { kind in
                FormalImportView(kind: kind) { Task { await load() } }
            }
            .sheet(item: $editing) { list in
                if let full {
                    CustomListEditor(list: list, styleID: full.id, items: full.shownItems(list),
                                     defaultItem: full.customDefault(list), parsed: full.parsedItems(list),
                                     canReset: full.customItems(list) != nil) { saved in
                        detail = saved
                    }
                }
            }
            .task { await poll() }
            .task(id: activeID) { await loadDetail() }
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 24) {
            header
            if let error {
                errorCard(error)
            }
            if let active {
                StyleKindTabs(selection: $kind, counts: counts(active))
                section(active)
                    .id(kind)
                    .transition(.opacity)
            } else if error == nil {
                loadingCard
            }
            if !others.isEmpty { otherStyles }
        }
    }

    @ViewBuilder
    private func section(_ style: Style) -> some View {
        switch kind {
        case .messages: messages(style)
        case .emails: emails(style)
        case .essays: essays(style)
        }
    }

    // MARK: Header

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text("Your voice").font(Theme.title(34)).foregroundStyle(.primary)
                Spacer(minLength: 8)
            }
            switcher
        }
        .padding(.top, 8)
    }

    /// The style in use as a pill; the menu switches styles or adds chats, emails and essays.
    private var switcher: some View {
        Menu {
            Section("Write as") {
                ForEach(styles) { style in
                    Button { use(style) } label: {
                        if style.id == active?.id {
                            Label(style.name, systemImage: "checkmark")
                        } else {
                            Text(style.name)
                        }
                    }
                    .disabled(!style.isReady)
                }
            }
            Section {
                Button { adding = true } label: {
                    Label("New style from chats…", systemImage: "bubble.left.and.bubble.right")
                }
                Button { formal = .email } label: { Label("Add emails", systemImage: "envelope") }
                Button { formal = .essay } label: { Label("Add essays", systemImage: "doc.text") }
            }
        } label: {
            HStack(spacing: 8) {
                Circle().fill(Theme.accentGradient).frame(width: 10, height: 10)
                Text(active?.name ?? SharedStore.styleName)
                    .font(Theme.label(15))
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(Color.accentColor)
            }
            .padding(.horizontal, 14).padding(.vertical, 9)
            .background(.regularMaterial, in: .capsule)
            .overlay(Capsule().stroke(Color.accentColor.opacity(0.25)))
            .shadow(color: Theme.glow.opacity(0.2), radius: 8, y: 3)
        }
    }

    /// Scores and status come from the list (refreshed while building); the detail may have scores the list lacks.
    private func mergedHero(_ style: Style) -> Style {
        var merged = style
        if merged.scores == nil, let full { merged.scores = full.scores }
        return merged
    }

    // MARK: Kinds of text

    private func formalCount(_ style: Style, _ key: String) -> Int {
        (full?.formal?.counts ?? style.formal?.counts ?? [:])[key] ?? 0
    }

    private func messageCount(_ style: Style) -> Int {
        (full?.counts?["turns"] ?? style.counts?["turns"] ?? 0) + (full?.learning?.typed ?? 0)
    }

    private func counts(_ style: Style) -> [StyleKind: Int] {
        [.messages: messageCount(style), .emails: formalCount(style, "email"), .essays: formalCount(style, "essay")]
    }

    /// The traits of one formal kind on its own; the mixed profile when the server doesn't split them.
    private func formalProfile(_ key: String) -> FormalProfile? {
        full?.formal?.kinds?[key] ?? full?.formal?.profile
    }

    private func messages(_ style: Style) -> some View {
        VStack(alignment: .leading, spacing: 28) {
            StyleHeroCard(style: mergedHero(style), isActive: style.id == activeID) {
                path.append(StyleRoute(id: style.id))
            }
            audiences
            listSection(title: "Your words", subtitle: "Words and phrases SaySo should never put in your messages.",
                        lists: [.messageAvoid])
            learned(.messages)
            TeachCard(icon: "bubble.left.and.bubble.right.fill", title: "Add chat exports",
                      detail: "WhatsApp, Telegram, Instagram, screenshots", gradient: StylePalette.messages) { adding = true }
        }
    }

    private func emails(_ style: Style) -> some View {
        let count = formalCount(style, "email")
        return VStack(alignment: .leading, spacing: 28) {
            if count > 0 {
                KindSummaryCard(kind: .emails, count: count, unit: count == 1 ? "email" : "emails",
                                line: "SaySo writes your emails with your greeting, your sign-off and your tone.")
                if let profile = formalProfile("email") {
                    VStack(alignment: .leading, spacing: 12) {
                        StyleSectionHeader(title: "Tone & length", subtitle: "How your own emails read.")
                        FormalTraitsCard(kind: .email, profile: profile)
                    }
                } else if loadingDetail {
                    detailLoading
                }
            } else {
                KindEmptyState(kind: .emails, title: "Teach me your emails",
                               detail: "Add a few emails you sent yourself. SaySo learns how you greet, ask and sign off, so its emails sound like you, not like a polite robot.",
                               button: "Add emails") { formal = .email }
            }
            listSection(title: "Greetings & sign-offs",
                        subtitle: "Edit them, put them in order and pick a default. SaySo uses yours, in the email's language.",
                        lists: [.openers, .signoffs])
            listSection(title: "Your words", subtitle: "Phrases SaySo should never put in your emails.", lists: [.emailAvoid])
            learned(.emails)
            if count > 0 {
                TeachCard(icon: "envelope.fill", title: "Add more emails",
                          detail: "How you greet, ask and sign off", gradient: StylePalette.emails) { formal = .email }
            }
        }
    }

    private func essays(_ style: Style) -> some View {
        let count = formalCount(style, "essay")
        return VStack(alignment: .leading, spacing: 28) {
            if count > 0 {
                KindSummaryCard(kind: .essays, count: count, unit: count == 1 ? "text" : "texts",
                                line: "Essays and papers you wrote teach SaySo your longer, formal voice: never your topics.")
                if let profile = formalProfile("essay") {
                    VStack(alignment: .leading, spacing: 12) {
                        StyleSectionHeader(title: "Structure & voice", subtitle: "How your own essays are built.")
                        FormalTraitsCard(kind: .essay, profile: profile)
                    }
                } else if loadingDetail {
                    detailLoading
                }
            } else {
                KindEmptyState(kind: .essays, title: "Teach me your essays",
                               detail: "Add essays, papers or documents you wrote. SaySo learns your sentence length, linking words and how direct you are.",
                               button: "Add essays") { formal = .essay }
            }
            listSection(title: "Your words", subtitle: "Phrases SaySo should never put in your essays.", lists: [.essayAvoid])
            learned(.essays)
            if count > 0 {
                TeachCard(icon: "doc.text.fill", title: "Add more essays & documents",
                          detail: "Your formal voice, from your own texts", gradient: StylePalette.essays) { formal = .essay }
            }
        }
    }

    /// Lists the user edits by hand, once the full style has loaded.
    private func listSection(title: String, subtitle: String, lists: [CustomList]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: title, subtitle: subtitle)
            if let full {
                ForEach(lists) { list in
                    CustomListCard(list: list, items: full.shownItems(list), defaultItem: full.customDefault(list),
                                   isCustom: full.customItems(list) != nil) { editing = list }
                }
            } else {
                detailLoading
            }
        }
    }

    private var detailLoading: some View {
        HStack { Spacer(); ProgressView(); Spacer() }
            .glassCard(radius: 20, padding: 28)
    }

    // MARK: By who you're talking to

    private var audiences: some View {
        VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "By who you're talking to",
                               subtitle: "Same you, different habits. Tap one to see all of it.")
            if let full {
                let list = audienceList(full)
                if list.isEmpty {
                    emptyAudiences
                } else {
                    audienceGrid(list, style: full)
                }
            } else if loadingDetail {
                HStack { Spacer(); ProgressView(); Spacer() }
                    .glassCard(radius: 20, padding: 28)
            } else {
                emptyAudiences
            }
        }
    }

    private func audienceList(_ style: Style) -> [Audience] {
        Audience.allCases.filter { style.profile?[$0.rawValue] != nil }
    }

    private func audienceGrid(_ list: [Audience], style: Style) -> some View {
        let rows: [[Audience]] = stride(from: 0, to: list.count, by: 2).map { start in
            Array(list[start..<min(start + 2, list.count)])
        }
        return VStack(spacing: 12) {
            ForEach(rows, id: \.self) { row in
                HStack(alignment: .top, spacing: 12) {
                    ForEach(row) { audience in
                        audienceCell(audience, style: style)
                    }
                    if row.count == 1 {
                        Color.clear.frame(maxWidth: .infinity)
                    }
                }
                .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    @ViewBuilder
    private func audienceCell(_ audience: Audience, style: Style) -> some View {
        if let profile = style.profile?[audience.rawValue] {
            Button {
                path.append(StyleRoute(id: style.id, focus: audience))
            } label: {
                StyleAudienceCard(audience: audience, profile: profile,
                                  example: style.examples?[audience.rawValue]?.first)
            }
            .buttonStyle(.plain)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var emptyAudiences: some View {
        HStack(spacing: 14) {
            Text("💬").font(.system(size: 28))
            VStack(alignment: .leading, spacing: 4) {
                Text("No audiences yet").font(Theme.label(15))
                Text("Add chats with friends, family or your partner and SaySo learns how you write to each.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .glassCard(radius: 20, padding: 16)
        .onTapGesture { adding = true }
    }

    // MARK: Learned

    /// Rules learned from fixes in Chat, each under its kind: email and essay rules start "In emails…" / "In essays…".
    private func learnedRules(for kind: StyleKind) -> [LearnedRule] {
        (full?.preferences ?? []).enumerated().compactMap { index, rule in
            let ruleKind: StyleKind = rule.hasPrefix("In emails") ? .emails : (rule.hasPrefix("In essays") ? .essays : .messages)
            return ruleKind == kind ? LearnedRule(index: index, text: rule) : nil
        }
    }

    @ViewBuilder
    private func learned(_ kind: StyleKind) -> some View {
        let rules = learnedRules(for: kind)
        if kind == .messages {
            let learning = full?.learning
            VStack(alignment: .leading, spacing: 12) {
                StyleSectionHeader(title: "SaySo learned from you",
                                   subtitle: "From your fixes in Chat and what you type with the keyboard.")
                VStack(alignment: .leading, spacing: 14) {
                    if rules.isEmpty {
                        Text("No rules yet. Tell an answer in Chat \u{201C}shorter\u{201D} or \u{201C}no emoji\u{201D} and SaySo remembers.")
                            .font(.footnote).foregroundStyle(.secondary)
                    } else {
                        ruleChips(rules)
                    }
                    HStack(spacing: 10) {
                        StyleStat(value: learning?.typed ?? 0, label: "sent with the keyboard", icon: "keyboard")
                        StyleStat(value: learning?.edited ?? 0, label: "suggestions you changed", icon: "pencil")
                        StyleStat(value: learning?.liked ?? 0, label: "answers you liked", icon: "hand.thumbsup")
                    }
                }
                .glassCard(radius: 20, padding: 16)
            }
        } else if !rules.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                StyleSectionHeader(title: "Learned from your fixes",
                                   subtitle: "Touch and hold a rule to forget it.")
                ruleChips(rules)
                    .glassCard(radius: 20, padding: 16)
            }
        }
    }

    private func ruleChips(_ rules: [LearnedRule]) -> some View {
        StyleFlowLayout(spacing: 8) {
            ForEach(rules) { item in
                StyleChip(text: item.text, icon: "sparkles")
                    .contextMenu {
                        Button(role: .destructive) { Task { await forget(item.index) } } label: {
                            Label("Forget", systemImage: "trash")
                        }
                    }
            }
        }
    }

    // MARK: Other styles and teaching

    private var otherStyles: some View {
        VStack(alignment: .leading, spacing: 10) {
            StyleSectionHeader(title: "Other styles")
            ForEach(others) { style in
                Button { path.append(StyleRoute(id: style.id)) } label: {
                    StyleRow(style: style, isActive: false)
                }
                .buttonStyle(.plain)
                .contextMenu {
                    if style.isReady {
                        Button { use(style) } label: { Label("Use this style", systemImage: "checkmark.circle") }
                    }
                    if style.id != "main" {
                        Button(role: .destructive) { Task { await delete(style) } } label: {
                            Label("Delete", systemImage: "trash")
                        }
                    }
                }
            }
            Text("Touch and hold a style to use or delete it. The one in use is what the keyboard and Back Tap write in.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func errorCard(_ message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
            Text(message).font(.footnote).foregroundStyle(.primary)
            Spacer(minLength: 0)
        }
        .glassCard(padding: 12)
    }

    private var loadingCard: some View {
        VStack(spacing: 10) {
            ProgressView()
            Text("Loading your styles…").font(.footnote).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .glassCard(radius: 20, padding: 32)
    }

    // MARK: Actions

    private func use(_ style: Style) {
        SharedStore.styleID = style.id
        SharedStore.styleName = style.name
        activeID = style.id
    }

    private func load() async {
        do {
            styles = try await SaySoAPI.styles()
            error = nil
            if !styles.contains(where: { $0.id == activeID && $0.isReady }), let main = styles.first {
                use(main)
            }
        } catch {
            self.error = error.localizedDescription
        }
        await loadDetail()
    }

    /// The active style's profile, examples, formal writing and learning (the list leaves them out).
    private func loadDetail() async {
        let id: String
        if let current = active?.id {
            id = current
        } else if styles.isEmpty {
            id = activeID
        } else {
            return
        }
        if detail?.id != id { loadingDetail = true }
        defer { loadingDetail = false }
        if let style = try? await SaySoAPI.style(id), style.id == (active?.id ?? id) {
            detail = style
        }
    }

    /// Refreshes while a style is still being built (the stages change every few seconds).
    private func poll() async {
        await load()
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(styles.contains(where: \.isBuilding) ? 3 : 30))
            await load()
        }
    }

    private func delete(_ style: Style) async {
        do {
            try await SaySoAPI.deleteStyle(style.id)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func forget(_ index: Int) async {
        guard let id = full?.id else { return }
        if let style = try? await SaySoAPI.updateStyle(id, removePreference: index) {
            detail = style
        }
    }
}

/// A rule learned from the user's fixes in Chat; index = its place in the style's preferences (to forget it).
struct LearnedRule: Identifiable {
    let index: Int
    let text: String
    var id: Int { index }
}

enum StageInfo {
    static let order = ["parsing", "needs_me", "reading", "profile", "checking", "training", "ready"]

    static func title(_ stage: String?) -> String {
        switch stage {
        case "uploading": "Uploading…"
        case "parsing": "Reading your files…"
        case "needs_me": "Waiting for you"
        case "reading": "Learning how you react…"
        case "profile": "Building your profile…"
        case "checking": "Self-check: writing test replies…"
        case "training": "Training your own model…"
        case "ready": "Ready"
        case "failed": "Failed"
        default: "Working…"
        }
    }
}
