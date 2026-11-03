import Observation
import SwiftUI
import UIKit

// Why the keys used to feel slow, and what this file does about it:
//
// 1. The system's gesture recognizers on the keyboard's window (the screen-edge and home-indicator gates) have
//    `delaysTouchesBegan` on: every touch reached the keys late, worst on the bottom row and near the edges.
//    `SystemTouchDelays` turns those delays off (the controller calls it once the keyboard is in its window).
// 2. A SwiftUI `DragGesture` per key went through SwiftUI's gesture pipeline before the key saw the touch, and handled
//    two-finger rollover typing poorly. Now ONE UIKit view (`KeyTouchView`) lies over the whole key grid, takes every
//    finger directly in `touchesBegan`, finds the key from the frames SwiftUI reports (`KeyAnchors`) and acts at once.
//    The SwiftUI keys only draw.
// 3. Letters were typed when the finger lifted. They are now typed the instant it lands, as the stock keyboard shows
//    its key popup on touch down; a new finger landing finishes every earlier one at once (rollover).
// 4. Each key's pressed state is its own tiny observable (`KeyPress`): a press redraws only that key, and nothing
//    animates it, so the highlight appears on touch down and is gone on lift, with no fade.

/// Which key a touch is on. Letters, digits and symbols are their own text (each is unique on its page).
enum KeyID: Hashable {
    case character(String)
    case shift, delete, symbols, page, globe, language, space, newline
}

/// What a key does with a touch.
struct KeyBehavior {
    enum Commit { case down, up }

    /// `.down`: acts the instant the finger lands (letters, space, shift, delete). `.up`: acts when it lifts, or when
    /// another finger lands first (return, 123, language, globe).
    var commit: Commit = .down
    /// Held, it acts again after 0.5 s and then every 0.1 s until the finger lifts (delete).
    var repeats = false
    var action: @MainActor () -> Void
    /// Held 0.45 s: runs this (a letter's alternate replaces the letter just typed).
    var longPress: (@MainActor () -> Void)?
}

/// One key's pressed state. Each key watches only its own, so a press redraws one key, not the keyboard.
@Observable
final class KeyPress {
    var isDown = false
}

/// The pressed state of every key, by key.
@MainActor
final class KeyPresses {
    private var states: [KeyID: KeyPress] = [:]

    func state(_ id: KeyID) -> KeyPress {
        if let state = states[id] { return state }
        let state = KeyPress()
        states[id] = state
        return state
    }

    /// Changes the key only if its state really changes (a write would redraw it even with the same value).
    func set(_ id: KeyID, _ down: Bool) {
        let press = state(id)
        if press.isDown != down { press.isDown = down }
    }

    func clearAll() {
        for state in states.values where state.isDown { state.isDown = false }
    }
}

/// Every key reports its touch area (its cap plus the half gaps around it), so the touch view can tell which key a
/// finger is on.
struct KeyAnchors: PreferenceKey {
    static var defaultValue: [KeyID: Anchor<CGRect>] { [:] }

    static func reduce(value: inout [KeyID: Anchor<CGRect>], nextValue: () -> [KeyID: Anchor<CGRect>]) {
        value.merge(nextValue()) { _, new in new }
    }
}

/// The one UIKit view that takes the touches for the whole key grid.
struct KeyTouchSurface: UIViewRepresentable {
    let frames: [KeyID: CGRect]
    let presses: KeyPresses
    let feedback: @MainActor () -> Void
    let behavior: @MainActor (KeyID) -> KeyBehavior?

    func makeUIView(context: Context) -> KeyTouchView {
        KeyTouchView(presses: presses)
    }

    func updateUIView(_ view: KeyTouchView, context: Context) {
        view.frames = frames
        view.feedback = feedback
        view.behavior = behavior
    }

    /// The keys went away (✨ results, the panel) with a finger still down: no key stays lit, nothing keeps repeating.
    static func dismantleUIView(_ view: KeyTouchView, coordinator: ()) {
        view.cancelAll()
    }
}

/// Takes every finger on the key grid and acts on it synchronously, in `touchesBegan` / `touchesEnded`, with no
/// gesture recognizer in between. Each finger keeps the key it landed on until it lifts.
final class KeyTouchView: UIView {
    var frames: [KeyID: CGRect] = [:]
    var feedback: @MainActor () -> Void = {}
    var behavior: @MainActor (KeyID) -> KeyBehavior? = { _ in nil }

    private let presses: KeyPresses

    /// One finger on one key.
    private final class Press {
        let touch: UITouch  // kept, so its identifier can't be reused while it is tracked
        let id: KeyID
        let behavior: KeyBehavior
        var pendingUp: Bool  // an `.up` key that hasn't acted yet
        var lit = true
        var timer: Timer?

        init(touch: UITouch, id: KeyID, behavior: KeyBehavior) {
            self.touch = touch
            self.id = id
            self.behavior = behavior
            pendingUp = behavior.commit == .up
        }
    }

    private var active: [ObjectIdentifier: Press] = [:]

    init(presses: KeyPresses) {
        self.presses = presses
        super.init(frame: .zero)
        backgroundColor = .clear
        isMultipleTouchEnabled = true  // rollover: a second finger lands while the first is still down
        isExclusiveTouch = false
        accessibilityElementsHidden = true  // VoiceOver uses the SwiftUI keys underneath
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window == nil {
            cancelAll()
        } else {
            // The window's gates, and SwiftUI's recognizers on the hosting view above, must not hold a touch or its
            // lift back from this view either.
            SystemTouchDelays.remove(above: self)
        }
    }

    // MARK: Touches

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        dropLostTouches()
        for touch in touches {
            rollOver()  // every earlier finger is done the moment a new one lands
            guard let id = key(at: touch.location(in: self)), let does = behavior(id) else { continue }
            let touchKey = ObjectIdentifier(touch)
            let press = Press(touch: touch, id: id, behavior: does)
            active[touchKey] = press
            presses.set(id, true)  // drawn in this same frame: no animation, no gesture recognizer to wait for
            if does.commit == .down { does.action() }
            feedback()
            if does.repeats {
                press.timer = schedule(after: 0.5, every: 0.1) { [weak self] in self?.repeatKey(touchKey) }
            } else if does.longPress != nil {
                press.timer = schedule(after: 0.45, every: nil) { [weak self] in self?.longPressKey(touchKey) }
            }
        }
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        // A finger keeps the key it landed on (the letter is already typed).
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            guard let press = active.removeValue(forKey: ObjectIdentifier(touch)) else { continue }
            finish(press, commit: true)
        }
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        for touch in touches {
            guard let press = active.removeValue(forKey: ObjectIdentifier(touch)) else { continue }
            finish(press, commit: false)
        }
    }

    /// Lets go of every finger without acting (the keys are leaving the screen).
    func cancelAll() {
        let all = Array(active.values)
        active = [:]
        for press in all { finish(press, commit: false) }
        presses.clearAll()
    }

    // MARK: Keys

    /// The key whose touch area holds the point, or the nearest one within 20 pt (the areas tile the grid; this only
    /// catches rounding at their seams).
    private func key(at point: CGPoint) -> KeyID? {
        var nearest: (id: KeyID, distance: CGFloat)?
        for (id, rect) in frames {
            if rect.contains(point) { return id }
            let dx = max(rect.minX - point.x, 0, point.x - rect.maxX)
            let dy = max(rect.minY - point.y, 0, point.y - rect.maxY)
            let distance = dx * dx + dy * dy
            if distance < (nearest?.distance ?? .infinity) { nearest = (id, distance) }
        }
        guard let nearest, nearest.distance <= 400 else { return nil }
        return nearest.id
    }

    /// Every finger still down is finished now: its `.up` action runs, its timers stop, its key goes dark.
    private func rollOver() {
        for press in active.values {
            press.timer?.invalidate()
            press.timer = nil
            unlight(press)
            if press.pendingUp {
                press.pendingUp = false
                press.behavior.action()
            }
        }
    }

    private func finish(_ press: Press, commit: Bool) {
        press.timer?.invalidate()
        press.timer = nil
        unlight(press)
        if commit && press.pendingUp {
            press.pendingUp = false
            press.behavior.action()
        }
    }

    /// The key goes dark at once, unless another finger is holding the same key.
    private func unlight(_ press: Press) {
        guard press.lit else { return }
        press.lit = false
        if !active.values.contains(where: { $0 !== press && $0.lit && $0.id == press.id }) {
            presses.set(press.id, false)
        }
    }

    /// A touch whose end never arrived (the system took it) is let go, so its key doesn't stay lit.
    private func dropLostTouches() {
        for (key, press) in active where press.touch.phase == .ended || press.touch.phase == .cancelled {
            active[key] = nil
            finish(press, commit: false)
        }
    }

    private func repeatKey(_ key: ObjectIdentifier) {
        guard let press = active[key], press.lit else { return }
        feedback()
        press.behavior.action()
    }

    private func longPressKey(_ key: ObjectIdentifier) {
        guard let press = active[key], press.lit, let longPress = press.behavior.longPress else { return }
        press.timer = nil
        press.pendingUp = false
        longPress()
    }

    /// A main-run-loop timer in the common modes (it fires while a finger is down).
    private func schedule(after delay: TimeInterval, every interval: TimeInterval?,
                          _ fire: @escaping @MainActor @Sendable () -> Void) -> Timer {
        let timer = Timer(fire: Date(timeIntervalSinceNow: delay), interval: interval ?? 0,
                          repeats: interval != nil) { _ in
            MainActor.assumeIsolated { fire() }
        }
        RunLoop.main.add(timer, forMode: .common)
        return timer
    }
}

/// The keyboard's window carries the system's gesture recognizers (the screen-edge and home-indicator gates). They
/// hold every touch back (`delaysTouchesBegan`) until they decide it isn't theirs: the classic custom-keyboard lag,
/// worst on the bottom row and near the edges. They also hold back the lift (`delaysTouchesEnded`), which kept a key
/// lit after the finger left it. Both delays are turned off on every view above the given one, up to and including
/// the window. Only the delays change: no recognizer is removed or disabled.
///
/// `cancelsTouchesInView` stays on: when the system does take a touch (a swipe home that starts on the keys), the key
/// must hear about it, so a held delete stops repeating and no key stays lit.
enum SystemTouchDelays {
    @MainActor
    static func remove(above view: UIView) {
        var current = view.superview
        while let ancestor = current {
            for recognizer in ancestor.gestureRecognizers ?? [] {
                if recognizer.delaysTouchesBegan { recognizer.delaysTouchesBegan = false }
                if recognizer.delaysTouchesEnded { recognizer.delaysTouchesEnded = false }
            }
            current = ancestor.superview
        }
    }
}
