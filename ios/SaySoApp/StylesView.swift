import SwiftUI

/// My styles: every way of writing SaySo has learned, the active one checked. Add one from chats, delete one.
struct StylesView: View {
    @State private var styles: [Style] = []
    @State private var activeID = SharedStore.styleID
    @State private var adding = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(styles) { style in
                        NavigationLink(value: style) { StyleRow(style: style, isActive: style.id == activeID) }
                            .swipeActions(edge: .leading) {
                                if style.isReady && style.id != activeID {
                                    Button("Use") { use(style) }.tint(.accentColor)
                                }
                            }
                            .swipeActions(edge: .trailing) {
                                if style.id != "main" {
                                    Button("Delete", role: .destructive) { Task { await delete(style) } }
                                }
                            }
                    }
                } footer: {
                    Text("The checked style is the one the keyboard and the Back Tap shortcut write in. Swipe right to use a style, left to delete it.")
                }
                if let error {
                    Text(error).foregroundStyle(.red).font(.footnote)
                }
            }
            .navigationTitle("My styles")
            .navigationDestination(for: Style.self) { style in
                StyleCardView(styleID: style.id, activeID: $activeID) { Task { await load() } }
            }
            .toolbar {
                Button { adding = true } label: { Label("Add style", systemImage: "plus") }
            }
            .sheet(isPresented: $adding, onDismiss: { Task { await load() } }) {
                AddStyleView { style in
                    use(style)
                    adding = false
                }
            }
            .refreshable { await load() }
            .task { await poll() }
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

struct StyleRow: View {
    let style: Style
    let isActive: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: isActive ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(isActive ? Color.accentColor : .secondary)
                .font(.title3)
            VStack(alignment: .leading, spacing: 4) {
                Text(style.name).font(.headline)
                if style.isBuilding, style.stage != "training" {
                    ProgressView(value: style.progress ?? 0) { Text(StageInfo.title(style.stage)).font(.caption) }
                } else if style.status == "failed" {
                    Text(style.error ?? "Couldn't build this style.").font(.caption).foregroundStyle(.red)
                } else {
                    Text(summary).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 2)
    }

    private var summary: String {
        var parts: [String] = []
        if let score = style.scores?.soundsLikeYou { parts.append("sounds like you \(Int(score * 100))%") }
        if let sense = style.scores?.makesSense { parts.append(String(format: "makes sense %.1f/5", sense)) }
        if style.stage == "training" { parts.append("training its own model…") }
        else if style.adapterReady == true { parts.append("own model") }
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
