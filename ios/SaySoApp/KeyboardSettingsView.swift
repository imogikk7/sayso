import SwiftUI
import UIKit

/// Customize the SaySo keyboard: which audiences and formats it shows, how it opens, how many variants ✨ gives.
struct KeyboardSettingsView: View {
    @State private var settings = SharedStore.keyboard

    private let grid: [GridItem] = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.backdrop
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        KeyboardPreview(settings: settings)
                        SectionTitle(text: "Layout").padding(.top, 6)
                        modeCard
                        audiencesCard
                        formatsCard
                        SectionTitle(text: "Suggestions").padding(.top, 6)
                        variantsCard
                        accentCard
                        SectionTitle(text: "Typing").padding(.top, 6)
                        hapticsCard
                        capitalCard
                        learningCard
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 12)
                    .padding(.bottom, 32)
                }
            }
            .toolbar(.hidden, for: .navigationBar)
            .onChange(of: settings) { _, value in SharedStore.keyboard = value }
        }
    }

    // MARK: - Header

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Keyboard").font(Theme.title(34))
            Text("Your voice, in every chat. Make it yours.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Layout

    private var modeCard: some View {
        SettingsCard(icon: "keyboard", colors: TileColors.deep, title: "Opens with",
                     subtitle: "What you see first when you switch to SaySo.") {
            HStack(spacing: 10) {
                SelectTile(icon: "textformat.abc", title: "Letters", selected: settings.startsWithLetters) {
                    settings.startsWithLetters = true
                }
                SelectTile(icon: "square.grid.2x2", title: "SaySo panel", selected: !settings.startsWithLetters) {
                    settings.startsWithLetters = false
                }
            }
        }
    }

    private var audiencesCard: some View {
        SettingsCard(icon: "person.2.fill", colors: TileColors.sky, title: "Audiences & order",
                     subtitle: "The chips you can pick from. The AI's guess is marked with ✨.") {
            VStack(alignment: .leading, spacing: 10) {
                LazyVGrid(columns: grid, spacing: 10) {
                    ForEach(Audience.allCases) { audience in
                        SelectTile(icon: Self.icon(for: audience), title: audience.label,
                                   selected: settings.audiences.contains(audience)) {
                            let toggle = binding(audience, in: \.audiences, all: Audience.allCases)
                            toggle.wrappedValue.toggle()
                        }
                    }
                }
                orderLine(settings.audiences.map(\.label))
            }
        }
    }

    private var formatsCard: some View {
        SettingsCard(icon: "square.stack.fill", colors: TileColors.violet, title: "Formats",
                     subtitle: "How ✨ can write: one message, a series, official or email.") {
            VStack(alignment: .leading, spacing: 10) {
                LazyVGrid(columns: grid, spacing: 10) {
                    ForEach(ReplyFormat.allCases) { format in
                        SelectTile(icon: format.systemImage, title: format.label,
                                   selected: settings.formats.contains(format)) {
                            let toggle = binding(format, in: \.formats, all: ReplyFormat.allCases)
                            toggle.wrappedValue.toggle()
                        }
                    }
                }
                orderLine(settings.formats.map(\.label))
            }
        }
    }

    /// "On the keyboard: 1 Partner · 2 Friends …" — the order the chips appear in. At least one always stays on.
    private func orderLine(_ labels: [String]) -> some View {
        let numbered: [String] = labels.enumerated().map { "\($0.offset + 1) \($0.element)" }
        return HStack(alignment: .top, spacing: 6) {
            Image(systemName: "list.number")
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.accentColor)
            Text(Lf("On the keyboard: %@", numbered.joined(separator: " · ")))
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: - Suggestions

    private var variantsCard: some View {
        SettingsCard(icon: "sparkles", colors: TileColors.sky, title: "Variants",
                     subtitle: Lf("✨ gives %lld variants at a time.", settings.variants)) {
            HStack(spacing: 10) {
                ForEach(1...3, id: \.self) { count in
                    variantButton(count)
                }
            }
        }
    }

    private func variantButton(_ count: Int) -> some View {
        let selected = settings.variants == count
        return Button {
            settings.variants = count
        } label: {
            VStack(spacing: 2) {
                Text("\(count)").font(Theme.display(22))
                Text(count == 1 ? "variant" : "variants").font(.caption2.weight(.medium))
            }
            .foregroundStyle(selected ? Color.white : Color.primary)
            .frame(maxWidth: .infinity, minHeight: 62)
            .background {
                if selected {
                    RoundedRectangle(cornerRadius: Theme.card).fill(Theme.accentGradient)
                } else {
                    RoundedRectangle(cornerRadius: Theme.card).fill(Color.primary.opacity(0.04))
                }
            }
            .overlay(RoundedRectangle(cornerRadius: Theme.card).stroke(Color.primary.opacity(selected ? 0 : 0.06)))
            .shadow(color: Color.accentColor.opacity(selected ? 0.3 : 0), radius: 8, y: 3)
            .contentShape(.rect(cornerRadius: Theme.card))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Lf("%lld variants", count))
        .accessibilityAddTraits(selected ? .isSelected : [])
        .animation(.snappy(duration: 0.2), value: selected)
    }

    private var accentCard: some View {
        SettingsCard(icon: "paintpalette.fill", colors: TileColors.teal, title: "Accent",
                     subtitle: "The color of ✨ and the return key.") {
            HStack(spacing: 14) {
                ForEach(KeyboardAccent.allCases) { accent in
                    accentButton(accent)
                }
                Spacer(minLength: 0)
            }
        }
    }

    private func accentButton(_ accent: KeyboardAccent) -> some View {
        let selected = settings.accent == accent
        return Button {
            settings.accent = accent
        } label: {
            ZStack {
                Circle()
                    .fill(LinearGradient(colors: [accent.color.opacity(0.7), accent.color],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 34, height: 34)
                if selected {
                    Image(systemName: "checkmark").font(.system(size: 13, weight: .heavy)).foregroundStyle(.white)
                }
            }
            .padding(3)
            .overlay(Circle().strokeBorder(selected ? accent.color : Color.clear, lineWidth: 2))
            .shadow(color: accent.color.opacity(selected ? 0.45 : 0.15), radius: 6, y: 2)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(L(accent.rawValue.capitalized))
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    // MARK: - Typing

    private var hapticsCard: some View {
        ToggleCard(icon: "hand.tap.fill", colors: TileColors.deep, title: "Haptics on keys",
                   subtitle: "A light tap you can feel on every key.", isOn: $settings.haptics)
    }

    private var capitalCard: some View {
        ToggleCard(icon: "textformat.size", colors: TileColors.violet, title: "Capital letter at sentence start",
                   subtitle: "Off: letters stay lowercase unless you tap ⇧ (double-tap for caps lock).",
                   isOn: $settings.autoCapitalize)
    }

    private var learningCard: some View {
        ToggleCard(
            icon: "graduationcap.fill", colors: TileColors.green, title: "Learn from what I type",
            subtitle: "Messages you send with SaySo's letter keys (and how you change a ✨ suggestion before sending) become examples of your style right away.",
            isOn: $settings.learns,
            note: "Only your own typing: pasted text, password, email, link, code and search fields are never learned. Off until you turn it on. See and delete them in Styles → your style → Learned from you.",
            noteIcon: "lock.shield.fill"
        )
    }

    // MARK: - Helpers

    private static func icon(for audience: Audience) -> String {
        switch audience {
        case .partner: "heart.fill"
        case .friends: "person.2.fill"
        case .family: "house.fill"
        case .elder_informal: "person.crop.circle.fill"
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

// MARK: - Live preview

/// A small drawing of the SaySo keyboard as it will look with these settings: the suggestion ✨ would give, the top
/// strip (audience chip with the AI's ✨ guess, format chip, ✨ key) and either the letter keys or the SaySo panel.
struct KeyboardPreview: View {
    let settings: KeyboardSettings

    private var accent: Color { settings.accent.color }
    private var accentFill: LinearGradient {
        LinearGradient(colors: [accent.opacity(0.72), accent], startPoint: .topLeading, endPoint: .bottomTrailing)
    }
    private var audience: Audience { settings.audiences.first ?? .friends }
    private var format: ReplyFormat { settings.formats.first ?? .message }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            topLine
            suggestion
            keyboard
        }
        .padding(14)
        .background {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.card + 8).fill(.regularMaterial)
                RoundedRectangle(cornerRadius: Theme.card + 8)
                    .fill(LinearGradient(colors: [accent.opacity(0.22), accent.opacity(0.04)],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
            }
        }
        .overlay(RoundedRectangle(cornerRadius: Theme.card + 8).stroke(accent.opacity(0.2)))
        .shadow(color: accent.opacity(0.22), radius: 18, y: 8)
        .animation(.snappy(duration: 0.25), value: settings)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Keyboard preview")
    }

    // MARK: Top line

    private var topLine: some View {
        HStack(spacing: 6) {
            Circle().fill(Color.green).frame(width: 7, height: 7)
            Text("LIVE PREVIEW")
                .font(.caption2.weight(.bold))
                .tracking(1.2)
                .foregroundStyle(.secondary)
            Spacer()
            Text(settings.startsWithLetters ? "Opens with letters" : "Opens with the panel")
                .font(.caption2.weight(.medium))
                .foregroundStyle(.secondary)
        }
    }

    // MARK: Suggestion

    /// Sample text for the first format, lowercase unless "Capital letter at sentence start" is on.
    private var bubbles: [String] {
        switch format {
        case .message: [cased(L("ok see you at 8 🙂"))]
        case .series: [cased(L("ok")), cased(L("see you at 8 🙂"))]
        case .official: [L("Noted, I'll be there at 8 pm.")]
        case .email: [L("Hi! I'll be there at 8 pm. Best,")]
        }
    }

    private func cased(_ text: String) -> String {
        guard settings.autoCapitalize else { return text }
        return String(text.prefix(1)).uppercased() + String(text.dropFirst())
    }

    private var suggestion: some View {
        VStack(alignment: .trailing, spacing: 4) {
            ForEach(Array(bubbles.enumerated()), id: \.offset) { _, text in
                Text(text)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 13)
                    .padding(.vertical, 8)
                    .background(accentFill, in: .rect(cornerRadius: Theme.bubble))
            }
            variantDots
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }

    private var variantDots: some View {
        HStack(spacing: 4) {
            ForEach(0..<settings.variants, id: \.self) { index in
                Capsule()
                    .fill(index == 0 ? accent : accent.opacity(0.3))
                    .frame(width: index == 0 ? 14 : 6, height: 6)
            }
            Text(Lf("%lld variants", settings.variants))
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.top, 2)
    }

    // MARK: Keyboard

    private var keyboard: some View {
        VStack(spacing: 8) {
            strip
            if settings.startsWithLetters {
                letters
            } else {
                panel
            }
        }
        .padding(7)
        .background(KeyColors.board, in: .rect(cornerRadius: Theme.card))
    }

    private var strip: some View {
        HStack(spacing: 6) {
            chip(icon: "sparkles", title: audience.label, extra: settings.audiences.count - 1, aiGuess: true)
            chip(icon: format.systemImage, title: format.label, extra: settings.formats.count - 1, aiGuess: false)
            Spacer(minLength: 4)
            Image(systemName: "sparkles")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 46, height: 30)
                .background(accentFill, in: .capsule)
                .shadow(color: accent.opacity(0.45), radius: 5, y: 2)
        }
    }

    private func chip(icon: String, title: String, extra: Int, aiGuess: Bool) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(aiGuess ? accent : Color.secondary)
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.primary)
            if extra > 0 {
                Text("+\(extra)")
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(.secondary)
            }
        }
        .lineLimit(1)
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background(KeyColors.cap, in: .rect(cornerRadius: Theme.chip))
    }

    // MARK: Letters

    private static let row1 = ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"]
    private static let row2 = ["a", "s", "d", "f", "g", "h", "j", "k", "l"]
    private static let row3 = ["z", "x", "c", "v", "b", "n", "m"]

    /// With auto-capitalize on, the keys show capitals, as at the start of a sentence.
    private func letter(_ text: String) -> String {
        settings.autoCapitalize ? text.uppercased() : text
    }

    private var letters: some View {
        VStack(spacing: 7) {
            HStack(spacing: 4) {
                ForEach(Self.row1, id: \.self) { key(letter($0)) }
            }
            HStack(spacing: 4) {
                ForEach(Self.row2, id: \.self) { key(letter($0)) }
            }
            .padding(.horizontal, 12)
            HStack(spacing: 4) {
                iconKey(settings.autoCapitalize ? "shift.fill" : "shift", width: 34)
                    .padding(.trailing, 6)
                ForEach(Self.row3, id: \.self) { key(letter($0)) }
                iconKey("delete.left", width: 34)
                    .padding(.leading, 6)
            }
            HStack(spacing: 4) {
                labelKey("123", width: 40, filled: false)
                iconKey("globe", width: 34)
                key("space")
                labelKey("return", width: 62, filled: true)
            }
        }
    }

    private func key(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 16))
            .foregroundStyle(.primary)
            .lineLimit(1)
            .frame(maxWidth: .infinity)
            .frame(height: 34)
            .background(KeyColors.cap, in: .rect(cornerRadius: 4))
            .shadow(color: Color.black.opacity(0.18), radius: 0, y: 1)
    }

    private func iconKey(_ systemImage: String, width: CGFloat) -> some View {
        Image(systemName: systemImage)
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(.primary)
            .frame(width: width, height: 34)
            .background(KeyColors.function, in: .rect(cornerRadius: 4))
            .shadow(color: Color.black.opacity(0.18), radius: 0, y: 1)
    }

    @ViewBuilder
    private func labelKey(_ text: String, width: CGFloat, filled: Bool) -> some View {
        if filled {
            Text(text)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: width, height: 34)
                .background(accentFill, in: .rect(cornerRadius: 4))
                .shadow(color: Color.black.opacity(0.18), radius: 0, y: 1)
        } else {
            Text(text)
                .font(.system(size: 13))
                .foregroundStyle(.primary)
                .frame(width: width, height: 34)
                .background(KeyColors.function, in: .rect(cornerRadius: 4))
                .shadow(color: Color.black.opacity(0.18), radius: 0, y: 1)
        }
    }

    // MARK: Panel

    private var panel: some View {
        VStack(spacing: 8) {
            HStack(spacing: 6) {
                panelTile(icon: "arrow.triangle.2.circlepath", title: "Rewrite")
                panelTile(icon: "square.and.pencil", title: "Write")
                panelTile(icon: "text.bubble", title: "Replies")
            }
            chipRow(settings.audiences.map { PreviewChip(id: $0.id, title: $0.label) }, selectedID: audience.id)
            chipRow(settings.formats.map { PreviewChip(id: $0.id, title: $0.label) }, selectedID: format.id)
        }
    }

    private func panelTile(icon: String, title: String) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(accent)
            Text(L(title))
                .font(.caption.weight(.semibold))
                .foregroundStyle(.primary)
        }
        .frame(maxWidth: .infinity, minHeight: 66)
        .background(KeyColors.cap, in: .rect(cornerRadius: Theme.chip))
        .shadow(color: Color.black.opacity(0.12), radius: 0, y: 1)
    }

    private func chipRow(_ items: [PreviewChip], selectedID: String) -> some View {
        HStack(spacing: 5) {
            ForEach(items) { item in
                miniChip(item.title, selected: item.id == selectedID)
            }
            Spacer(minLength: 0)
        }
    }

    private func miniChip(_ title: String, selected: Bool) -> some View {
        Text(title)
            .font(.caption2.weight(selected ? .semibold : .regular))
            .lineLimit(1)
            .minimumScaleFactor(0.8)
            .foregroundStyle(selected ? Color.white : Color.primary)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background {
                if selected {
                    Capsule().fill(accentFill)
                } else {
                    Capsule().fill(KeyColors.cap)
                }
            }
    }
}

/// One audience or format chip in the panel preview.
private struct PreviewChip: Identifiable {
    let id: String
    let title: String
}

/// Key, function key and board colors close to the system keyboard, in light and dark mode.
private enum KeyColors {
    static let board = Color(UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(white: 0.16, alpha: 1)
            : UIColor(red: 0.82, green: 0.83, blue: 0.86, alpha: 1)
    })
    static let cap = Color(UIColor { traits in
        traits.userInterfaceStyle == .dark ? UIColor(white: 0.40, alpha: 1) : UIColor.white
    })
    static let function = Color(UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(white: 0.27, alpha: 1)
            : UIColor(red: 0.68, green: 0.70, blue: 0.74, alpha: 1)
    })
}
