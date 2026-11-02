import SwiftUI

/// My styles: every way of writing SaySo has learned, the active one checked. Add one from chats, delete one.
struct StylesView: View {
    @State private var styles: [Style] = []
    @State private var activeID = SharedStore.styleID
    @State private var adding = false
    @State private var formal: FormalKind?
    @State private var error: String?
    @State private var path: [Style] = []

    private var active: Style? { styles.first { $0.id == activeID } ?? styles.first }

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                Theme.backdrop
                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Styles").font(.system(size: 36, weight: .bold))
                            Text("Which one is you?").font(.title3).foregroundStyle(.secondary)
                        }
                        if let active { hero(active) }
                        if styles.count > 0 { topStyles }
                        teach
                        if let error {
                            Text(error).foregroundStyle(.red).font(.footnote)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 12)
                }
            }
            .navigationDestination(for: Style.self) { style in
                StyleCardView(styleID: style.id, activeID: $activeID) { Task { await load() } }
            }
            .toolbar {
                Menu {
                    Button { adding = true } label: {
                        Label("Messages (chats)", systemImage: "bubble.left.and.bubble.right")
                    }
                    Button { formal = .email } label: { Label("Emails", systemImage: "envelope") }
                    Button { formal = .essay } label: { Label("Essays & documents", systemImage: "doc.text") }
                } label: {
                    Label("Add", systemImage: "plus")
                }
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
            .refreshable { await load() }
            .task { await poll() }
        }
    }

    /// The active style: how much it sounds like the user, whether it makes sense, and where to open it.
    private func hero(_ style: Style) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(style.name).font(.headline)
                Spacer()
                Text(style.id == activeID ? "In use" : "Ready")
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .foregroundStyle(Color.accentColor)
                    .background(Color.accentColor.opacity(0.12), in: .capsule)
            }
            if let you = style.scores?.soundsLikeYou {
                ScoreCard(title: "Sounds like you", value: "\(Int(you * 100))%",
                          detail: style.scores?.generic.map { "(generic AI \(Int($0 * 100))%)" })
            }
            if let sense = style.scores?.makesSense {
                ScoreCard(title: "Makes sense", value: String(format: "%.1f / 5", sense), trend: false)
            }
            if style.isBuilding {
                ProgressView(value: style.progress ?? 0) { Text(StageInfo.title(style.stage)).font(.caption) }
            }
            Button("Open this style") { path.append(style) }
                .buttonStyle(PrimaryButtonStyle())
        }
        .glassCard(radius: 20, padding: 16)
    }

    private var topStyles: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionTitle(text: "Your styles")
            ForEach(styles) { style in
                Button { path.append(style) } label: { StyleRow(style: style, isActive: style.id == activeID) }
                    .buttonStyle(.plain)
                    .contextMenu {
                        if style.isReady && style.id != activeID {
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

    /// The three ways to teach SaySo more, as cards.
    private var teach: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionTitle(text: "Teach SaySo more")
            TeachCard(icon: "bubble.left.and.bubble.right.fill", title: "Add chat exports",
                      detail: "WhatsApp, Telegram, Instagram, screenshots") { adding = true }
            TeachCard(icon: "envelope.fill", title: "Add your emails", detail: "How you greet, ask and sign off") {
                formal = .email
            }
            TeachCard(icon: "doc.text.fill", title: "Add essays & documents", detail: "Your formal voice, from your own texts") {
                formal = .essay
            }
        }
    }

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
}

struct TeachCard: View {
    let icon: String
    let title: String
    let detail: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(Theme.accentGradient, in: .rect(cornerRadius: Theme.card))
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                    Text(detail).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "plus.circle.fill").font(.title3).foregroundStyle(Color.accentColor)
            }
            .glassCard(padding: 12)
        }
        .buttonStyle(.plain)
    }
}

struct StyleRow: View {
    let style: Style
    let isActive: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: isActive ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(isActive ? Color.accentColor : .secondary)
                .font(.title3)
            VStack(alignment: .leading, spacing: 4) {
                Text(style.name).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                if style.isBuilding, style.stage != "training" {
                    ProgressView(value: style.progress ?? 0) { Text(StageInfo.title(style.stage)).font(.caption) }
                } else if style.status == "failed" {
                    Text(style.error ?? "Couldn't build this style.").font(.caption).foregroundStyle(.red)
                } else {
                    Text(summary).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                }
            }
            Spacer()
            if let score = style.scores?.soundsLikeYou {
                Text("\(Int(score * 100))%")
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(Theme.navy)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Color.accentColor.opacity(0.12), in: .capsule)
            }
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .glassCard()
    }

    private var summary: String {
        var parts: [String] = []
        if let sense = style.scores?.makesSense { parts.append(String(format: "makes sense %.1f/5", sense)) }
        if style.stage == "training" { parts.append("training its own model…") }
        else if style.adapterReady == true { parts.append("Muse Spark Open writes in this style") }
        if parts.isEmpty { parts.append(style.source ?? "ready") }
        return parts.joined(separator: " · ")
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
