import SwiftUI

/// The SaySo keyboard: a compact top strip (mode, audience, format, ✨) over letter keys or the panel; results replace
/// both. No background of its own: the system keyboard backdrop shows through, as behind the stock keyboard.
struct PanelView: View {
    @ObservedObject var model: PanelModel
    @Environment(\.colorScheme) private var scheme
    @Environment(\.verticalSizeClass) private var verticalSizeClass

    private var accent: Color { KeyTheme.accent(model.settings.accent) }
    private var metrics: KeyMetrics { KeyMetrics.current(compactHeight: verticalSizeClass == .compact) }

    var body: some View {
        VStack(spacing: 0) {
            strip
                .frame(height: metrics.strip)
            content
                .frame(maxWidth: .infinity)
                .frame(height: metrics.keys)
        }
        // The keys sit at the bottom, like the stock keyboard's, if the system ever gives more height than asked.
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
        .dynamicTypeSize(.small ... .large)  // the keyboard has a fixed height; huge text sizes would push keys out
    }

    @ViewBuilder private var content: some View {
        if model.busy {
            VStack(spacing: 10) {
                ProgressView().controlSize(.large)
                Label("Writing it your way…", systemImage: "sparkles")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if !model.options.isEmpty {
            // ✨ results, panel results and the Back Tap shortcut's replies: shown whichever mode is active.
            ResultsView(model: model)
        } else if model.mode == .letters {
            LetterKeys(model: model, metrics: metrics)
        } else {
            panel
        }
    }

    // MARK: Strip

    private var strip: some View {
        HStack(spacing: 6) {
            Button {
                model.mode = model.mode == .letters ? .panel : .letters
                model.closeResults()
            } label: {
                Image(systemName: model.mode == .letters ? "rectangle.grid.1x2" : "keyboard")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(accent)
                    .frame(width: 34, height: 32)
                    .background { Capsule().fill(KeyTheme.chipFill(scheme)) }
                    .contentShape(.rect)
            }
            .buttonStyle(.plain)
            if model.mode == .letters, model.options.isEmpty, let message = model.message {
                stripStatus(message)
            } else {
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
            }
            Spacer(minLength: 0)
            Button {
                if model.mode == .letters { model.sparkle() } else { model.run() }
            } label: {
                Image(systemName: "sparkles")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Color.white)
                    .symbolEffect(.pulse, isActive: model.busy)
                    .frame(width: 50, height: 32)
                    .background {
                        ZStack {
                            Capsule().fill(accent)
                            Capsule().fill(KeyTheme.gloss)
                        }
                    }
                    .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .disabled(model.busy)
        }
        .padding(.horizontal, 6)
    }

    /// The AI thinks this text is for someone else than the chosen audience.
    private var hint: Bool {
        if let first = model.suggested.first { return first != model.audience }
        return false
    }

    /// A strip chip: neutral fill, icon and title in the accent.
    private func chip(_ title: String, systemImage: String, highlighted: Bool) -> some View {
        HStack(spacing: 5) {
            Image(systemName: systemImage)
                .font(.caption.weight(.semibold))
            Text(title)
                .font(.footnote.weight(.semibold))
            Image(systemName: "chevron.down")
                .font(.system(size: 8, weight: .bold))
                .foregroundStyle(.secondary)
        }
        .foregroundStyle(accent)
        .lineLimit(1)
        .padding(.horizontal, 11)
        .frame(height: 32)
        .background {
            if highlighted {
                ZStack {
                    Capsule().fill(accent.opacity(0.14))
                    Capsule().strokeBorder(accent.opacity(0.6), lineWidth: 1)
                }
            } else {
                Capsule().fill(KeyTheme.chipFill(scheme))
            }
        }
    }

    /// A short status in the strip, where the chips are (the keys keep their place); tap it to dismiss.
    private func stripStatus(_ message: String) -> some View {
        HStack(spacing: 6) {
            Button {
                model.message = nil
                model.warming = false
            } label: {
                HStack(spacing: 5) {
                    Image(systemName: model.warming ? "hourglass" : "info.circle")
                        .font(.caption.weight(.semibold))
                    Text(message)
                        .font(.caption)
                        .lineLimit(2)
                        .minimumScaleFactor(0.8)
                        .multilineTextAlignment(.leading)
                }
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(.rect)
            }
            .buttonStyle(.plain)
            if model.warming {
                Button("Retry") { model.sparkle() }
                    .font(.caption.weight(.semibold))
                    .buttonStyle(.plain)
                    .foregroundStyle(accent)
            }
        }
    }

    // MARK: Panel

    private var panel: some View {
        ScrollView {
            VStack(spacing: 8) {
                Picker("Mode", selection: Binding(get: { model.tab }, set: { model.selectTab($0) })) {
                    ForEach(PanelTab.allCases) { Text(L($0.rawValue)).tag($0) }
                }
                .pickerStyle(.segmented)
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
                                RoundedRectangle(cornerRadius: KeyTheme.card, style: .continuous)
                                    .fill(KeyTheme.chipFill(scheme))
                            }
                        action(model.tab == .rewrite ? "Rewrite in my style" : "Write it like me", systemImage: "sparkles") {
                            model.run()
                        }
                    }
                    if let message = model.message { status(message) }
                }
            }
            .padding(.horizontal, 8)
            .padding(.top, metrics.top)
            .padding(.bottom, 6)
        }
        .scrollIndicators(.hidden)
        .scrollBounceBehavior(.basedOnSize)
    }

    private var hintText: String {
        L(model.tab == .rewrite
            ? "Type or dictate a draft, then tap ✨."
            : "Type what you want to say (“tell her I'm 20 min late”), then tap ✨.")
    }

    private func status(_ message: String) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: model.warming ? "hourglass" : "info.circle")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(message).font(.caption).foregroundStyle(.secondary)
            Spacer(minLength: 0)
            if model.warming {
                Button("Retry") { model.mode == .letters ? model.sparkle() : model.run() }
                    .font(.caption.weight(.semibold))
                    .controlSize(.small)
            }
        }
        .padding(.horizontal, 4)
    }

    /// A panel action: a neutral key-like bar, its icon in the accent.
    private func action(_ title: String, systemImage: String, run: @escaping () -> Void) -> some View {
        Button(action: run) {
            Label {
                Text(L(title))
            } icon: {
                Image(systemName: systemImage).foregroundStyle(accent)
            }
        }
        .buttonStyle(PanelActionStyle())
        .opacity(model.busy ? 0.5 : 1)
        .disabled(model.busy)
    }
}
