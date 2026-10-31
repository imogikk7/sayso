import SwiftUI

/// SaySo's own letter keys: Russian and English, numbers and symbols, shift, delete that repeats, space, return.
/// Long press types the alternate (ё, ъ, Kazakh letters). No autocorrect.
struct LetterKeys: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        let rows = model.page == .letters ? model.language.rows : model.page.rows
        VStack(spacing: 10) {
            row(rows[0])
            row(rows[1])
            HStack(spacing: 5) {
                if model.page == .letters {
                    SpecialKey(systemImage: model.shift == .caps ? "capslock.fill" : model.shift == .on ? "shift.fill" : "shift",
                               width: 42, action: model.toggleShift)
                } else {
                    SpecialKey(title: model.page == .numbers ? "#+=" : "123", width: 42) {
                        model.page = model.page == .numbers ? .symbols : .numbers
                    }
                }
                row(rows[2])
                DeleteKey(model: model)
            }
            HStack(spacing: 5) {
                SpecialKey(title: model.page == .letters ? "123" : "ABC", width: 44) {
                    model.page = model.page == .letters ? .numbers : .letters
                }
                if model.showsGlobe {
                    SpecialKey(systemImage: "globe", width: 38, action: model.nextKeyboard)
                }
                SpecialKey(title: model.language.switchLabel, width: 38, action: model.switchLanguage)
                CharacterKey(label: model.language.spaceLabel, font: .callout) { model.space() }
                SpecialKey(title: model.returnLabel, width: 78, action: model.newline)
            }
        }
        .padding(.horizontal, 3)
    }

    private func row(_ keys: [String]) -> some View {
        HStack(spacing: 5) {
            ForEach(keys, id: \.self) { key in
                CharacterKey(label: model.page == .letters && model.shift != .off ? key.uppercased() : key,
                             font: .title3, hasAlternate: alternates[key] != nil && model.page == .letters,
                             onLongPress: { model.typeAlternate(key) }) {
                    model.type(key)
                }
            }
        }
    }
}

/// A letter key; a long press types its alternate instead (ё, ъ, Kazakh letters).
struct CharacterKey: View {
    let label: String
    var font: Font = .title3
    var hasAlternate = false
    var onLongPress: (() -> Void)? = nil
    let action: () -> Void

    @State private var usedAlternate = false

    var body: some View {
        Button {
            if usedAlternate { usedAlternate = false } else { action() }
        } label: {
            Text(label)
                .font(font)
                .frame(maxWidth: .infinity, minHeight: 42)
                .overlay(alignment: .topTrailing) {
                    if hasAlternate { Circle().fill(.secondary).frame(width: 3, height: 3).padding(4) }
                }
        }
        .buttonStyle(KeyStyle(background: Color(.systemBackground), pressed: Color(.systemGray3)))
        .simultaneousGesture(LongPressGesture(minimumDuration: 0.45).onEnded { _ in
            guard let onLongPress else { return }
            usedAlternate = true
            onLongPress()
        })
    }
}

struct SpecialKey: View {
    var title: String? = nil
    var systemImage: String? = nil
    let width: CGFloat
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Group {
                if let systemImage { Image(systemName: systemImage) } else { Text(title ?? "").font(.callout) }
            }
            .frame(width: width, height: 42)
        }
        .buttonStyle(KeyStyle(background: Color(.systemGray3), pressed: Color(.systemBackground)))
    }
}

struct KeyStyle: ButtonStyle {
    let background: Color
    let pressed: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(.primary)
            .background(configuration.isPressed ? pressed : background, in: .rect(cornerRadius: 6))
            .shadow(color: .black.opacity(0.25), radius: 0, y: 1)
            .contentShape(.rect)
    }
}

/// Deletes on touch down, then repeats while held (slowly first, then faster).
struct DeleteKey: View {
    @ObservedObject var model: PanelModel
    @State private var repeating: Task<Void, Never>?

    var body: some View {
        Image(systemName: repeating == nil ? "delete.left" : "delete.left.fill")
            .frame(width: 42, height: 42)
            .background(Color(.systemGray3), in: .rect(cornerRadius: 6))
            .shadow(color: .black.opacity(0.25), radius: 0, y: 1)
            .contentShape(.rect)
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    guard repeating == nil else { return }
                    model.deleteBackward()
                    repeating = Task {
                        try? await Task.sleep(for: .milliseconds(450))
                        var count = 0
                        while !Task.isCancelled {
                            model.deleteBackward()
                            count += 1
                            try? await Task.sleep(for: .milliseconds(count > 15 ? 40 : 90))
                        }
                    }
                }
                .onEnded { _ in
                    repeating?.cancel()
                    repeating = nil
                })
    }
}
