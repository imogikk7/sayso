import SwiftUI

/// The SaySo keyboard: a top strip (mode, audience, format, ✨) over letter keys or the panel; results replace both.
struct PanelView: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        VStack(spacing: 6) {
            strip
            if model.busy {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if !model.options.isEmpty {
                ResultsView(model: model)
            } else if model.mode == .letters {
                VStack(spacing: 4) {
                    if let message = model.message { status(message) }
                    LetterKeys(model: model)
                }
            } else {
                panel
            }
            Spacer(minLength: 0)
        }
        .padding(.top, 6)
        .tint(model.settings.accent.color)
        .dynamicTypeSize(.small ... .large)  // the keyboard has a fixed height; huge text sizes would push keys out
    }

    // MARK: Strip

    private var strip: some View {
        HStack(spacing: 6) {
            Button {
                model.mode = model.mode == .letters ? .panel : .letters
                model.closeResults()
            } label: {
                Image(systemName: model.mode == .letters ? "rectangle.grid.1x2" : "keyboard")
                    .frame(width: 34, height: 30)
                    .background(Color(.systemBackground), in: .capsule)
            }
            .buttonStyle(.plain)
            Menu {
                if !model.suggested.isEmpty {
                    Section("AI suggests") {
                        ForEach(model.suggested.filter(model.settings.audiences.contains)) { audience in
                            Button { model.audience = audience } label: { Label(audience.label, systemImage: "sparkles") }
                        }
                    }
                }
                Picker("Audience", selection: $model.audience) {
                    ForEach(model.settings.audiences) { Text($0.label).tag($0) }
                }
            } label: {
                chip(model.audience.label, systemImage: hint ? "sparkles" : "person.2", highlighted: hint)
            }
            Menu {
                Picker("Format", selection: $model.format) {
                    ForEach(model.settings.formats) { Label($0.label, systemImage: $0.systemImage).tag($0) }
                }
            } label: {
                chip(model.format.label, systemImage: model.format.systemImage, highlighted: false)
            }
            Spacer(minLength: 0)
            Button {
                if model.mode == .letters { model.sparkle() } else { model.run() }
            } label: {
                Image(systemName: "sparkles")
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(width: 48, height: 30)
                    .background(model.settings.accent.color, in: .capsule)
            }
            .buttonStyle(.plain)
            .disabled(model.busy)
        }
        .padding(.horizontal, 8)
    }

    /// The AI thinks this text is for someone else than the chosen audience.
    private var hint: Bool {
        if let first = model.suggested.first { return first != model.audience }
        return false
    }

    private func chip(_ title: String, systemImage: String, highlighted: Bool) -> some View {
        Label(title, systemImage: systemImage)
            .font(.caption.weight(.medium))
            .lineLimit(1)
            .padding(.horizontal, 10)
            .frame(height: 30)
            .foregroundStyle(highlighted ? model.settings.accent.color : .primary)
            .background(Color(.systemBackground), in: .capsule)
    }

    // MARK: Panel

    private var panel: some View {
        VStack(spacing: 10) {
            Picker("Mode", selection: $model.tab) {
                ForEach(PanelTab.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .onChange(of: model.tab) { model.options = []; model.message = nil }
            if !model.hasFullAccess {
                Label("Turn on Full Access: Settings → General → Keyboard → Keyboards → SaySo", systemImage: "lock")
                    .font(.caption).foregroundStyle(.orange)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            VStack(alignment: .leading, spacing: 8) {
                if model.tab == .replies {
                    HStack {
                        action("Last screenshot", systemImage: "camera.viewfinder") { model.loadLatest() }
                        PasteButton(payloadType: String.self) { strings in
                            Task { @MainActor in model.reply(to: strings.joined(separator: "\n")) }
                        }
                        .labelStyle(.titleAndIcon)
                        .buttonBorderShape(.capsule)
                        .disabled(model.busy)
                    }
                } else {
                    Text(model.draft.isEmpty ? hintText : model.draft)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    action(model.tab == .rewrite ? "Rewrite in my style" : "Write it like me", systemImage: "wand.and.stars") {
                        model.run()
                    }
                }
                if let message = model.message { status(message) }
            }
        }
        .padding(.horizontal, 10)
    }

    private var hintText: String {
        model.tab == .rewrite
            ? "Type or dictate a draft, then tap ✨."
            : "Type what you want to say (“tell her I'm 20 min late”), then tap ✨."
    }

    private func status(_ message: String) -> some View {
        HStack(alignment: .top) {
            Text(message).font(.caption).foregroundStyle(.secondary)
            Spacer(minLength: 0)
            if model.warming {
                Button("Retry") { model.mode == .letters ? model.sparkle() : model.run() }.controlSize(.small)
            }
        }
        .padding(.horizontal, 10)
    }

    private func action(_ title: String, systemImage: String, run: @escaping () -> Void) -> some View {
        Button(action: run) { Label(title, systemImage: systemImage).frame(maxWidth: .infinity) }
            .buttonStyle(.borderedProminent)
            .disabled(model.busy)
    }
}
