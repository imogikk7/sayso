import SwiftUI

/// Customize the SaySo keyboard: which audiences and formats it shows, how it opens, how many variants ✨ gives.
struct KeyboardSettingsView: View {
    @State private var settings = SharedStore.keyboard

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    KeyboardPreview(settings: settings)
                        .listRowInsets(EdgeInsets())
                }
                Section("Opens with") {
                    Picker("Opens with", selection: $settings.startsWithLetters) {
                        Text("Letters").tag(true)
                        Text("SaySo panel").tag(false)
                    }
                    .pickerStyle(.segmented)
                }
                Section {
                    ForEach(Audience.allCases) { audience in
                        Toggle(audience.label, isOn: binding(audience, in: \.audiences, all: Audience.allCases))
                    }
                } header: {
                    Text("Audiences")
                } footer: {
                    Text("The chips you can pick from. The AI's guess is marked with ✨.")
                }
                Section("Formats") {
                    ForEach(ReplyFormat.allCases) { format in
                        Toggle(isOn: binding(format, in: \.formats, all: ReplyFormat.allCases)) {
                            Label(format.label, systemImage: format.systemImage)
                        }
                    }
                }
                Section("Suggestions") {
                    Stepper("✨ gives \(settings.variants) variant\(settings.variants == 1 ? "" : "s")",
                            value: $settings.variants, in: 1...3)
                    Toggle("Haptics on keys", isOn: $settings.haptics)
                }
                Section("Accent") {
                    HStack(spacing: 14) {
                        ForEach(KeyboardAccent.allCases) { accent in
                            Circle()
                                .fill(accent.color)
                                .frame(width: 30, height: 30)
                                .overlay(Circle().strokeBorder(.primary, lineWidth: settings.accent == accent ? 2.5 : 0))
                                .onTapGesture { settings.accent = accent }
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            .navigationTitle("Keyboard")
            .onChange(of: settings) { _, value in SharedStore.keyboard = value }
        }
    }

    /// A toggle for one item of an ordered list setting; at least one item always stays on.
    private func binding<T: Equatable>(_ item: T, in path: WritableKeyPath<KeyboardSettings, [T]>, all: [T]) -> Binding<Bool> {
        Binding {
            settings[keyPath: path].contains(item)
        } set: { on in
            var items = settings[keyPath: path]
            if on {
                items.append(item)
                items = all.filter(items.contains)
            } else if items.count > 1 {
                items.removeAll { $0 == item }
            }
            settings[keyPath: path] = items
        }
    }
}

/// What the top strip of the keyboard will look like.
struct KeyboardPreview: View {
    let settings: KeyboardSettings

    var body: some View {
        VStack(spacing: 8) {
            HStack(spacing: 6) {
                chip(settings.audiences.first?.label ?? "Friends", systemImage: "person.2")
                chip(settings.formats.first?.label ?? "Message", systemImage: settings.formats.first?.systemImage ?? "bubble.left")
                Spacer()
                Image(systemName: "sparkles")
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(width: 40, height: 32)
                    .background(settings.accent.color, in: .capsule)
            }
            if settings.startsWithLetters {
                HStack(spacing: 4) {
                    ForEach(Array("йцукенгшщзх"), id: \.self) { letter in
                        Text(String(letter))
                            .font(.callout)
                            .frame(maxWidth: .infinity, minHeight: 34)
                            .background(Color(.systemBackground), in: .rect(cornerRadius: 5))
                    }
                }
            } else {
                Text("Rewrite · Write · Replies").font(.callout).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 34)
            }
        }
        .padding(10)
        .background(Color(.systemGray5))
    }

    private func chip(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.caption.weight(.medium))
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(Color(.systemBackground), in: .capsule)
    }
}
