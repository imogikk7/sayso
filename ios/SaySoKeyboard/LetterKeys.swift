import SwiftUI

/// SaySo's own letter keys: Russian and English, numbers and symbols, shift, delete that repeats, space, return.
/// Long press types the alternate (ё, ъ, Kazakh letters). No autocorrect.
struct LetterKeys: View {
    @ObservedObject var model: PanelModel
    let metrics: KeyMetrics

    /// The stock keyboard's type: letters at 22.5 pt (20 in landscape), labels and glyphs at 16–17 pt.
    private var letterFont: Font { .system(size: metrics.keyHeight > 40 ? 22.5 : 20) }

    var body: some View {
        let rows = model.page == .letters ? model.language.rows : model.page.rows
        let gap = KeyMetrics.keyGap(columns: rows.map(\.count).max() ?? 10)
        let height = metrics.keyHeight
        VStack(spacing: metrics.rowGap) {
            row(rows[0], gap: gap)
            row(rows[1], gap: gap)
            HStack(spacing: gap) {
                if model.page == .letters {
                    SpecialKey(systemImage: model.shift == .caps ? "capslock.fill" : model.shift == .on ? "shift.fill" : "shift",
                               width: 42, height: height, action: model.toggleShift)
                } else {
                    SpecialKey(title: model.page == .numbers ? "#+=" : "123", width: 42, height: height) {
                        model.page = model.page == .numbers ? .symbols : .numbers
                    }
                }
                row(rows[2], gap: gap)
                DeleteKey(model: model, height: height)
            }
            HStack(spacing: 6) {
                SpecialKey(title: model.page == .letters ? "123" : "ABC", width: 45, height: height) {
                    model.page = model.page == .letters ? .numbers : .letters
                }
                if model.showsGlobe {
                    SpecialKey(systemImage: "globe", width: 40, height: height, action: model.nextKeyboard)
                }
                SpecialKey(title: model.language.switchLabel, width: 40, height: height, action: model.switchLanguage)
                CharacterKey(label: model.language.spaceLabel, font: .system(size: 16), height: height) { model.space() }
                SpecialKey(title: model.returnLabel, width: 88, height: height,
                           kind: model.returnLabel == "return" ? .special : .accent, action: model.newline)
            }
        }
        .padding(.horizontal, metrics.side)
        .padding(.top, metrics.top)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }

    private func row(_ keys: [String], gap: CGFloat) -> some View {
        HStack(spacing: gap) {
            ForEach(keys, id: \.self) { key in
                CharacterKey(label: model.page == .letters && model.shift != .off ? key.uppercased() : key,
                             font: letterFont, height: metrics.keyHeight,
                             hasAlternate: alternates[key] != nil && model.page == .letters,
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
    var font: Font = .system(size: 22.5)
    var height: CGFloat = 43
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
                .frame(maxWidth: .infinity, minHeight: height, maxHeight: height)
                .overlay(alignment: .topTrailing) {
                    if hasAlternate { Circle().fill(Color.secondary).opacity(0.6).frame(width: 4, height: 4).padding(4) }
                }
        }
        .buttonStyle(KeyStyle(kind: .letter))
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
    var height: CGFloat = 43
    var kind: KeyKind = .special
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Group {
                if let systemImage {
                    Image(systemName: systemImage).font(.system(size: 17, weight: .regular))
                } else {
                    Text(title ?? "").font(.system(size: 16))
                }
            }
            .frame(width: width, height: height)
        }
        .buttonStyle(KeyStyle(kind: kind))
    }
}

/// Key caps are Buttons (a gesture-only key fired twice on some taps); the look lives in `KeyCap`.
struct KeyStyle: ButtonStyle {
    var kind: KeyKind = .letter

    func makeBody(configuration: Configuration) -> some View {
        KeyCap(kind: kind, pressed: configuration.isPressed) { configuration.label }
    }
}

/// Deletes on touch down, then repeats while held (slowly first, then faster).
struct DeleteKey: View {
    @ObservedObject var model: PanelModel
    var height: CGFloat = 43
    @State private var repeating: Task<Void, Never>?

    var body: some View {
        KeyCap(kind: .special, pressed: repeating != nil) {
            Image(systemName: repeating == nil ? "delete.left" : "delete.left.fill")
                .font(.system(size: 17, weight: .regular))
                .frame(width: 42, height: height)
        }
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
