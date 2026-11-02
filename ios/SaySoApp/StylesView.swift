import SwiftUI

/// Where a tap in the Styles tab leads: a style's card, optionally scrolled to one audience.
struct StyleRoute: Hashable {
    let id: String
    var focus: Audience? = nil
}

/// Your voice: the style in use (how much it sounds like you), split by kind of text and by who you talk to,
/// what SaySo learned from you, your other styles and ways to teach it more.
struct StylesView: View {
    @State private var styles: [Style] = []
    @State private var activeID = SharedStore.styleID
    @State private var detail: Style?
    @State private var loadingDetail = false
    @State private var adding = false
    @State private var formal: FormalKind?
    @State private var error: String?
    @State private var path: [StyleRoute] = []

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
            .task { await poll() }
            .task(id: activeID) { await loadDetail() }
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 28) {
            header
            if let error {
                errorCard(error)
            }
            if let active {
                StyleHeroCard(style: mergedHero(active), isActive: active.id == activeID) {
                    path.append(StyleRoute(id: active.id))
                }
                kinds(active)
                audiences
                learned
            } else if error == nil {
                loadingCard
            }
            if !others.isEmpty { otherStyles }
            teach
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

    // MARK: By kind of text

    private func kinds(_ style: Style) -> some View {
        let turns = full?.counts?["turns"] ?? style.counts?["turns"] ?? 0
        let chats = full?.counts?["chats"] ?? style.counts?["chats"] ?? 0
        let typed = full?.learning?.typed ?? 0
        let formalCounts = full?.formal?.counts ?? style.formal?.counts ?? [:]
        let emails = formalCounts["email"] ?? 0
        let essays = formalCounts["essay"] ?? 0
        var messageDetail: String = chats > 0 ? "from \(chats) chats" : "from your chats"
        if typed > 0 { messageDetail += " + \(typed) typed" }
        return VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "By kind of text", subtitle: "Chats teach your messages; your own emails and essays teach your formal voice.")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 14) {
                    StyleKindCard(icon: "bubble.left.and.bubble.right.fill", gradient: StylePalette.messages,
                                  title: "Messages", count: turns + typed, unit: "messages", detail: messageDetail,
                                  status: style.isBuilding ? StageInfo.title(style.stage) : "Ready") {
                        if turns + typed > 0 { path.append(StyleRoute(id: style.id)) } else { adding = true }
                    }
                    StyleKindCard(icon: "envelope.fill", gradient: StylePalette.emails,
                                  title: "Emails", count: emails, unit: emails == 1 ? "email" : "emails",
                                  detail: emails > 0 ? "greetings, asks, sign-offs" : "How you greet, ask and sign off",
                                  status: "Ready") {
                        if emails > 0 { path.append(StyleRoute(id: style.id)) } else { formal = .email }
                    }
                    StyleKindCard(icon: "doc.text.fill", gradient: StylePalette.essays,
                                  title: "Essays & documents", count: essays, unit: essays == 1 ? "text" : "texts",
                                  detail: essays > 0 ? "your longer, formal voice" : "Your formal voice for longer texts",
                                  status: "Ready") {
                        if essays > 0 { path.append(StyleRoute(id: style.id)) } else { formal = .essay }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 10)
            }
            .padding(.horizontal, -20)
            .padding(.vertical, -10)
        }
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

    private var learned: some View {
        let rules = full?.preferences ?? []
        let learning = full?.learning
        return VStack(alignment: .leading, spacing: 12) {
            StyleSectionHeader(title: "SaySo learned from you",
                               subtitle: "From your fixes in Chat and what you type with the keyboard.")
            VStack(alignment: .leading, spacing: 14) {
                if rules.isEmpty {
                    Text("No rules yet. Tell an answer in Chat \u{201C}shorter\u{201D} or \u{201C}no emoji\u{201D} and SaySo remembers.")
                        .font(.footnote).foregroundStyle(.secondary)
                } else {
                    StyleFlowLayout(spacing: 8) {
                        ForEach(Array(rules.enumerated()), id: \.offset) { index, rule in
                            StyleChip(text: rule, icon: "sparkles")
                                .contextMenu {
                                    Button(role: .destructive) { Task { await forget(index) } } label: {
                                        Label("Forget", systemImage: "trash")
                                    }
                                }
                        }
                    }
                }
                HStack(spacing: 10) {
                    StyleStat(value: learning?.typed ?? 0, label: "sent with the keyboard", icon: "keyboard")
                    StyleStat(value: learning?.edited ?? 0, label: "suggestions you changed", icon: "pencil")
                    StyleStat(value: learning?.liked ?? 0, label: "answers you liked", icon: "hand.thumbsup")
                }
            }
            .glassCard(radius: 20, padding: 16)
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

    private var teach: some View {
        VStack(alignment: .leading, spacing: 10) {
            StyleSectionHeader(title: "Teach SaySo more")
            TeachCard(icon: "bubble.left.and.bubble.right.fill", title: "Add chat exports",
                      detail: "WhatsApp, Telegram, Instagram, screenshots", gradient: StylePalette.messages) { adding = true }
            TeachCard(icon: "envelope.fill", title: "Add your emails",
                      detail: "How you greet, ask and sign off", gradient: StylePalette.emails) { formal = .email }
            TeachCard(icon: "doc.text.fill", title: "Add essays & documents",
                      detail: "Your formal voice, from your own texts", gradient: StylePalette.essays) { formal = .essay }
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
