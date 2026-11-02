import SwiftUI

/// The SaySo keyboard: a top strip (mode, audience, format, ✨) over letter keys or the panel; results replace both.
struct PanelView: View {
    @ObservedObject var model: PanelModel
    @Environment(\.colorScheme) private var scheme

    private var accent: Color { KeyTheme.accent(model.settings.accent) }

    var body: some View {
        VStack(spacing: 6) {
            strip
            if model.busy {
                VStack(spacing: 10) {
                    ProgressView().controlSize(.large).tint(accent)
                    Label("Writing it your way…", systemImage: "sparkles")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
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
        .background { KeyBackdrop(accent: accent) }
        .tint(accent)
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
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(KeyTheme.keyText(scheme))
                    .frame(width: 34, height: 30)
                    .background { glassPill() }
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
                    .foregroundStyle(Color.white)
                    .symbolEffect(.pulse, isActive: model.busy)
                    .frame(width: 54, height: 30)
                    .background {
                        ZStack {
                            Capsule().fill(LinearGradient(colors: sparkleColors,
                                                          startPoint: .topLeading, endPoint: .bottomTrailing))
                            Capsule().fill(KeyTheme.gloss)
                            Capsule().strokeBorder(Color.white.opacity(0.35), lineWidth: 0.5)
                        }
                    }
                    .shadow(color: accent.opacity(0.55), radius: 8, x: 0, y: 2)
                    .shadow(color: accent.opacity(0.3), radius: 2, x: 0, y: 1)
            }
            .buttonStyle(.plain)
            .disabled(model.busy)
        }
        .padding(.horizontal, 8)
    }

    /// The brand blue fades from the light glow; other accents stay solid under the gloss.
    private var sparkleColors: [Color] {
        model.settings.accent == .blue ? [KeyTheme.glow, accent] : [accent, accent]
    }

    /// The AI thinks this text is for someone else than the chosen audience.
    private var hint: Bool {
        if let first = model.suggested.first { return first != model.audience }
        return false
    }

    private func chip(_ title: String, systemImage: String, highlighted: Bool) -> some View {
        HStack(spacing: 5) {
            Image(systemName: systemImage)
                .font(.caption.weight(.semibold))
                .foregroundStyle(accent)
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(highlighted ? accent : KeyTheme.keyText(scheme))
            Image(systemName: "chevron.down")
                .font(.system(size: 8, weight: .bold))
                .foregroundStyle(.secondary)
        }
        .lineLimit(1)
        .padding(.horizontal, 11)
        .frame(height: 30)
        .background {
            if highlighted {
                ZStack {
                    Capsule().fill(accent.opacity(0.14))
                    Capsule().strokeBorder(accent.opacity(0.6), lineWidth: 1)
                }
            } else {
                glassPill()
            }
        }
    }

    /// The light frosted pill behind the strip's buttons and chips.
    private func glassPill() -> some View {
        ZStack {
            Capsule().fill(KeyTheme.chipFill(scheme))
            Capsule().strokeBorder(KeyTheme.chipEdge(scheme), lineWidth: 0.5)
        }
        .shadow(color: KeyTheme.softShadow(scheme), radius: 3, x: 0, y: 1)
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
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .background(Color.orange.opacity(0.12), in: .rect(cornerRadius: KeyTheme.chip))
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
                        .foregroundStyle(model.draft.isEmpty ? Color.secondary : KeyTheme.keyText(scheme))
                        .lineLimit(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                        .background {
                            ZStack {
                                RoundedRectangle(cornerRadius: KeyTheme.card, style: .continuous).fill(KeyTheme.chipFill(scheme))
                                RoundedRectangle(cornerRadius: KeyTheme.card, style: .continuous)
                                    .strokeBorder(KeyTheme.chipEdge(scheme), lineWidth: 0.5)
                            }
                            .shadow(color: KeyTheme.softShadow(scheme), radius: 4, x: 0, y: 2)
                        }
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
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: model.warming ? "hourglass" : "info.circle")
                .font(.caption.weight(.semibold))
                .foregroundStyle(accent)
            Text(message).font(.caption).foregroundStyle(.secondary)
            Spacer(minLength: 0)
            if model.warming {
                Button("Retry") { model.mode == .letters ? model.sparkle() : model.run() }
                    .font(.caption.weight(.semibold))
                    .controlSize(.small)
            }
        }
        .padding(.horizontal, 10)
    }

    private func action(_ title: String, systemImage: String, run: @escaping () -> Void) -> some View {
        Button(action: run) { Label(title, systemImage: systemImage) }
            .buttonStyle(GlowButtonStyle(accent: accent))
            .opacity(model.busy ? 0.5 : 1)
            .disabled(model.busy)
    }
}
