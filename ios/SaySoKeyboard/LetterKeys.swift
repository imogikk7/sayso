import SwiftUI

/// SaySo's own letter keys: Russian and English, numbers and symbols, shift, delete that repeats, space, return.
/// Long press types the alternate (ё, ъ, Kazakh letters). No autocorrect.
///
/// Laid out like the stock keyboard (sizes in `KeyMetrics`): letter keys keep one width on every row, shorter rows are
/// centered, and each key's touch area takes in half the gap around it (the outer keys reach the keyboard's edges), so
/// a tap between two keys still types one.
///
/// The keys here only draw. Touches go to one UIKit view over the grid (`KeyTouchSurface`, see KeyTouches.swift for
/// why): each key reports its touch area through `KeyAnchors`, and `behavior(_:)` says what it does.
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
        // Nothing animates on the keys: not a press, not shift, not a page or language change (no fade on release).
        .transaction { $0.animation = nil }
        .overlayPreferenceValue(KeyAnchors.self) { anchors in
            GeometryReader { proxy in
                KeyTouchSurface(frames: anchors.mapValues { proxy[$0] }, presses: model.presses,
                                feedback: { model.feedback() }, behavior: { behavior($0) })
            }
        }
        .frame(maxHeight: .infinity, alignment: .bottom)
    }

    /// What each key does. Letters, space, shift and delete act on touch down (as fast as a key can be); return and
    /// the keys that change the layout act on lift, or as soon as another finger lands.
    private func behavior(_ id: KeyID) -> KeyBehavior? {
        switch id {
        case .character(let key):
            var letter = KeyBehavior(action: { model.type(key) })
            if model.page == .letters && alternates[key] != nil {
                letter.longPress = { model.swapForAlternate(key) }
            }
            return letter
        case .shift:
            return KeyBehavior(action: { model.toggleShift() })
        case .delete:
            return KeyBehavior(repeats: true, action: { model.deleteBackward() })
        case .space:
            return KeyBehavior(action: { model.space() })
        case .symbols:
            return KeyBehavior(commit: .up, action: { model.page = model.page == .numbers ? .symbols : .numbers })
        case .page:
            return KeyBehavior(commit: .up, action: { model.page = model.page == .letters ? .numbers : .letters })
        case .globe:
            return KeyBehavior(commit: .up, action: { model.nextKeyboard() })
        case .language:
            return KeyBehavior(commit: .up, action: { model.switchLanguage() })
        case .newline:
            return KeyBehavior(commit: .up, action: { model.newline() })
        }
    }

    /// A key that draws itself pressed while `id` is down (VoiceOver activates it through `behavior`).
    private func keyView<Label: View>(_ id: KeyID, kind: KeyKind, width: CGFloat?, hit: EdgeInsets,
                                      callout: KeyCallout? = nil,
                                      @ViewBuilder label: @escaping (Bool) -> Label) -> KeyView<Label> {
        KeyView(id: id, kind: kind, width: width, height: metrics.keyHeight, hit: hit,
                press: model.presses.state(id), callout: callout,
                activate: { behavior(id)?.action() }, label: label)
    }

    /// A row of letters, centered, each key `key` wide.
    private func letterRow(_ keys: [String], key: CGFloat, gap: CGFloat, width: CGFloat,
                           vertical: (top: CGFloat, bottom: CGFloat)) -> some View {
        let used = CGFloat(keys.count) * key + CGFloat(max(keys.count - 1, 0)) * gap
        let edge = max(0, (width - used) / 2)
        return HStack(spacing: 0) {
            letters(keys, key: key, gap: gap, leading: edge, trailing: edge, room: edge, vertical: vertical)
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
        let shift = model.shift
        let page = model.page
        return HStack(spacing: 0) {
            if letterPage {
                keyView(.shift, kind: .special, width: side, hit: hit(metrics.side, around / 2)) { _ in
                    Image(systemName: shift == .caps ? "capslock.fill" : shift == .on ? "shift.fill" : "shift")
                        .font(.system(size: 17, weight: .regular))
                }
            } else {
                keyView(.symbols, kind: .special, width: side, hit: hit(metrics.side, around / 2)) { _ in
                    Text(page == .numbers ? "#+=" : "123").font(.system(size: 16))
                }
            }
            letters(keys, key: keyWidth, gap: gap, leading: around / 2, trailing: around / 2, room: .infinity,
                    vertical: vertical)
            keyView(.delete, kind: .special, width: side, hit: hit(around / 2, metrics.side)) { pressed in
                Image(systemName: pressed ? "delete.left.fill" : "delete.left")
                    .font(.system(size: 17, weight: .regular))
                    .contentTransition(.identity)
            }
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
        let page = model.page
        let language = model.language
        let returnLabel = model.returnLabel
        return HStack(spacing: 0) {
            keyView(.page, kind: .special, width: function, hit: hit(metrics.side, half)) { _ in
                Text(page == .letters ? "123" : "ABC").font(.system(size: 16))
            }
            if model.showsGlobe {
                keyView(.globe, kind: .special, width: function, hit: hit(half, half)) { _ in
                    Image(systemName: "globe").font(.system(size: 17, weight: .regular))
                }
            }
            keyView(.language, kind: .special, width: function, hit: hit(half, half)) { _ in
                Text(language.switchLabel).font(.system(size: 16))
            }
            keyView(.space, kind: .letter, width: nil, hit: hit(half, half)) { _ in
                Text(language.spaceLabel).font(.system(size: 16))
            }
            keyView(.newline, kind: returnLabel == "return" ? .special : .accent, width: metrics.returnWidth(width),
                hit: hit(half, metrics.side)) { _ in
                Text(returnLabel).font(.system(size: 16))
            }
        }
        .frame(width: width)
    }

    /// Letter keys side by side; `key` nil makes them share the row's width. The first and last reach out by
    /// `leading` / `trailing`, the others by half a gap. `room` is how far the outer keys are from the keyboard's
    /// edges (their popup stays on screen).
    @ViewBuilder
    private func letters(_ keys: [String], key: CGFloat?, gap: CGFloat, leading: CGFloat, trailing: CGFloat,
                         room: CGFloat, vertical: (top: CGFloat, bottom: CGFloat)) -> some View {
        let upper = model.page == .letters && model.shift != .off
        let page = model.page
        let font = letterFont
        // The stock popup: as tall as the strip lets the top row's reach (the keyboard can't draw above itself).
        let calloutTop = min(metrics.keyHeight * 1.05, metrics.strip + metrics.top - KeyCallout.flare - 1)
        let calloutFont = Font.system(size: metrics.keyHeight > 40 ? 32 : 26)
        let overhang = ((key ?? 33) * 0.3).rounded()
        ForEach(Array(keys.enumerated()), id: \.element) { index, letter in
            let hasAlternate = page == .letters && alternates[letter] != nil
            let shown = upper ? letter.uppercased() : letter
            let callout = KeyCallout(text: shown, font: calloutFont, topHeight: calloutTop,
                                     leading: index == 0 ? max(0, min(overhang, room - 1)) : overhang,
                                     trailing: index == keys.count - 1 ? max(0, min(overhang, room - 1)) : overhang)
            keyView(.character(letter), kind: .letter, width: key,
                    hit: EdgeInsets(top: vertical.top, leading: index == 0 ? leading : gap / 2,
                                    bottom: vertical.bottom, trailing: index == keys.count - 1 ? trailing : gap / 2),
                    callout: callout) { _ in
                Text(shown)
                    .font(font)
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

/// One key, drawn only: lit while its `KeyPress` is down. It reads nothing else that changes on a press, so a press
/// redraws this key alone. Its touch area (the cap plus `hit` around it) goes to the touch view through `KeyAnchors`.
struct KeyView<Label: View>: View {
    let id: KeyID
    let kind: KeyKind
    let width: CGFloat?  // nil: as wide as the row allows
    let height: CGFloat
    let hit: EdgeInsets
    let press: KeyPress
    let callout: KeyCallout?
    let activate: @MainActor () -> Void
    let label: (Bool) -> Label

    var body: some View {
        let pressed = press.isDown
        KeyCap(kind: kind, pressed: pressed) {
            label(pressed)
                .frame(minWidth: width, maxWidth: width ?? .infinity, minHeight: height, maxHeight: height)
        }
        .overlay {
            if pressed, let callout { callout }
        }
        .padding(hit)
        .anchorPreference(key: KeyAnchors.self, value: .bounds) { [id: $0] }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { activate() }
    }
}

/// The stock key popup: the letter, bigger, in a balloon over the key, shown the instant the finger lands and gone the
/// instant it lifts. Its neck is the key itself; its head is `leading` / `trailing` wider than the key.
struct KeyCallout: View {
    /// From the head down to the key's top.
    static let flare: CGFloat = 8

    let text: String
    let font: Font
    let topHeight: CGFloat
    let leading: CGFloat
    let trailing: CGFloat

    @Environment(\.colorScheme) private var scheme

    var body: some View {
        GeometryReader { geometry in
            let key = geometry.size
            let width = key.width + leading + trailing
            let height = key.height + Self.flare + topHeight
            ZStack(alignment: .top) {
                CalloutShape(neckLeading: leading, neckWidth: key.width, neckHeight: key.height, flare: Self.flare)
                    .fill(KeyTheme.calloutFill(scheme))
                    .shadow(color: Color.black.opacity(scheme == .dark ? 0.5 : 0.3), radius: 1.5, x: 0, y: 0.5)
                Text(text)
                    .font(font)
                    .foregroundStyle(KeyTheme.keyText(scheme))
                    .frame(width: width, height: topHeight)
            }
            .frame(width: width, height: height)
            // The neck lines up with the key: bottom on its bottom, `leading` out from its left edge.
            .position(x: width / 2 - leading, y: key.height - height / 2)
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

/// A balloon: a wide rounded head that narrows into a neck the size of the key below it.
struct CalloutShape: Shape {
    let neckLeading: CGFloat
    let neckWidth: CGFloat
    let neckHeight: CGFloat
    let flare: CGFloat

    func path(in rect: CGRect) -> Path {
        let head: CGFloat = 8  // the head's corners
        let neck = KeyTheme.key  // the key's corners
        let headBottom = rect.maxY - neckHeight - flare
        let neckTop = headBottom + flare
        let left = rect.minX + neckLeading
        let right = left + neckWidth
        var path = Path()
        path.move(to: CGPoint(x: rect.minX + head, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX - head, y: rect.minY))
        path.addQuadCurve(to: CGPoint(x: rect.maxX, y: rect.minY + head), control: CGPoint(x: rect.maxX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: headBottom))
        path.addCurve(to: CGPoint(x: right, y: neckTop), control1: CGPoint(x: rect.maxX, y: headBottom + flare / 2),
                      control2: CGPoint(x: right, y: headBottom + flare / 2))
        path.addLine(to: CGPoint(x: right, y: rect.maxY - neck))
        path.addQuadCurve(to: CGPoint(x: right - neck, y: rect.maxY), control: CGPoint(x: right, y: rect.maxY))
        path.addLine(to: CGPoint(x: left + neck, y: rect.maxY))
        path.addQuadCurve(to: CGPoint(x: left, y: rect.maxY - neck), control: CGPoint(x: left, y: rect.maxY))
        path.addLine(to: CGPoint(x: left, y: neckTop))
        path.addCurve(to: CGPoint(x: rect.minX, y: headBottom), control1: CGPoint(x: left, y: headBottom + flare / 2),
                      control2: CGPoint(x: rect.minX, y: headBottom + flare / 2))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY + head))
        path.addQuadCurve(to: CGPoint(x: rect.minX + head, y: rect.minY), control: CGPoint(x: rect.minX, y: rect.minY))
        path.closeSubpath()
        return path
    }
}
