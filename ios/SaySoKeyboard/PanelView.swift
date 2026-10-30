import SwiftUI

struct PanelView: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        VStack(spacing: 10) {
            header
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
            content
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.top, 10)
        .dynamicTypeSize(.small ... .large)  // the panel has a fixed height; huge text sizes would push buttons out
    }

    /// Audience chips in one plain row (a horizontal ScrollView gets iOS 26's edge blur and the chips smear).
    private var header: some View {
        HStack(spacing: 6) {
            if model.showsGlobe {
                Button(action: model.nextKeyboard) { Image(systemName: "globe") }
                    .buttonStyle(.bordered)
            }
            ForEach(Audience.allCases) { audience in
                let selected = model.audience == audience
                Button { model.audience = audience } label: {
                    Text(audience.label)
                        .font(.subheadline.weight(selected ? .semibold : .regular))
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 7)
                        .foregroundStyle(selected ? Color.white : Color.primary)
                        .background(selected ? Color.accentColor : Color.primary.opacity(0.1), in: .capsule)
                }
                .buttonStyle(.plain)
            }
        }
    }

    @ViewBuilder private var content: some View {
        if !model.options.isEmpty {
            ScrollView {
                VStack(spacing: 6) {
                    ForEach(model.options) { option in
                        Button { model.insert(option) } label: {
                            HStack(alignment: .top, spacing: 8) {
                                if let label = option.label {
                                    Text(label).font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
                                        .frame(width: 58, alignment: .leading)
                                }
                                Text(option.text).frame(maxWidth: .infinity, alignment: .leading)
                                    .multilineTextAlignment(.leading)
                                Image(systemName: "arrow.down.left").foregroundStyle(.secondary)
                            }
                            .padding(8)
                            .background(.background.secondary, in: .rect(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        } else {
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
                    Text(model.draft.isEmpty ? hint : model.draft)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    action(model.tab == .rewrite ? "Rewrite in my style" : "Write it like me", systemImage: "wand.and.stars") {
                        model.run()
                    }
                }
                status
            }
        }
    }

    private var hint: String {
        model.tab == .rewrite
            ? "Type or dictate a draft with your usual keyboard, then switch to SaySo."
            : "Type what you want to say (“tell her I'm 20 min late”), then switch to SaySo."
    }

    @ViewBuilder private var status: some View {
        if model.busy {
            ProgressView().frame(maxWidth: .infinity)
        } else if let message = model.message {
            HStack(alignment: .top) {
                Text(message).font(.caption).foregroundStyle(.secondary)
                if model.warming {
                    Button("Retry") { model.run() }.controlSize(.small)
                }
            }
        }
    }

    private func action(_ title: String, systemImage: String, run: @escaping () -> Void) -> some View {
        Button(action: run) { Label(title, systemImage: systemImage).frame(maxWidth: .infinity) }
            .buttonStyle(.borderedProminent)
            .disabled(model.busy)
    }
}
