import SwiftUI

/// SaySo's own letter keys: Russian and English, numbers and symbols, shift, delete that repeats, space, return.
/// Long press types the alternate (ё, ъ, Kazakh letters). No autocorrect.
///
/// Laid out like the stock keyboard (sizes in `KeyMetrics`): letter keys keep one width on every row, shorter rows are
/// centered, and each key's touch area takes in half the gap around it (the outer keys reach the keyboard's edges), so
/// a tap between two keys still types one.
struct LetterKeys: View {
    @ObservedObject var model: PanelModel
    let metrics: KeyMetrics

    /// The stock keyboard's type: letters at 22.5 pt (20 in landscape), labels and glyphs at 16–17 pt.
    private var letterFont: Font { .system(size: metrics.keyHeight > 40 ? 22.5 : 20) }

    var body: some View {
        GeometryReader { geometry in
            keyboard(width: geometry.size.width)
        }
    }

    /// The touch area above and below the caps of row `index` (0 = top): half the row gap, or the keyboard's top and
    /// bottom margins for the outer rows.
    private func vertical(_ index: Int) -> (top: CGFloat, bottom: CGFloat) {
        (index == 0 ? metrics.top : metrics.rowGap / 2, index == 3 ? metrics.bottom : metrics.rowGap / 2)
    }

    private func keyboard(width: CGFloat) -> some View {
        let rows = model.page == .letters ? model.language.rows : model.page.rows
        let columns = rows.map(\.count).max() ?? 10
        let gap = metrics.gap(columns: columns)
        let key = metrics.keyWidth(width, columns: columns)
        return VStack(spacing: 0) {
            letterRow(rows[0], key: key, gap: gap, width: width, vertical: vertical(0))
            letterRow(rows[1], key: key, gap: gap, width: width, vertical: vertical(1))
            thirdRow(rows[2], key: key, gap: gap, width: width, vertical: vertical(2))
            bottomRow(width: width, vertical: vertical(3))
        }
        .frame(width: width, height: metrics.keys)
        .frame(maxHeight: .infinity, alignment: .bottom)
    }

    /// A row of letters, centered, each key `key` wide.
    private func letterRow(_ keys: [String], key: CGFloat, gap: CGFloat, width: CGFloat,
                           vertical: (top: CGFloat, bottom: CGFloat)) -> some View {
        let used = CGFloat(keys.count) * key + CGFloat(max(keys.count - 1, 0)) * gap
        let edge = max(0, (width - used) / 2)
        return HStack(spacing: 0) {
            letters(keys, key: key, gap: gap, leading: edge, trailing: edge, vertical: vertical)
        }
    }

    /// The third row: shift (or 123 / #+=) at the left edge, the letters centered, delete at the right edge.
    private func thirdRow(_ keys: [String], key: CGFloat, gap: CGFloat, width: CGFloat,
                          vertical: (top: CGFloat, bottom: CGFloat)) -> some View {
        let inner = width - 2 * metrics.side
        let letterPage = model.page == .letters
        // Letters keep their width; the five punctuation keys of the number pages share what the side keys leave.
        let keyWidth: CGFloat? = letterPage ? key : nil
        let used = letterPage ? CGFloat(keys.count) * key + CGFloat(max(keys.count - 1, 0)) * gap : 0
        let side = letterPage ? max(0, min(metrics.functionWidth(width), (inner - used) / 2 - gap))
                              : metrics.functionWidth(width)
        // The space between a side key and the letters (on the number pages: half a key more than a gap, as on iOS).
        let around = letterPage ? max(gap, (inner - used) / 2 - side) : gap + key / 2
        let hit = { (leading: CGFloat, trailing: CGFloat) in
            EdgeInsets(top: vertical.top, leading: leading, bottom: vertical.bottom, trailing: trailing)
        }
        return HStack(spacing: 0) {
            if letterPage {
                KeyButton(kind: .special, width: side, height: metrics.keyHeight, hit: hit(metrics.side, around / 2),
                          onDown: model.feedback, action: model.toggleShift) {
                    Image(systemName: model.shift == .caps ? "capslock.fill" : model.shift == .on ? "shift.fill" : "shift")
                        .font(.system(size: 17, weight: .regular))
                }
            } else {
                KeyButton(kind: .special, width: side, height: metrics.keyHeight, hit: hit(metrics.side, around / 2),
                          onDown: model.feedback, action: { model.page = model.page == .numbers ? .symbols : .numbers }) {
                    Text(model.page == .numbers ? "#+=" : "123").font(.system(size: 16))
                }
            }
            letters(keys, key: keyWidth, gap: gap, leading: around / 2, trailing: around / 2, vertical: vertical)
            DeleteKey(model: model, width: side, height: metrics.keyHeight, hit: hit(around / 2, metrics.side))
        }
        .frame(width: width)
    }

    /// The bottom row, the same in every language: 123, globe (only where iOS asks for it), language, space, return.
    private func bottomRow(width: CGFloat, vertical: (top: CGFloat, bottom: CGFloat)) -> some View {
        let function = metrics.functionWidth(width)
        let half = metrics.keyGap / 2
        let hit = { (leading: CGFloat, trailing: CGFloat) in
            EdgeInsets(top: vertical.top, leading: leading, bottom: vertical.bottom, trailing: trailing)
        }
        return HStack(spacing: 0) {
            KeyButton(kind: .special, width: function, height: metrics.keyHeight, hit: hit(metrics.side, half),
                      onDown: model.feedback, action: { model.page = model.page == .letters ? .numbers : .letters }) {
                Text(model.page == .letters ? "123" : "ABC").font(.system(size: 16))
            }
            if model.showsGlobe {
                KeyButton(kind: .special, width: function, height: metrics.keyHeight, hit: hit(half, half),
                          onDown: model.feedback, action: model.nextKeyboard) {
                    Image(systemName: "globe").font(.system(size: 17, weight: .regular))
                }
            }
            KeyButton(kind: .special, width: function, height: metrics.keyHeight, hit: hit(half, half),
                      onDown: model.feedback, action: model.switchLanguage) {
                Text(model.language.switchLabel).font(.system(size: 16))
            }
            KeyButton(kind: .letter, width: nil, height: metrics.keyHeight, hit: hit(half, half),
                      onDown: model.feedback, action: model.space) {
                Text(model.language.spaceLabel).font(.system(size: 16))
            }
            KeyButton(kind: model.returnLabel == "return" ? .special : .accent, width: metrics.returnWidth(width),
                      height: metrics.keyHeight, hit: hit(half, metrics.side),
                      onDown: model.feedback, action: model.newline) {
                Text(model.returnLabel).font(.system(size: 16))
            }
        }
        .frame(width: width)
    }

    /// Letter keys side by side; `key` nil makes them share the row's width. The first and last reach out by
    /// `leading` / `trailing`, the others by half a gap.
    @ViewBuilder
    private func letters(_ keys: [String], key: CGFloat?, gap: CGFloat, leading: CGFloat, trailing: CGFloat,
                         vertical: (top: CGFloat, bottom: CGFloat)) -> some View {
        let upper = model.page == .letters && model.shift != .off
        ForEach(Array(keys.enumerated()), id: \.element) { index, letter in
            let hasAlternate = model.page == .letters && alternates[letter] != nil
            KeyButton(kind: .letter, width: key, height: metrics.keyHeight,
                      hit: EdgeInsets(top: vertical.top, leading: index == 0 ? leading : gap / 2,
                                      bottom: vertical.bottom, trailing: index == keys.count - 1 ? trailing : gap / 2),
                      onDown: model.feedback,
                      onLongPress: hasAlternate ? { model.typeAlternate(letter) } : nil,
                      action: { model.type(letter) }) {
                Text(upper ? letter.uppercased() : letter)
                    .font(letterFont)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .overlay(alignment: .topTrailing) {
                        if hasAlternate {
                            Circle().fill(Color.secondary).opacity(0.6).frame(width: 4, height: 4).padding(4)
                        }
                    }
            }
        }
    }
}

/// One key that reacts like the stock one: the cap lights up the instant a finger lands (with the haptic, which never
/// waits), the action runs the instant it lifts, and nothing animates. A long press, if the key has one, runs instead
/// of the action. The pressed state lives in the key itself, so a press redraws only this key.
///
/// The touch area is the cap plus `hit` around it. A key is one drag gesture from touch down to lift, so it fires
/// exactly once per touch.
struct KeyButton<Label: View>: View {
    let kind: KeyKind
    let width: CGFloat?  // nil: as wide as the row allows
    let height: CGFloat
    let hit: EdgeInsets
    let onDown: () -> Void
    let onLongPress: (() -> Void)?
    let action: () -> Void
    let label: Label

    @GestureState(resetTransaction: Transaction(animation: nil)) private var pressed = false
    @State private var holding: Task<Void, Never>?
    @State private var usedLongPress = false

    init(kind: KeyKind, width: CGFloat?, height: CGFloat, hit: EdgeInsets = EdgeInsets(),
         onDown: @escaping () -> Void = {}, onLongPress: (() -> Void)? = nil,
         action: @escaping () -> Void, @ViewBuilder label: () -> Label) {
        self.kind = kind
        self.width = width
        self.height = height
        self.hit = hit
        self.onDown = onDown
        self.onLongPress = onLongPress
        self.action = action
        self.label = label()
    }

    var body: some View {
        KeyCap(kind: kind, pressed: pressed) {
            label
                .frame(minWidth: width, maxWidth: width ?? .infinity, minHeight: height, maxHeight: height)
        }
        .padding(hit)
        .contentShape(.rect)
        .gesture(
            DragGesture(minimumDistance: 0)
                .updating($pressed) { _, state, transaction in
                    transaction.animation = nil
                    state = true
                }
                .onEnded { _ in
                    holding?.cancel()
                    holding = nil
                    if usedLongPress { usedLongPress = false } else { action() }
                }
        )
        .onChange(of: pressed) { _, down in
            holding?.cancel()
            holding = nil
            guard down else { return }  // lifted (or the system took the touch): nothing more to do
            usedLongPress = false
            onDown()
            guard let onLongPress else { return }
            holding = Task { @MainActor in
                try? await Task.sleep(for: .milliseconds(450))
                guard !Task.isCancelled else { return }
                usedLongPress = true
                onLongPress()
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { action() }
    }
}

/// Deletes on touch down, then, held, repeats after 0.5 s every 0.1 s until the finger lifts.
struct DeleteKey: View {
    let model: PanelModel  // not observed: nothing in the model changes how this key looks
    let width: CGFloat
    let height: CGFloat
    var hit = EdgeInsets()

    @GestureState(resetTransaction: Transaction(animation: nil)) private var pressed = false
    @State private var repeating: Task<Void, Never>?

    var body: some View {
        KeyCap(kind: .special, pressed: pressed) {
            Image(systemName: pressed ? "delete.left.fill" : "delete.left")
                .font(.system(size: 17, weight: .regular))
                .frame(width: width, height: height)
        }
        .padding(hit)
        .contentShape(.rect)
        .gesture(
            DragGesture(minimumDistance: 0)
                .updating($pressed) { _, state, transaction in
                    transaction.animation = nil
                    state = true
                }
        )
        .onChange(of: pressed) { _, down in
            repeating?.cancel()
            repeating = nil
            guard down else { return }
            model.feedback()
            model.deleteBackward()
            repeating = Task { @MainActor in
                try? await Task.sleep(for: .milliseconds(500))
                while !Task.isCancelled {
                    model.feedback()
                    model.deleteBackward()
                    try? await Task.sleep(for: .milliseconds(100))
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { model.deleteBackward() }
    }
}
